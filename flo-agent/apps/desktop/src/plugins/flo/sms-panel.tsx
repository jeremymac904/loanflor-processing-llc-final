import { Button } from '@hermes/plugin-sdk'
import { useCallback, useEffect, useMemo, useState } from 'react'

import type { FileRecord } from './ashley'

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
const ROLES = [
  'Borrower',
  'Co-Borrower',
  'Loan Officer',
  'Processor',
  'Title Contact',
  'Insurance Contact',
  'Other',
  'Ashley'
]
const field = 'w-full rounded-md border border-(--ui-stroke-tertiary) bg-(--ui-bg-quaternary) px-3 py-2 text-sm'

function initialContacts(ws: FileRecord) {
  const rows: Array<{ displayName: string; role: string; mobile: string }> = []

  for (const borrower of ws.submission?.borrowers ?? []) {
    if (borrower.phone) {
      rows.push({
        displayName: borrower.name ?? 'Borrower',
        role: borrower.role === 'co_borrower' ? 'Co-Borrower' : 'Borrower',
        mobile: borrower.phone
      })
    }
  }

  const lo = ws.submission?.loan_officer

  if (lo?.phone) {
    rows.push({ displayName: lo.name ?? 'Loan Officer', role: 'Loan Officer', mobile: lo.phone })
  }

  return rows
}

export function SmsPanel({ ws, ask }: { ws: FileRecord; ask: (id: string, title: string, prompt: string) => void }) {
  const bridge = (window as any).hermesDesktop?.flo
  const [contacts, setContacts] = useState<Contact[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [recipientId, setRecipientId] = useState('')
  const [body, setBody] = useState('')
  const [draftContact, setDraftContact] = useState({ displayName: '', role: 'Borrower', mobile: '' })
  const [showAdd, setShowAdd] = useState(false)
  const [preview, setPreview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const fileName = ws.display_name ?? ws.workspace_id

  const refresh = useCallback(async () => {
    if (!bridge) {
      return
    }

    const [saved, history] = (await Promise.all([
      bridge.smsGetContacts(ws.workspace_id).catch(() => []),
      bridge.smsGetMessages(ws.workspace_id).catch(() => [])
    ])) as [Contact[], Message[]]

    let rows = Array.isArray(saved) ? saved : []

    if (!rows.length) {
      const seeded = initialContacts(ws)

      if (seeded.length) {
        const result = await bridge
          .smsSaveContacts({ workspaceId: ws.workspace_id, contacts: seeded })
          .catch(() => null)

        if (result?.ok) {
          rows = result.contacts
        }
      }
    }

    setContacts(rows)
    setMessages(Array.isArray(history) ? history : [])
    setRecipientId(current =>
      rows.some(row => row.contactId === current)
        ? current
        : (rows.find(row => row.smsConsent !== 'opted_out')?.contactId ?? '')
    )
  }, [bridge, ws])

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

  const saveContacts = async (rows: Array<Partial<Contact>>) => {
    const result = await bridge.smsSaveContacts({ workspaceId: ws.workspace_id, contacts: rows })

    if (!result?.ok) {
      throw new Error(result?.error ?? 'Contacts could not be saved.')
    }
    setContacts(result.contacts)

    return result.contacts as Contact[]
  }

  const addContact = async () => {
    setBusy(true)
    setError(null)
    setNotice(null)

    try {
      const rows = await saveContacts([...contacts, draftContact])
      setRecipientId(rows.at(-1)?.contactId ?? '')
      setDraftContact({ displayName: '', role: 'Borrower', mobile: '' })
      setShowAdd(false)
      setNotice('Contact saved. Confirm the person may be contacted by SMS before sending.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Contact could not be saved.')
    } finally {
      setBusy(false)
    }
  }

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
          <Button onClick={() => setShowAdd(value => !value)} size="xs" variant="secondary">
            {showAdd ? 'Cancel' : 'Add contact'}
          </Button>
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
        {showAdd ? (
          <div className="grid gap-2 rounded border border-(--ui-stroke-tertiary) p-3 sm:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs">
              <span>Name</span>
              <input
                className={field}
                onChange={event => setDraftContact(value => ({ ...value, displayName: event.target.value }))}
                value={draftContact.displayName}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs">
              <span>Role</span>
              <select
                className={field}
                onChange={event => setDraftContact(value => ({ ...value, role: event.target.value }))}
                value={draftContact.role}
              >
                {ROLES.map(role => (
                  <option key={role}>{role}</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs">
              <span>Mobile number</span>
              <input
                className={field}
                onChange={event => setDraftContact(value => ({ ...value, mobile: event.target.value }))}
                placeholder="+1 904 555 0100"
                value={draftContact.mobile}
              />
            </label>
            <p className="m-0 text-xs text-(--ui-text-secondary) sm:col-span-3">
              Use the complete mobile number. Flo does not guess from partial numbers.
            </p>
            <div className="sm:col-span-3">
              <Button
                disabled={busy || !draftContact.displayName.trim() || !draftContact.mobile.trim()}
                onClick={() => void addContact()}
                size="xs"
              >
                Save contact
              </Button>
            </div>
          </div>
        ) : null}
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
