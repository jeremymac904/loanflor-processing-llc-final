import { Button } from '@hermes/plugin-sdk'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { runFloAction } from './actions-api'
import type { FileRecord } from './ashley'
import type { CustomerFileContact } from './data'

type Contact = {
  contactId: string
  displayName: string
  role: string
  mobile: string
  communicationStatus: string
  smsConsent: string
}
type Message = {
  sid: string
  contactId: string | null
  direction: string
  timestamp: string
  body: string
  status: string
  approvedBy?: string
  media?: Array<{ sid: string }>
}
const field = 'w-full rounded-md border border-(--ui-stroke-tertiary) bg-(--ui-bg-quaternary) px-3 py-2 text-sm'

const ROLE_LABELS: Record<string, string> = {
  borrower: 'Borrower', co_borrower: 'Co-Borrower', loan_officer: 'Loan Officer',
  lender: 'Lender', lender_ae: 'Lender Account Executive / AE', buyers_agent: "Buyer's Agent / Realtor",
  listing_agent: 'Listing Agent / Realtor', title_closing_agent: 'Title / Closing Agent',
  insurance_agent: 'HOI / Insurance Agent', employer_voe: 'Employer / VOE Contact',
  appraiser_amc: 'Appraiser / AMC', other: 'Other'
}

