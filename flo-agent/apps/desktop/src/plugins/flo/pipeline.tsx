/**
 * Pipeline — every file as one plain row; opening a file shows one clean
 * summary with one-click actions (Request From Borrower, Order Title/HOI,
 * Ask Flo, Why?) and optional expandable detail areas. Every button goes
 * through Flo (`./chat.ts`); Ashley never picks a bot.
 *
 * Ashley-facing drop affordance: dropping PDF / image files anywhere on the
 * file view attaches them to the open loan via the existing
 * `uploadDocumentsPrompt` flow. We deliberately don't import the chat
 * app's `useFileDropZone` (plugins are forbidden from reaching into the
 * chat internals); instead this minimal inline handler covers the 90% case
 * of native file drops, with the same `dataTransfer.items` extraction
 * pattern.
 */

import { Button, cn, host, Loader, useValue } from '@hermes/plugin-sdk'
import {
  type DragEvent as ReactDragEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react'

import {
  activeEsignRequest,
  askFloPrompt,
  borrowerRequestPrompt,
  borrowerRequestWaiting,
  conditionItem,
  conditionPlainEnglish,
  conditionsByOwner,
  conditionStatus,
  conditionStatusTone,
  confirmCtcPrompt,
  ctcReadiness,
  dismissCtcPrompt,
  documentBoard,
  documentsReceived,
  type DocumentView,
  editDraftPrompt,
  eligibleEsignTemplate,
  emailConditionsApplyPrompt,
  emailConditionsDismissPrompt,
  ESIGN_STATUS_LABEL,
  esignCancelPrompt,
  esignReminderPrompt,
  type EsignRequest,
  type FileRecord,
  fileSummary,
  groupedOwnerCount,
  loRequestPrompt,
  missingDocumentDraft,
  missingDocuments,
  notNeededDocumentPrompt,
  ORDER_TYPE_LABEL,
  orderPrompt,
  orderStateLabel,
  ownerHasWaiting,
  pendingCtcProposal,
  pendingEmailConditions,
  prefillSignRecipients,
  reclassifyDocumentPrompt,
  requestedMissingItems,
  requestPrompt,
  reviewDraftPrompt,
  reviewEmailPrompt,
  sendDraftPrompt,
  sendForSignaturePrompt,
  STATUS_TONE,
  teamHints,
  uploadDocumentsPrompt,
  waitingLabel,
  type WhyKind,
  whyPrompt
} from './ashley'
import { preferFloProfile, reportStartFailure, runFloInBackground, startFloChat } from './chat'
import { type TeamState, useTeamState } from './state'
import { Fact, Pill } from './ui'

export const PIPELINE_ROUTE = '/pipeline'

/** `?file=<id>` from the hash route, kept in sync with navigation. */
function useFileParam(): [null | string, (id: null | string) => void] {
  const read = () => {
    const query = window.location.hash.split('?')[1] ?? ''

    return new URLSearchParams(query).get('file')
  }

  const [file, setFile] = useState<null | string>(read)
  useEffect(() => {
    const onChange = () => setFile(read())
    window.addEventListener('hashchange', onChange)

    return () => window.removeEventListener('hashchange', onChange)
  }, [])

  const set = (id: null | string) => {
    setFile(id)
    host.navigate(id ? `${PIPELINE_ROUTE}?file=${encodeURIComponent(id)}` : PIPELINE_ROUTE)
  }

  return [file, set]
}

export function useAsk(state: TeamState | null) {
  const activeProfile = useValue(host.state.profile) as null | string | undefined
  const [busy, setBusy] = useState<null | string>(null)
  const profile = preferFloProfile(state?.profiles ?? [], activeProfile)

  const ask = useCallback(
    (id: string, title: string, prompt: string) => {
      setBusy(id)
      void startFloChat(title, prompt, profile)
        .catch((error: unknown) => reportStartFailure(title, error))
        .finally(() => setBusy(null))
    },
    [profile]
  )

  const background = useCallback(
    (id: string, title: string, prompt: string) => {
      setBusy(id)
      void runFloInBackground(title, prompt, profile)
        .catch((error: unknown) => reportStartFailure(title, error))
        .finally(() => setBusy(null))
    },
    [profile]
  )

  return { ask, background, busy, profile }
}

function WhyButton({ busy, label = 'Why?', onClick }: { busy: boolean; label?: string; onClick: () => void }) {
  return (
    <button
      className="text-xs text-(--ui-text-tertiary) hover:underline"
      disabled={busy}
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  )
}

function toFileUrl(path: string): string {
  const normalised = path.replace(/\\/g, '/')

  return `file://${normalised.startsWith('/') ? '' : '/'}${normalised.split('/').map(encodeURIComponent).join('/')}`
}

/** Ashley's "Send for Signature" review panel — the one new surface this feature adds, inline in the
 * existing Documents section (no new dashboard, no new agent). Opens read-only ("review") with the loan's
 * recipients prefilled; [Edit] unlocks the fields, [Send for Signature] confirms and hands off to Flo
 * (`flo_esign_send`, which stops at Ashley's native approval prompt), [Cancel] closes without sending. */
function SendForSignaturePanel({
  ws,
  doc,
  isBusy,
  onSend,
  onClose
}: {
  ws: FileRecord
  doc: DocumentView
  isBusy: boolean
  onSend: (
    templateKey: string,
    recipients: Array<{ name: string; email: string; role: string }>,
    message: string
  ) => void
  onClose: () => void
}) {
  const template = eligibleEsignTemplate(doc)
  const [mode, setMode] = useState<'review' | 'edit'>('review')

  const [recipients, setRecipients] = useState(() => {
    const prefilled = prefillSignRecipients(ws)

    return prefilled.length > 0 ? prefilled : [{ name: '', email: '', role: 'SIGNER' }]
  })

  const [message, setMessage] = useState(
    `Please review and sign the attached ${doc.subtype ?? doc.categoryLabel.toLowerCase()}.`
  )

  if (!template) {
    return (
      <div className="rounded-md border border-(--ui-stroke-tertiary) p-3 text-sm text-(--ui-text-secondary)">
        This document needs signing setup.
        <button className="ml-2 text-xs text-(--ui-text-tertiary) hover:underline" onClick={onClose} type="button">
          Close
        </button>
      </div>
    )
  }

  const setRecipient = (i: number, field: 'name' | 'email', value: string) =>
    setRecipients(rows => rows.map((r, idx) => (idx === i ? { ...r, [field]: value } : r)))

  const canSend = recipients.length > 0 && recipients.every(r => r.name.trim() && /.+@.+\..+/.test(r.email))

  return (
    <div className="flex flex-col gap-3 rounded-md border border-(--ui-accent) p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold">Send for Signature</span>
        <span className="text-xs text-(--ui-text-tertiary)">· {template.label}</span>
        <button className="ml-auto text-xs text-(--ui-text-tertiary) hover:underline" onClick={onClose} type="button">
          Close
        </button>
      </div>
      <Fact label="Document" value={doc.name} />
      <div className="flex flex-col gap-2">
        <span className="text-[0.6875rem] uppercase tracking-wide text-(--ui-text-tertiary)">
          {recipients.length > 1 ? 'Signers' : 'Signer'}
        </span>
        {recipients.map((r, i) =>
          mode === 'edit' ? (
            <div className="flex flex-wrap gap-2" key={i}>
              <input
                className="min-w-0 flex-1 rounded border border-(--ui-stroke-tertiary) bg-transparent px-2 py-1 text-sm"
                onChange={e => setRecipient(i, 'name', e.target.value)}
                placeholder="Full name"
                value={r.name}
              />
              <input
                className="min-w-0 flex-1 rounded border border-(--ui-stroke-tertiary) bg-transparent px-2 py-1 text-sm"
                onChange={e => setRecipient(i, 'email', e.target.value)}
                placeholder="Email address"
                value={r.email}
              />
            </div>
          ) : (
            <span className="text-sm" key={i}>
              {r.name || '(name needed)'} {r.email ? `<${r.email}>` : '(email needed)'}
            </span>
          )
        )}
        {mode === 'edit' ? (
          <button
            className="self-start text-xs text-(--ui-text-tertiary) hover:underline"
            onClick={() => setRecipients(rows => [...rows, { name: '', email: '', role: 'SIGNER' }])}
            type="button"
          >
            + Add another signer
          </button>
        ) : null}
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-[0.6875rem] uppercase tracking-wide text-(--ui-text-tertiary)">Message</span>
        {mode === 'edit' ? (
          <textarea
            className="rounded border border-(--ui-stroke-tertiary) bg-transparent px-2 py-1 text-sm"
            onChange={e => setMessage(e.target.value)}
            rows={2}
            value={message}
          />
        ) : (
          <p className="m-0 text-sm text-(--ui-text-secondary)">{message}</p>
        )}
      </div>
      <Fact label="Fields" value="Signature, Date" />
      {!canSend ? (
        <p className="m-0 text-xs text-destructive">
          Every signer needs a name and a valid email before this can be sent.
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button disabled={isBusy || !canSend} onClick={() => onSend(template.key, recipients, message)} size="xs">
          Send for Signature
        </Button>
        <Button onClick={() => setMode(m => (m === 'edit' ? 'review' : 'edit'))} size="xs" variant="secondary">
          {mode === 'edit' ? 'Done Editing' : 'Edit'}
        </Button>
        <Button onClick={onClose} size="xs" variant="secondary">
          Cancel
        </Button>
      </div>
    </div>
  )
}

/** Status + Remind/Cancel for a document that already has a live signature request. */
function EsignStatusPanel({
  request,
  isBusy,
  onRemind,
  onCancel
}: {
  request: EsignRequest
  isBusy: boolean
  onRemind: () => void
  onCancel: () => void
}) {
  const label = ESIGN_STATUS_LABEL[request.status ?? 'draft'] ?? 'Needs attention'
  const canRemind = request.status === 'sent' || request.status === 'partially_signed'
  const canCancel = canRemind

  return (
    <div className="flex flex-col gap-2 rounded-md border border-(--ui-stroke-tertiary) p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone={label === 'Signed' ? 'good' : label === 'Needs attention' ? 'warn' : 'muted'}>{label}</Pill>
        {(request.recipients ?? []).map(r => (
          <span className="text-xs text-(--ui-text-secondary)" key={r.email}>
            {r.name} &lt;{r.email}&gt;
          </span>
        ))}
      </div>
      {request.explanation ? <p className="m-0 text-xs text-(--ui-text-secondary)">{request.explanation}</p> : null}
      {canRemind || canCancel ? (
        <div className="flex flex-wrap gap-2">
          {canRemind ? (
            <Button disabled={isBusy} onClick={onRemind} size="xs" variant="secondary">
              Send Reminder
            </Button>
          ) : null}
          {canCancel ? (
            <Button disabled={isBusy} onClick={onCancel} size="xs" variant="secondary">
              Cancel Request
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

/** Inline viewer for one document (PDF or image) from the private copy on this machine. */
function DocumentPreview({
  ws,
  doc,
  isBusy,
  onClose,
  onNotNeeded,
  onReclassify,
  onSendForSignature,
  onRemindSignature,
  onCancelSignature
}: {
  ws: FileRecord
  doc: DocumentView
  isBusy: boolean
  onClose: () => void
  onNotNeeded: () => void
  onReclassify: () => void
  onSendForSignature: (
    templateKey: string,
    recipients: Array<{ name: string; email: string; role: string }>,
    message: string
  ) => void
  onRemindSignature: () => void
  onCancelSignature: () => void
}) {
  const [dataUrl, setDataUrl] = useState<null | string>(null)
  const [error, setError] = useState<null | string>(null)
  const isImage = /\.(png|jpe?g|gif|webp)$/i.test(doc.name)
  const isPdf = /\.pdf$/i.test(doc.name)

  useEffect(() => {
    let cancelled = false
    setDataUrl(null)
    setError(null)

    if (!doc.path) {
      setError('The file has not been received yet.')

      return
    }

    if (!isImage && !isPdf) {
      setError('No inline preview for this file type. Open it to view.')

      return
    }

    window.hermesDesktop
      ?.readFileDataUrl(doc.path)
      .then(url => {
        if (!cancelled) {
          setDataUrl(url)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Could not load the preview. Open it to view.')
        }
      })

    return () => {
      cancelled = true
    }
  }, [doc.path, doc.name, isImage, isPdf])

  const open = () => {
    if (doc.path) {
      void window.hermesDesktop?.openExternal(toFileUrl(doc.path)).catch(() => setError('Could not open the file.'))
    }
  }

  const [showSendPanel, setShowSendPanel] = useState(false)
  const eligible = eligibleEsignTemplate(doc)
  const activeRequest = activeEsignRequest(ws, doc.id)

  return (
    <div className="flex flex-col gap-2 rounded-md border border-(--ui-stroke-tertiary) p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{doc.name}</span>
        <Pill tone={doc.attention ? 'warn' : 'muted'}>{doc.statusLabel}</Pill>
        <button className="ml-auto text-xs text-(--ui-text-tertiary) hover:underline" onClick={onClose} type="button">
          Close
        </button>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Fact label="Category" value={doc.subtype ? `${doc.categoryLabel} · ${doc.subtype}` : doc.categoryLabel} />
        <Fact label="Received" value={doc.received ?? '—'} />
        <Fact label="Status" tone={doc.attention ? 'warn' : undefined} value={doc.statusLabel} />
        <Fact label="Borrower" value={doc.borrower ?? '—'} />
      </div>
      {doc.note ? <p className="m-0 text-xs text-(--ui-text-secondary)">{doc.note}</p> : null}
      {dataUrl && isPdf ? (
        <iframe className="h-[28rem] w-full rounded border-0 bg-white" src={dataUrl} title={doc.name} />
      ) : null}
      {dataUrl && isImage ? (
        <img alt={doc.name} className="max-h-[28rem] w-auto self-start rounded" src={dataUrl} />
      ) : null}
      {!dataUrl && !error ? <Loader /> : null}
      {error ? <p className="m-0 text-xs text-(--ui-text-secondary)">{error}</p> : null}
      <div className="flex flex-wrap gap-2">
        <Button disabled={!doc.path} onClick={open} size="xs" variant="secondary">
          Open
        </Button>
        {dataUrl ? (
          <a
            className="inline-flex items-center rounded border border-(--ui-stroke-tertiary) px-2 text-xs hover:bg-(--chrome-action-hover)"
            download={doc.name}
            href={dataUrl}
          >
            Download
          </a>
        ) : null}
        {doc.status !== 'not_needed' ? (
          <Button disabled={isBusy} onClick={onNotNeeded} size="xs" variant="secondary">
            Mark Not Needed
          </Button>
        ) : null}
        <Button disabled={isBusy} onClick={onReclassify} size="xs" variant="secondary">
          Reclassify
        </Button>
        {eligible && !activeRequest ? (
          <Button disabled={isBusy} onClick={() => setShowSendPanel(v => !v)} size="xs">
            Send for Signature
          </Button>
        ) : null}
      </div>
      {activeRequest ? (
        <EsignStatusPanel
          isBusy={isBusy}
          onCancel={onCancelSignature}
          onRemind={onRemindSignature}
          request={activeRequest}
        />
      ) : null}
      {showSendPanel && eligible ? (
        <SendForSignaturePanel
          doc={doc}
          isBusy={isBusy}
          onClose={() => setShowSendPanel(false)}
          onSend={(templateKey, recipients, message) => {
            onSendForSignature(templateKey, recipients, message)
            setShowSendPanel(false)
          }}
          ws={ws}
        />
      ) : null}
    </div>
  )
}

function DocumentsSection({
  ws,
  isBusy,
  ask,
  onRequest,
  why
}: {
  ws: FileRecord
  isBusy: boolean
  ask: (id: string, title: string, prompt: string) => void
  onRequest: () => void
  why: (subject: string) => void
}) {
  const name = ws.display_name ?? ws.workspace_id
  const groups = documentBoard(ws)
  const missing = missingDocuments(ws)
  const clarifications = ws.readiness ? [] : (ws.documents_summary?.needs_clarification ?? [])
  const received = documentsReceived(ws)
  const [showAll, setShowAll] = useState(false)
  const [preview, setPreview] = useState<null | DocumentView>(null)
  const attention = groups.reduce((n, g) => n + g.attention, 0)

  const upload = async () => {
    const paths = (await window.hermesDesktop?.selectPaths({ multiple: true }).catch(() => [])) ?? []

    if (paths.length > 0) {
      ask('upload-doc', `Add documents · ${name}`, uploadDocumentsPrompt(ws, paths))
    }
  }

  return (
    <details open={received > 0 || missing.length > 0}>
      <summary className="cursor-pointer text-sm">
        Documents
        {received > 0 ? ` · ${received} received` : ''}
        {missing.length > 0 ? ` · ${missing.length} missing` : ''}
        {attention > 0 ? ` · ${attention} need${attention === 1 ? 's' : ''} a look` : ''}
      </summary>
      <div className="mt-2 flex flex-col gap-3">
        {groups.length === 0 ? (
          <p className="m-0 text-xs text-(--ui-text-secondary)">Nothing missing that we know of.</p>
        ) : null}

        {groups.length > 0 ? (
          <ul className="m-0 flex list-none flex-col gap-2 p-0 text-sm">
            {groups.map(g => (
              <li key={g.category}>
                <span className="text-[0.6875rem] uppercase tracking-wide text-(--ui-text-tertiary)">{g.label}</span>
                <ul className="m-0 flex list-none flex-col gap-0.5 p-0">
                  {g.documents
                    .filter(d => showAll || (d.status !== 'duplicate' && d.status !== 'not_needed'))
                    .map(d => (
                      <li className="flex flex-wrap items-center gap-2" key={d.id}>
                        <span aria-hidden className={d.attention ? 'text-(--ui-accent)' : 'text-(--ui-text-tertiary)'}>
                          {d.attention ? '⚠' : '✓'}
                        </span>
                        <button className="text-left hover:underline" onClick={() => setPreview(d)} type="button">
                          {d.subtype ?? g.label}
                          {d.borrower ? ` · ${d.borrower}` : ''}
                        </button>
                        <span className="text-xs text-(--ui-text-tertiary)">{d.name}</span>
                        {d.status !== 'received' && d.status !== 'reviewed' ? (
                          <Pill tone={d.attention ? 'warn' : 'muted'}>{d.statusLabel}</Pill>
                        ) : null}
                        {d.note && d.attention ? (
                          <span className="text-xs text-(--ui-text-secondary)">{d.note}</span>
                        ) : null}
                        {(() => {
                          const esign = activeEsignRequest(ws, d.id)

                          return esign ? (
                            <Pill
                              tone={
                                esign.status === 'signed' || esign.status === 'retrieved'
                                  ? 'good'
                                  : esign.status === 'needs_attention' || esign.status === 'declined'
                                    ? 'warn'
                                    : 'muted'
                              }
                            >
                              {ESIGN_STATUS_LABEL[esign.status ?? 'draft'] ?? 'Needs attention'}
                            </Pill>
                          ) : null
                        })()}
                      </li>
                    ))}
                  {g.missing.map(item => (
                    <li className="flex flex-wrap items-center gap-2" key={`missing:${item}`}>
                      <span aria-hidden className="text-(--ui-accent)">
                        ⚠
                      </span>
                      <span>{item} missing</span>
                      <WhyButton busy={isBusy} onClick={() => why(item)} />
                    </li>
                  ))}
                  {g.waiting ? <li className="text-(--ui-text-tertiary)">Waiting</li> : null}
                </ul>
              </li>
            ))}
          </ul>
        ) : null}

        {clarifications.length > 0 ? (
          <ul className="m-0 flex list-none flex-col gap-0.5 p-0 text-xs text-(--ui-text-secondary)">
            {clarifications.map(c => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        ) : null}

        {preview ? (
          <DocumentPreview
            doc={preview}
            isBusy={isBusy}
            onCancelSignature={() => {
              const req = activeEsignRequest(ws, preview.id)

              if (req) {
                ask(`esign-cancel:${req.request_id}`, `Cancel signature · ${name}`, esignCancelPrompt(ws, req))
              }
            }}
            onClose={() => setPreview(null)}
            onNotNeeded={() =>
              ask(`not-needed:${preview.id}`, `Not needed · ${name}`, notNeededDocumentPrompt(ws, preview))
            }
            onReclassify={() =>
              ask(`reclassify:${preview.id}`, `Reclassify · ${name}`, reclassifyDocumentPrompt(ws, preview))
            }
            onRemindSignature={() => {
              const req = activeEsignRequest(ws, preview.id)

              if (req) {
                ask(`esign-remind:${req.request_id}`, `Remind · ${name}`, esignReminderPrompt(ws, req))
              }
            }}
            onSendForSignature={(templateKey, recipients, message) =>
              ask(
                `esign-send:${preview.id}`,
                `Send for signature · ${name}`,
                sendForSignaturePrompt(ws, preview, templateKey, recipients, message)
              )
            }
            ws={ws}
          />
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button disabled={isBusy} onClick={() => void upload()} size="xs" variant="secondary">
            Upload Missing Doc
          </Button>
          {missing.length > 0 ? (
            <Button
              disabled={isBusy || Boolean(missingDocumentDraft(ws)) || borrowerRequestWaiting(ws)}
              onClick={onRequest}
              size="xs"
            >
              Request Missing Documents
            </Button>
          ) : null}
          {groups.length > 0 ? (
            <Button onClick={() => setShowAll(v => !v)} size="xs" variant="secondary">
              {showAll ? 'Hide extras' : 'View Documents'}
            </Button>
          ) : null}
        </div>
      </div>
    </details>
  )
}

function EmailConditionsCard({
  ws,
  isBusy,
  ask
}: {
  ws: FileRecord
  isBusy: boolean
  ask: (id: string, title: string, prompt: string) => void
}) {
  const proposal = pendingEmailConditions(ws)

  if (!proposal) {return null}
  const name = ws.display_name ?? ws.workspace_id ?? 'this file'
  const items = proposal.proposed ?? []

  return (
    <div
      className="mb-2 flex flex-col gap-2 rounded-md border border-(--ui-accent) bg-(--ui-bg-quaternary) p-3"
      data-testid="email-conditions-card"
    >
      <div className="flex items-center gap-2">
        <span className="text-[0.6875rem] uppercase tracking-wide text-(--ui-text-tertiary)">
          New conditions · {name}
        </span>
      </div>
      <p className="m-0 text-sm">
        {items.length === 1
          ? '1 new condition detected from a lender email.'
          : `${items.length} new conditions detected from a lender email.`}
      </p>
      {proposal.email_already_applied ? (
        <p className="m-0 text-xs text-(--ui-text-secondary)">
          (Email was already applied — nothing new to add.)
        </p>
      ) : null}
      {items.length > 0 ? (
        <ul className="m-0 flex list-none flex-col gap-0.5 p-0 pl-4 text-sm">
          {items.map((c, i) => (
            <li key={(c.identity ?? '') + '-' + i}>
              {c.required_item ?? c.plain_english ?? c.condition_type ?? 'item'}
              {c.owner ? <span className="ml-1 text-xs text-(--ui-text-tertiary)">· {c.owner}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={isBusy || proposal.email_already_applied}
          onClick={() => ask('email-conditions-apply',
                            `Add conditions · ${name}`,
                            emailConditionsApplyPrompt(ws, proposal))}
          size="xs"
        >
          Add to File
        </Button>
        <Button
          disabled={isBusy}
          onClick={() => ask('email-conditions-review',
                            `Review email · ${name}`,
                            reviewEmailPrompt(ws, proposal))}
          size="xs"
          variant="secondary"
        >
          Review
        </Button>
        <Button
          disabled={isBusy}
          onClick={() => ask('email-conditions-dismiss',
                            `Dismiss conditions card · ${name}`,
                            emailConditionsDismissPrompt(ws, proposal))}
          size="xs"
          variant="secondary"
        >
          Not Now
        </Button>
      </div>
    </div>
  )
}

function CtcEmailCard({
  ws,
  isBusy,
  ask
}: {
  ws: FileRecord
  isBusy: boolean
  ask: (id: string, title: string, prompt: string) => void
}) {
  const proposal = pendingCtcProposal(ws)

  if (!proposal) {return null}
  const name = ws.display_name ?? ws.workspace_id ?? 'this file'
  const ambiguous = !proposal.is_ctc

  return (
    <div
      className="mb-2 flex flex-col gap-2 rounded-md border border-(--ui-accent) bg-(--ui-bg-quaternary) p-3"
      data-testid="ctc-email-card"
    >
      <div className="flex items-center gap-2">
        <span className="text-[0.6875rem] uppercase tracking-wide text-(--ui-text-tertiary)">
          {ambiguous ? 'Possible closing update' : 'Clear to Close?'}
        </span>
        <span className="text-xs text-(--ui-text-tertiary)">· {name}</span>
      </div>
      <p className="m-0 text-sm">
        {ambiguous
          ? 'Possible closing update — review email.'
          : `Lender email appears to confirm Clear to Close (matched: "${proposal.matched_phrase ?? 'clear to close'}").`}
      </p>
      <p className="m-0 text-xs text-(--ui-text-secondary)">
        Source: {proposal.sender ?? 'lender email'}
      </p>
      <div className="flex flex-wrap gap-2">
        {!ambiguous ? (
          <Button
            disabled={isBusy}
            onClick={() => ask('ctc-email-confirm',
                              `Confirm CTC · ${name}`,
                              confirmCtcPrompt(ws, proposal))}
            size="xs"
          >
            Confirm CTC
          </Button>
        ) : null}
        <Button
          disabled={isBusy}
          onClick={() => ask('ctc-email-review',
                            `Review email · ${name}`,
                            reviewEmailPrompt(ws, proposal))}
          size="xs"
          variant="secondary"
        >
          Review Email
        </Button>
        <Button
          disabled={isBusy}
          onClick={() => ask('ctc-email-dismiss',
                            `Dismiss CTC card · ${name}`,
                            dismissCtcPrompt(ws, proposal))}
          size="xs"
          variant="secondary"
        >
          Not Now
        </Button>
      </div>
    </div>
  )
}

function ConditionsSection({
  ws,
  isBusy,
  requestBorrower,
  requestLO,
  why
}: {
  ws: FileRecord
  isBusy: boolean
  requestBorrower: () => void
  requestLO: () => void
  why: (subject: string, kind: WhyKind) => void
}) {
  const groups = conditionsByOwner(ws)
  const waiting = (ws.conditions ?? []).filter(c => conditionStatus(c) === 'Waiting')
  const needsReview = (ws.conditions ?? []).filter(c => conditionStatus(c) === 'Needs Review')
  const openTotal = groups.reduce((n, g) => n + g.items.length, 0)

  return (
    <div className="m-0 mt-1 flex flex-col gap-2 text-sm" data-testid="conditions-section">
      {groups.length === 0 && waiting.length === 0 ? (
        <p className="m-0 text-xs text-(--ui-text-secondary)">No conditions logged.</p>
      ) : null}

      {groups.map(group => {
        const isBorrower = group.owner === 'Borrower'
        const isLO = group.owner === 'Loan Officer'

        const showConsolidated =
          (isBorrower || isLO) && groupedOwnerCount(ws, group.owner) >= 2 && !ownerHasWaiting(ws, group.owner)

        const buttonLabel =
          isBorrower
            ? `Request Borrower Items (${groupedOwnerCount(ws, 'Borrower')})`
            : isLO
              ? `Request LO Items (${groupedOwnerCount(ws, 'Loan Officer')})`
              : null

        return (
          <div
            className="rounded-md border border-(--ui-stroke-tertiary) p-2"
            data-testid={`conditions-group-${group.owner.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
            key={group.owner}
          >
            <div className="flex flex-wrap items-center gap-2">
              <Pill>{group.owner}</Pill>
              <span className="text-xs text-(--ui-text-tertiary)">
                {group.items.length} {group.items.length === 1 ? 'item' : 'items'}
              </span>
              {showConsolidated && buttonLabel ? (
                isBorrower ? (
                  <Button className="ml-auto" disabled={isBusy} onClick={requestBorrower} size="xs">
                    {buttonLabel}
                  </Button>
                ) : (
                  <Button className="ml-auto" disabled={isBusy} onClick={requestLO} size="xs">
                    {buttonLabel}
                  </Button>
                )
              ) : null}
            </div>
            <ul className="m-0 mt-1 flex list-none flex-col gap-1 p-0">
              {group.items.map((c, i) => {
                const status = conditionStatus(c)

                return (
                  <li className="flex flex-col gap-0.5" key={(c.id ?? c.text) + '-' + i}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span>{conditionItem(c)}</span>
                      <Pill tone={conditionStatusTone(status)}>{status}</Pill>
                      {c.needs_sage ? <Pill>Needs Sage</Pill> : null}
                      <WhyButton
                        busy={isBusy}
                        onClick={() => why(c.text ?? conditionItem(c), 'condition')}
                      />
                    </div>
                    {conditionPlainEnglish(c) !== conditionItem(c) ? (
                      <p className="m-0 pl-0 text-xs text-(--ui-text-secondary)">
                        {conditionPlainEnglish(c)}
                      </p>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          </div>
        )
      })}

      {waiting.length > 0 ? (
        <div className="flex flex-col gap-1 rounded-md border border-(--ui-stroke-tertiary) p-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs uppercase tracking-wide text-(--ui-text-tertiary)">Waiting</span>
          </div>
          <ul className="m-0 flex list-none flex-col gap-0.5 p-0">
            {waiting.map((c, i) => (
              <li className="text-xs text-(--ui-text-secondary)" key={(c.id ?? c.text) + '-w-' + i}>
                {waitingLabel(c.owner)} · {conditionItem(c)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {needsReview.length > 0 ? (
        <div className="flex flex-col gap-1 rounded-md border border-(--ui-stroke-tertiary) p-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs uppercase tracking-wide text-(--ui-text-tertiary)">Needs Review</span>
          </div>
          <ul className="m-0 flex list-none flex-col gap-1 p-0">
            {needsReview.map((c, i) => (
              <li className="text-xs text-(--ui-text-secondary)" key={(c.id ?? c.text) + '-r-' + i}>
                <span className="font-medium">{conditionItem(c)}</span>
                {c.needs_review_reason ? <> · {c.needs_review_reason}</> : null}
                <WhyButton
                  busy={isBusy}
                  onClick={() => why(c.text ?? conditionItem(c), 'condition')}
                />
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {openTotal + waiting.length === 0 ? (
        <p className="m-0 mt-1 text-xs text-(--ui-text-secondary)">
          Nothing open here. Flo will flag the next step.
        </p>
      ) : null}
    </div>
  )
}

function MissingRequestPanel({
  ws,
  draft,
  isBusy,
  loading,
  onSend,
  onEdit,
  onNotNow
}: {
  ws: FileRecord
  draft?: NonNullable<FileRecord['drafts']>[number]
  isBusy: boolean
  loading: boolean
  onSend: () => void
  onEdit: (body: string) => void
  onNotNow: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [body, setBody] = useState(draft?.body ?? '')

  useEffect(() => {
    if (!editing) {
      setBody(draft?.body ?? '')
    }
  }, [draft?.body, editing])

  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-(--ui-accent) bg-(--ui-bg-quaternary) p-3"
      data-testid="missing-request-panel"
    >
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold">Request Missing Documents</span>
        <span className="text-xs text-(--ui-text-tertiary)">Whisper draft</span>
      </div>
      {loading ? (
        <p className="m-0 text-sm text-(--ui-text-secondary)">Whisper is preparing one concise message…</p>
      ) : null}
      {!loading && draft ? (
        <>
          <textarea
            aria-label="Borrower message draft"
            className="min-h-28 rounded border border-(--ui-stroke-tertiary) bg-transparent px-2 py-1 text-sm"
            disabled={!editing || isBusy}
            onChange={e => setBody(e.target.value)}
            value={body}
          />
          <div className="flex flex-wrap gap-2">
            <Button disabled={isBusy} onClick={onSend} size="xs">
              Send
            </Button>
            <Button
              disabled={isBusy}
              onClick={() => (editing ? onEdit(body) : setEditing(true))}
              size="xs"
              variant="secondary"
            >
              {editing ? 'Save Edit' : 'Edit'}
            </Button>
            <Button disabled={isBusy} onClick={onNotNow} size="xs" variant="secondary">
              Not Now
            </Button>
          </div>
          <p className="m-0 text-[0.6875rem] text-(--ui-text-quaternary)">
            Nothing goes out until you approve the send.
          </p>
        </>
      ) : null}
    </div>
  )
}

function FilePanel({
  state,
  ws,
  onClose,
  reload
}: {
  state: TeamState
  ws: FileRecord
  onClose: () => void
  reload: () => void
}) {
  const { ask, background, busy } = useAsk(state)
  const summary = fileSummary(ws, state.approvals, state.tasks)

  const hints = teamHints(
    state.activity.filter(a => a.workspace_id === ws.workspace_id),
    state.workspaces,
    3
  )

  const hasTitle = (ws.orders ?? []).some(o => o.order_type === 'title' && o.state !== 'cancelled')
  const hasHoi = (ws.orders ?? []).some(o => o.order_type === 'hoi' && o.state !== 'cancelled')

  const ctcAll = ctcReadiness(ws)

  const isCtcConfirmed = (ws: FileRecord) =>
    ws.milestone === 'Clear to Close' && Boolean(ws.ctc_confirmed_at)

  const ctcCelebrate = (ws: FileRecord) => {
    const name = ws.display_name ?? ws.workspace_id ?? 'this file'

    return `${name} is CTC. Boom. 💚`
  }

  // Drag-and-drop loan documents onto the file view → attach to this loan.
  // The drop goes through the same uploadDocumentsPrompt the "Upload Missing
  // Doc" button uses, so the path / classification / dedupe behaviour is
  // identical to the file-picker flow.
  const [isDragOver, setIsDragOver] = useState(false)
  const dragDepth = useRef(0)

  const dropHandlers = useMemo(
    () => ({
      onDragEnter: (event: ReactDragEvent) => {
        // Only native file drags (not session drags) — match the chat's
        // `dragHasAttachments` heuristic by looking for the Files MIME.
        const types = Array.from(event.dataTransfer.types ?? [])

        if (!types.includes('Files')) {
          return
        }

        event.preventDefault()
        dragDepth.current += 1
        setIsDragOver(true)
      },
      onDragOver: (event: ReactDragEvent) => {
        const types = Array.from(event.dataTransfer.types ?? [])

        if (!types.includes('Files')) {
          return
        }

        event.preventDefault()
        event.dataTransfer.dropEffect = 'copy'
      },
      onDragLeave: () => {
        dragDepth.current = Math.max(0, dragDepth.current - 1)

        if (dragDepth.current === 0) {
          setIsDragOver(false)
        }
      },
      onDrop: (event: ReactDragEvent) => {
        const types = Array.from(event.dataTransfer.types ?? [])

        if (!types.includes('Files')) {
          return
        }

        event.preventDefault()
        dragDepth.current = 0
        setIsDragOver(false)
        const paths: string[] = []

        for (const item of Array.from(event.dataTransfer.items ?? [])) {
          if (item.kind !== 'file') {continue}
          const f = item.getAsFile()

          if (!f) {continue}
          // Electron exposes the absolute path via webUtils on the
          // preload bridge (window.hermesDesktop.getPathForFile). It is
          // not on the File object itself outside Electron; fall back to
          // the path the OS sometimes surfaces via webkitGetAsEntry.
          const win = typeof window !== 'undefined' ? window : undefined
          const path = (win as any)?.hermesDesktop?.getPathForFile?.(f) ?? ''

          if (path && /\.(pdf|jpe?g|png)$/i.test(path)) {
            paths.push(path)
          }
        }

        if (paths.length === 0) {
          return
        }

        ask('upload-doc', `Add documents · ${summary.name}`, uploadDocumentsPrompt(ws, paths))
      },
    }),
    [ask, summary.name, ws]
  )

  const drafts = (ws.drafts ?? []).filter(d => d.status === 'draft' || d.status === 'proposed')
  const isBusy = busy !== null
  const draft = missingDocumentDraft(ws)
  const requestedItems = requestedMissingItems(ws)
  const [requestPanel, setRequestPanel] = useState(false)
  const [requesting, setRequesting] = useState(false)

  useEffect(() => {
    if (requesting && draft) {
      setRequesting(false)
    }
  }, [draft, requesting])

  useEffect(() => {
    if (!requestPanel || draft || borrowerRequestWaiting(ws)) {
      return
    }

    const timer = window.setInterval(reload, 1500)

    return () => window.clearInterval(timer)
  }, [draft, requestPanel, reload, requesting, ws])

  const startMissingRequest = () => {
    setRequestPanel(true)

    if (!draft && !borrowerRequestWaiting(ws)) {
      setRequesting(true)
      background('request-missing', `Request items · ${summary.name}`, requestPrompt(ws))
    }
  }

  const why = (subject: string, kind: WhyKind) =>
    ask(`why:${subject}`, `Why? ${summary.name}`, whyPrompt(ws, subject, kind))

  return (
    <div
      className="relative flex flex-col gap-4 rounded-md border border-(--ui-stroke-tertiary) p-4"
      data-file-workspace={ws.workspace_id}
      data-testid="file-panel"
      {...dropHandlers}
    >
      {isDragOver ? (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-md border-2 border-dashed border-(--ui-accent) bg-(--ui-bg-quaternary) text-sm font-medium"
          data-testid="file-drop-overlay"
        >
          Drop documents to attach to {summary.name}
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="m-0 text-base font-semibold uppercase tracking-wide">{summary.name}</h2>
        {summary.readiness === 'New submission' ? <Pill tone="warn">NEW LOAN</Pill> : null}
        <Pill tone={STATUS_TONE[summary.status]}>{summary.status}</Pill>
        <Pill>{summary.milestone}</Pill>
        <button className="ml-auto text-xs text-(--ui-text-tertiary) hover:underline" onClick={onClose} type="button">
          Back to pipeline
        </button>
      </div>

      {ws.submission ? (
        <p className="m-0 text-xs text-(--ui-text-secondary)">
          Submitted by {ws.submission.loan_officer?.name ?? 'the loan officer'}
          {ws.submission.loan_officer?.company ? ` (${ws.submission.loan_officer.company})` : ''} from the website
          {ws.submission.expected_closing_date ? ` · expected close ${ws.submission.expected_closing_date}` : ''}
        </p>
      ) : null}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Fact label="Readiness" value={summary.readiness} />
        <Fact
          label="AUS"
          value={
            <span className="flex items-center gap-1">
              {summary.aus}
              {summary.aus !== 'Not checked yet' ? (
                <WhyButton busy={isBusy} label="What does this mean?" onClick={() => why(summary.aus, 'aus')} />
              ) : null}
            </span>
          }
        />
        <Fact label="Income" tone={summary.income === 'Needs work' ? 'warn' : undefined} value={summary.income} />
        <Fact label="Assets" tone={summary.assets === 'Needs work' ? 'warn' : undefined} value={summary.assets} />
        <Fact label="Orders" value={summary.orders} />
        <Fact label="Conditions" value={summary.conditions} />
        <Fact label="CTC" value={ctcAll.summary} />
      </div>

      {isCtcConfirmed(ws) ? (
        <div
          className="rounded-md border border-(--ui-accent) bg-(--ui-bg-quaternary) p-3"
          data-testid="ctc-confirmed-banner"
        >
          <p className="m-0 text-sm font-semibold">{ctcCelebrate(ws)}</p>
          <p className="m-0 mt-1 text-xs text-(--ui-text-secondary)">
            Next: prepare for closing.
          </p>
        </div>
      ) : (
        <div
          className="rounded-md border border-(--ui-stroke-tertiary) p-3 text-sm"
          data-testid="ctc-readiness"
        >
          <span className="text-[0.6875rem] uppercase tracking-wide text-(--ui-text-tertiary)">
            CTC readiness
          </span>
          <p className="m-0 mt-1 text-sm">{ctcAll.summary}</p>
          <ul className="m-0 mt-1 flex flex-wrap gap-2 p-0 text-xs">
            {ctcAll.open_count > 0 ? <li><Pill tone="warn">{ctcAll.open_count} open</Pill></li> : null}
            {ctcAll.waiting_count > 0 ? <li><Pill>{ctcAll.waiting_count} waiting</Pill></li> : null}
            {ctcAll.needs_review_count > 0 ? <li><Pill tone="bad">{ctcAll.needs_review_count} need review</Pill></li> : null}
            {ctcAll.cleared_count > 0 ? <li><Pill tone="good">{ctcAll.cleared_count} cleared</Pill></li> : null}
          </ul>
          {ctcAll.all_tracked ? (
            <p className="m-0 mt-2 text-xs text-(--ui-text-secondary)">
              Flo will mark Clear to Close once an actual lender / UW
              notice arrives and you confirm.
            </p>
          ) : null}
        </div>
      )}

      <div className="rounded-md bg-(--ui-bg-quaternary) p-3">
        <span className="text-[0.6875rem] uppercase tracking-wide text-(--ui-text-tertiary)">Best next move</span>
        <p className="m-0 text-sm">{summary.nextMove}</p>
        {summary.risk ? <p className="m-0 mt-1 text-sm text-destructive">Risk: {summary.risk}</p> : null}
      </div>

      <div className="flex flex-wrap gap-2">
        {summary.missing.length > 0 ? (
          <Button disabled={isBusy} onClick={startMissingRequest} size="sm">
            Request Missing Documents
          </Button>
        ) : null}
        {!hasTitle ? (
          <Button
            disabled={isBusy}
            onClick={() => ask('order-title', `Order title · ${summary.name}`, orderPrompt(ws, 'title'))}
            size="sm"
            variant="secondary"
          >
            Order Title
          </Button>
        ) : null}
        {!hasHoi ? (
          <Button
            disabled={isBusy}
            onClick={() => ask('order-hoi', `Order HOI · ${summary.name}`, orderPrompt(ws, 'hoi'))}
            size="sm"
            variant="secondary"
          >
            Order HOI
          </Button>
        ) : null}
        <Button
          disabled={isBusy}
          onClick={() => ask('ask-flo', `Ask Flo · ${summary.name}`, askFloPrompt(ws))}
          size="sm"
          variant="secondary"
        >
          Ask Flo
        </Button>
      </div>

      {requestPanel ? (
        <MissingRequestPanel
          draft={draft}
          isBusy={isBusy}
          loading={requesting || (!draft && !borrowerRequestWaiting(ws))}
          onEdit={body => {
            if (draft?.draft_id) {
              background(
                `edit-draft:${draft.draft_id}`,
                `Edit request · ${summary.name}`,
                editDraftPrompt(ws, draft.draft_id, body)
              )
            }

            setRequesting(true)
          }}
          onNotNow={() => setRequestPanel(false)}
          onSend={() => {
            if (draft?.draft_id) {
              background(
                `send-draft:${draft.draft_id}`,
                `Send request · ${summary.name}`,
                sendDraftPrompt(ws, draft.draft_id)
              )
            }
          }}
          ws={ws}
        />
      ) : null}

      {requestedItems.length > 0 ? (
        <div className="rounded-md border border-(--ui-stroke-tertiary) p-3" data-testid="borrower-requested">
          <span className="text-[0.6875rem] uppercase tracking-wide text-(--ui-text-tertiary)">
            Requested from borrower
          </span>
          <ul className="m-0 mt-1 list-disc pl-5 text-sm">
            {requestedItems.map(item => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className="m-0 mt-1 text-sm text-(--ui-text-secondary)">Status: Waiting</p>
        </div>
      ) : null}

      {hints.length > 0 ? (
        <ul className="m-0 flex list-none flex-col gap-0.5 p-0 text-xs text-(--ui-text-tertiary)">
          {hints.map(h => (
            <li key={h}>{h}</li>
          ))}
        </ul>
      ) : null}

      <DocumentsSection
        ask={ask}
        isBusy={isBusy}
        onRequest={startMissingRequest}
        why={item => why(item, 'missing')}
        ws={ws}
      />

      <details>
        <summary className="cursor-pointer text-sm">Income &amp; Assets</summary>
        <div className="mt-1 flex flex-col gap-1 text-sm">
          <span>
            Income: {summary.income} <WhyButton busy={isBusy} onClick={() => why('the income calculation', 'income')} />
          </span>
          <span>
            Assets: {summary.assets} <WhyButton busy={isBusy} onClick={() => why('the asset review', 'asset')} />
          </span>
          {(ws.readiness?.discrepancies ?? []).map(d => (
            <span className="text-destructive" key={d}>
              {d.replace(/^conflicting:\s*/i, '')} <WhyButton busy={isBusy} onClick={() => why(d, 'warning')} />
            </span>
          ))}
        </div>
      </details>

      <details open>
        <summary className="cursor-pointer text-sm">
          Conditions {summary.conditions !== 'None open' ? `· ${summary.conditions}` : ''}
        </summary>
        {pendingEmailConditions(ws) ? <EmailConditionsCard ask={ask} isBusy={isBusy} ws={ws} /> : null}
        {pendingCtcProposal(ws) ? <CtcEmailCard ask={ask} isBusy={isBusy} ws={ws} /> : null}
        {(ws.conditions ?? []).length === 0 ? (
          <p className="m-0 mt-1 text-xs text-(--ui-text-secondary)">No conditions logged.</p>
        ) : (
          <ConditionsSection
            isBusy={isBusy}
            requestBorrower={() => ask('borrower-request', `Borrower items · ${summary.name}`, borrowerRequestPrompt(ws))}
            requestLO={() => ask('lo-request', `Loan-officer items · ${summary.name}`, loRequestPrompt(ws))}
            why={why}
            ws={ws}
          />
        )}
      </details>

      <details>
        <summary className="cursor-pointer text-sm">Orders</summary>
        {(ws.orders ?? []).length === 0 ? (
          <p className="m-0 mt-1 text-xs text-(--ui-text-secondary)">Nothing ordered yet.</p>
        ) : (
          <ul className="m-0 mt-1 flex list-none flex-col gap-1 p-0 text-sm">
            {(ws.orders ?? []).map(o => (
              <li key={o.order_id ?? o.order_type}>
                {ORDER_TYPE_LABEL[o.order_type ?? 'custom'] ?? 'Order'}: {orderStateLabel(o.state).toLowerCase()}
                {o.vendor_or_destination && !o.vendor_or_destination.startsWith('SOURCE_GAP')
                  ? ` · ${o.vendor_or_destination}`
                  : ''}
              </li>
            ))}
          </ul>
        )}
      </details>

      <details open={drafts.length > 0}>
        <summary className="cursor-pointer text-sm">
          Communication {drafts.length > 0 ? `· ${drafts.length} ready for you` : ''}
        </summary>
        {drafts.length === 0 ? (
          <p className="m-0 mt-1 text-xs text-(--ui-text-secondary)">No drafts waiting.</p>
        ) : (
          <ul className="m-0 mt-1 flex list-none flex-col gap-2 p-0 text-sm">
            {drafts.map(d => (
              <li className="rounded-md border border-(--ui-stroke-tertiary) p-2" key={d.draft_id}>
                <div className="flex items-center gap-2">
                  <span className="font-medium capitalize">{d.audience ?? 'message'}</span>
                  <span className="text-(--ui-text-secondary)">{d.purpose}</span>
                  {d.urgency ? <Pill tone={d.urgency.startsWith('needs') ? 'warn' : 'muted'}>{d.urgency}</Pill> : null}
                </div>
                {d.body ? (
                  <p className="m-0 mt-1 whitespace-pre-wrap text-xs text-(--ui-text-secondary)">
                    {d.body.slice(0, 400)}
                  </p>
                ) : null}
                <div className="mt-2">
                  <Button
                    disabled={isBusy}
                    onClick={() =>
                      ask(
                        `draft:${d.draft_id}`,
                        `Review draft · ${summary.name}`,
                        reviewDraftPrompt(ws, d.draft_id ?? '')
                      )
                    }
                    size="xs"
                  >
                    Review &amp; Send
                  </Button>
                </div>
                <p className="m-0 mt-1 text-[0.6875rem] text-(--ui-text-quaternary)">
                  Whisper drafted this. Nothing goes out until you approve it.
                </p>
              </li>
            ))}
          </ul>
        )}
      </details>
    </div>
  )
}

export function PipelinePage() {
  const { state, reload } = useTeamState()
  const [selected, setSelected] = useFileParam()

  const rows = useMemo(
    () => (state ? state.workspaces.map(w => fileSummary(w as FileRecord, state.approvals, state.tasks)) : []),
    [state]
  )

  const ws = state?.workspaces.find(w => w.workspace_id === selected) as FileRecord | undefined

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-6 py-8">
      <header className="flex items-center gap-3">
        <h1 className="m-0 text-lg font-semibold tracking-wide">Pipeline</h1>
        <span className="text-xs text-(--ui-text-tertiary)">
          {rows.length} {rows.length === 1 ? 'file' : 'files'}
        </span>
      </header>
      {!state ? <Loader /> : null}
      {state && ws ? <FilePanel onClose={() => setSelected(null)} reload={reload} state={state} ws={ws} /> : null}
      {state && !ws ? (
        rows.length === 0 ? (
          <p className="m-0 text-sm text-(--ui-text-secondary)">
            No files yet. Tell Flo about one (“open a file for Johnson”) and it shows up here.
          </p>
        ) : (
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {rows.map(r => (
              <li key={r.workspaceId}>
                <button
                  className="flex w-full flex-col gap-1 rounded-md border border-(--ui-stroke-tertiary) p-3 text-left hover:bg-(--chrome-action-hover)"
                  onClick={() => setSelected(r.workspaceId)}
                  type="button"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{r.name}</span>
                    {r.readiness === 'New submission' ? <Pill tone="warn">NEW LOAN</Pill> : null}
                    <Pill tone={STATUS_TONE[r.status]}>{r.status}</Pill>
                    <span className="text-xs text-(--ui-text-secondary)">{r.milestone}</span>
                    <span className="text-xs text-(--ui-text-secondary)">· {r.readiness}</span>
                    {r.documents > 0 ? (
                      <span className="text-xs text-(--ui-text-secondary)">
                        · {r.documents} {r.documents === 1 ? 'document' : 'documents'}
                      </span>
                    ) : null}
                    {r.missing.length > 0 ? (
                      <span className="text-xs text-(--ui-text-secondary)">
                        · Missing: {r.missing.length} {r.missing.length === 1 ? 'item' : 'items'}
                      </span>
                    ) : null}
                  </div>
                  <span className="text-xs text-(--ui-text-secondary)">Next: {r.nextMove}</span>
                  <span className={cn('text-xs', r.risk ? 'text-destructive' : 'text-(--ui-text-tertiary)')}>
                    Risk: {r.risk ?? 'None'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )
      ) : null}
    </div>
  )
}