export function SmsPanel({ ws, ask }: { ws: FileRecord; ask: (id: string, title: string, prompt: string) => void }) {
  const bridge = (window as any).hermesDesktop?.flo
  const [contacts, setContacts] = useState<Contact[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [recipientId, setRecipientId] = useState('')
  const [body, setBody] = useState('')
  const [preview, setPreview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const fileName = ws.display_name ?? ws.workspace_id

  const refresh = useCallback(async () => {
    if (!bridge) {
      return
    }

    const [history, workspaceContacts] = (await Promise.all([
      bridge.smsGetMessages(ws.workspace_id).catch(() => []),
      runFloAction<{ action: string; message: string; contacts: CustomerFileContact[] }>('contacts-get', { workspace_id: ws.workspace_id })
        .then(result => ({ ...result, available: true }))
        .catch(() => ({ contacts: ws.contacts ?? [], available: true }))
    ])) as [Message[], { contacts: CustomerFileContact[]; available: boolean }]

    // The workspace roster is authoritative. Twilio's local file stores only
    // message history and SMS-consent state; this projection carries stable
    // Customer File IDs into that existing delivery/consent implementation.
    const roster = Array.isArray(workspaceContacts.contacts) ? workspaceContacts.contacts : []

    const projected = roster.flatMap(contact => {
      const mobile = String(contact.mobile || contact.phone || '').trim()

      if (!mobile) {return []}
      const label = ROLE_LABELS[contact.role] ?? 'Other'

      return [{
        contactId: contact.contact_id,
        displayName: contact.name || contact.custom_role || label,
        role: label,
        mobile,
      }]
    })

    let rows: Contact[] = []

    if (workspaceContacts.available) {
      const result = await bridge.smsSaveContacts({ workspaceId: ws.workspace_id, contacts: projected }).catch(() => null)
      rows = result?.ok ? result.contacts : []
    }

    setContacts(rows)
    setMessages(Array.isArray(history) ? history : [])
    setRecipientId(current =>
      rows.some(row => row.contactId === current)
        ? current
        : (rows.find(row => row.smsConsent !== 'opted_out')?.contactId ?? '')
    )
  }, [bridge, ws.contacts, ws.workspace_id])

  useEffect(() => {
    void refresh()
  }, [refresh])
  useEffect(() => {
    const timer = window.setInterval(() => {
      void refresh()
    }, 30_000)

    return () => window.clearInterval(timer)
  }, [refresh])

  const recipient = useMemo(() => contacts.find(row => row.contactId === recipientId) ?? null, [contacts, recipientId])
  const conversation = useMemo(() => messages.filter(row => row.contactId === recipientId), [messages, recipientId])

  const send = async () => {
    if (!recipient) {
      return
    }

    setBusy(true)
    setError(null)
    setNotice(null)

    try {
      const result = await bridge.smsSend({
        workspaceId: ws.workspace_id,
        contactId: recipient.contactId,
        to: recipient.mobile,
        body
      })

      if (result?.error) {
        setError(result.error)
      } else {
        setBody('')
        setPreview(false)
        setNotice('Twilio accepted the message. Delivery will update from Twilio’s actual message status.')
        await refresh()
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Twilio could not send the message.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <details className="rounded-md border border-(--ui-stroke-tertiary) p-3" open={conversation.length > 0}>
      <summary className="cursor-pointer text-sm font-medium">
        Text Messages{conversation.length ? ` · ${conversation.length}` : ''}
      </summary>
      <div className="mt-3 flex flex-col gap-3">
        {!contacts.length ? <p className="m-0 text-xs text-(--ui-text-secondary)">No Customer File contacts with a phone number are set. Add or update them in the Contacts section above.</p> : null}
        {error ? (
          <p className="m-0 rounded border border-destructive p-2 text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p className="m-0 rounded border border-(--ui-stroke-tertiary) p-2 text-sm" role="status">
            {notice}
          </p>
        ) : null}
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex min-w-60 flex-1 flex-col gap-1 text-xs">
            <span>Recipient in {fileName}</span>
            <select
              className={field}
              onChange={event => {
                setRecipientId(event.target.value)
                setPreview(false)
              }}
              value={recipientId}
            >
              <option value="">Choose a contact…</option>
              {contacts.map(row => (
                <option disabled={row.smsConsent === 'opted_out'} key={row.contactId} value={row.contactId}>
                  {row.displayName} · {row.role} · {row.mobile}
                  {row.smsConsent === 'opted_out' ? ' · SMS Opted Out' : ''}
                </option>
              ))}
            </select>
          </label>
          <Button
            disabled={busy}
            onClick={async () => {
              setBusy(true)
              await bridge.smsSync().catch(() => undefined)
              await refresh()
              setBusy(false)
            }}
            size="xs"
            variant="secondary"
          >
            Sync messages
          </Button>
        </div>
        {contacts.map(row => (
          <div className="flex flex-wrap items-center gap-2 text-xs" key={row.contactId}>
            <span>
              {row.displayName} · {row.role} · {row.mobile}
            </span>
            <span
              className={row.smsConsent === 'opted_out' ? 'font-medium text-destructive' : 'text-(--ui-text-tertiary)'}
            >
              {row.smsConsent === 'opted_out'
                ? 'SMS Opted Out'
                : row.smsConsent === 'opted_in'
                  ? 'SMS allowed by START reply'
                  : 'SMS consent unknown'}
            </span>
          </div>
        ))}
        {conversation.length ? (
          <ol
            aria-label="Text message conversation"
            className="m-0 flex max-h-80 list-none flex-col gap-2 overflow-y-auto p-0"
          >
            {conversation.map(message => (
              <li
                className={`max-w-[90%] rounded-lg border border-(--ui-stroke-tertiary) p-3 ${message.direction === 'outbound' ? 'self-end' : 'self-start'}`}
                key={message.sid}
              >
                <div className="flex flex-wrap gap-x-2 text-[0.6875rem] text-(--ui-text-tertiary)">
                  <span>
                    {message.direction === 'outbound'
                      ? 'Flo · outgoing'
                      : (contacts.find(row => row.contactId === message.contactId)?.displayName ?? 'Incoming text')}
                  </span>
                  <span>{new Date(message.timestamp).toLocaleString()}</span>
                  <span className="capitalize">{message.status}</span>
                  <span>Twilio</span>
                  {message.approvedBy ? <span>Approved by {message.approvedBy}</span> : null}
                </div>
                <p className="mb-0 mt-1 whitespace-pre-wrap text-sm">{message.body || 'Attachment received'}</p>
                {message.media?.length ? (
                  <p className="mb-0 mt-1 text-xs text-(--ui-text-secondary)">
                    Attachment received · {message.media.length} media item(s). Flo has not opened or analyzed it.
                  </p>
                ) : null}
              </li>
            ))}
          </ol>
        ) : (
          <p className="m-0 text-xs text-(--ui-text-tertiary)">No text messages for this contact yet.</p>
        )}
        {recipient ? (
          <div className="flex flex-col gap-2 border-t border-(--ui-stroke-tertiary) pt-3">
            <p className="m-0 text-xs text-(--ui-text-secondary)">
              To: {recipient.displayName} · {recipient.role} · {recipient.mobile}
            </p>
            {recipient.smsConsent === 'unknown' ? (
              <p className="m-0 text-xs text-(--ui-text-warning)">
                Consent status is unknown. Confirm SMS permission before sending.
              </p>
            ) : null}
            {preview ? (
              <div className="rounded-md border border-(--ui-stroke-tertiary) p-3">
                <p className="m-0 text-xs font-medium">Review before sending</p>
                <p className="m-0 mt-2 whitespace-pre-wrap text-sm">{body}</p>
                <div className="mt-3 flex gap-2">
                  <Button disabled={busy || recipient.smsConsent === 'opted_out'} onClick={() => void send()} size="xs">
                    Send
                  </Button>
                  <Button disabled={busy} onClick={() => setPreview(false)} size="xs" variant="secondary">
                    Edit
                  </Button>
                  <Button
                    disabled={busy}
                    onClick={() => {
                      setPreview(false)
                      setBody('')
                    }}
                    size="xs"
                    variant="secondary"
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <>
                <textarea
                  className={`${field} min-h-20 resize-y`}
                  disabled={recipient.smsConsent === 'opted_out'}
                  maxLength={1600}
                  onChange={event => setBody(event.target.value)}
                  placeholder="Write a concise, professional text…"
                  value={body}
                />
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    disabled={busy || recipient.smsConsent === 'opted_out' || !body.trim()}
                    onClick={() => setPreview(true)}
                    size="xs"
                  >
                    Review draft
                  </Button>
                  <Button
                    disabled={busy}
                    onClick={() =>
                      ask(
                        `sms-draft:${ws.workspace_id}`,
                        `Draft text · ${fileName}`,
                        `Draft a concise, professional SMS using only confirmed facts in the current Customer File. Do not send it.\nFile: ${fileName} (${ws.workspace_id})\nRecipient: ${recipient.displayName}, ${recipient.role}\nPurpose: ${body.trim() || 'Ask Ashley what to say.'}\nIf a needed fact is absent, ask Ashley rather than inventing it.`
                      )
                    }
                    size="xs"
                    variant="secondary"
                  >
                    Ask Flo to draft
                  </Button>
                  <span className="ml-auto text-xs text-(--ui-text-tertiary)">{body.length}/1600</span>
                </div>
              </>
            )}
          </div>
        ) : null}
      </div>
    </details>
  )
}
