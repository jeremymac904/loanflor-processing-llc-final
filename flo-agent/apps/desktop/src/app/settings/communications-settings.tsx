import { Button } from '@hermes/plugin-sdk'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { useTeamState } from '../../plugins/flo/state'

type TwilioStatus = {
  state: 'not_connected' | 'connected' | 'needs_attention'
  sendingNumber: string
  accountSid: string | null
  apiKeySid: string | null
  lastSyncAt: string | null
  lastSyncError: string | null
  ashleyMobile?: string | null
}

type SmsMessage = {
  sid: string
  workspaceId: string | null
  contactId: string | null
  from: string
  body: string
  timestamp: string
  media?: Array<{ sid: string; contentType: string | null }>
  candidates?: Array<{ workspaceId: string; contactId: string; displayName: string }>
  matchStatus?: string
}

type SmsContact = { contactId: string; displayName: string; role: string; mobile: string }

const EMPTY_STATUS: TwilioStatus = {
  state: 'not_connected',
  sendingNumber: '+19046829414',
  accountSid: null,
  apiKeySid: null,
  lastSyncAt: null,
  lastSyncError: null,
  ashleyMobile: null
}

const fieldClass = 'w-full rounded-md border border-(--ui-stroke-tertiary) bg-(--ui-bg-quaternary) px-3 py-2 text-sm'

export function CommunicationsSettings() {
  const bridge = (window as any).hermesDesktop?.flo
  const { state } = useTeamState(60_000)
  const [status, setStatus] = useState<TwilioStatus>(EMPTY_STATUS)
  const [accountSid, setAccountSid] = useState('')
  const [apiKeySid, setApiKeySid] = useState('')
  const [apiKeySecret, setApiKeySecret] = useState('')
  const [ashleyMobile, setAshleyMobile] = useState('')
  const [unmatched, setUnmatched] = useState<SmsMessage[]>([])
  const [contactMap, setContactMap] = useState<Record<string, SmsContact[]>>({})
  const [assignment, setAssignment] = useState<Record<string, { workspaceId: string; contactId: string }>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!bridge) {
      return
    }

    const [nextStatus, rows] = await Promise.all([
      bridge.smsStatus().catch(() => EMPTY_STATUS),
      bridge.smsGetUnmatched().catch(() => [])
    ])

    setStatus({ ...EMPTY_STATUS, ...nextStatus })
    setAshleyMobile(nextStatus?.ashleyMobile ?? '')
    setUnmatched(Array.isArray(rows) ? rows : [])
  }, [bridge])

  useEffect(() => {
    void refresh()
  }, [refresh])
  useEffect(() => {
    const timer = window.setInterval(() => {
      void refresh()
    }, 30_000)

    return () => window.clearInterval(timer)
  }, [refresh])

  const files = state?.workspaces ?? []
  useEffect(() => {
    if (!bridge || files.length === 0) {
      return
    }
    let cancelled = false
    void Promise.all(
      files.map(
        async file => [file.workspace_id, await bridge.smsGetContacts(file.workspace_id).catch(() => [])] as const
      )
    ).then(rows => {
      if (!cancelled) {
        setContactMap(Object.fromEntries(rows))
      }
    })

    return () => {
      cancelled = true
    }
  }, [bridge, files])

  const fileNames = useMemo(
    () => new Map(files.map(file => [file.workspace_id, file.display_name ?? file.workspace_id])),
    [files]
  )

  const saveCredentials = async () => {
    setBusy(true)
    setError(null)
    setNotice(null)

    try {
      const result = await bridge.smsSaveCredentials({
        accountSid: accountSid.trim(),
        apiKeySid: apiKeySid.trim(),
        apiKeySecret
      })
      setApiKeySecret('')

      if (!result?.ok) {
        setError(result?.error ?? 'Twilio could not verify these credentials.')
      } else {
        setNotice('Twilio is connected. The API Key Secret was encrypted on this PC.')
      }

      await refresh()
    } catch {
      setError(
        'Twilio could not be reached. Your encrypted credentials are saved; check your connection and try again.'
      )
      await refresh()
    } finally {
      setBusy(false)
    }
  }

  const saveAshleyMobile = async () => {
    setBusy(true)
    setError(null)
    setNotice(null)

    try {
      const result = await bridge.smsSaveAshleyMobile(ashleyMobile)

      if (!result?.ok) {
        setError(result?.error ?? 'Ashley’s mobile number was not saved.')
      } else {
        setNotice('Ashley’s mobile number was saved on this PC.')
      }

      await refresh()
    } catch {
      setError('Ashley’s mobile number could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  const assign = async (message: SmsMessage) => {
    const selected = assignment[message.sid]

    if (!selected?.workspaceId || !selected.contactId) {
      return
    }
    setError(null)
    const result = await bridge.smsAssignMessage({ sid: message.sid, ...selected })

    if (!result?.ok) {
      setError(result?.error ?? 'This message could not be assigned.')

      return
    }

    setAssignment(rows => {
      const copy = { ...rows }
      delete copy[message.sid]

      return copy
    })
    await refresh()
  }

  const statusLabel =
    status.state === 'connected'
      ? 'Connected'
      : status.state === 'needs_attention'
        ? 'Needs Attention'
        : 'Not Connected'

  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto">
      <header className="border-b border-(--ui-stroke-tertiary) px-6 py-5">
        <h1 className="m-0 text-lg font-semibold">Text Messaging</h1>
        <p className="mb-0 mt-1 text-sm text-(--ui-text-secondary)">
          Manage Flo’s Twilio connection and review messages that need a file match.
        </p>
      </header>

      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-6">
        {error ? (
          <div className="rounded-md border border-destructive p-3 text-sm text-destructive" role="alert">
            {error}
          </div>
        ) : null}
        {notice ? (
          <div className="rounded-md border border-(--ui-stroke-tertiary) p-3 text-sm" role="status">
            {notice}
          </div>
        ) : null}

        <section className="flex flex-col gap-3 rounded-lg border border-(--ui-stroke-tertiary) p-4">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="m-0 text-base font-semibold">Twilio</h2>
            <span
              className={`rounded-full px-2.5 py-1 text-xs ${status.state === 'connected' ? 'bg-(--ui-bg-success) text-(--ui-text-success)' : status.state === 'needs_attention' ? 'bg-(--ui-bg-warning) text-(--ui-text-warning)' : 'bg-(--ui-bg-quaternary) text-(--ui-text-secondary)'}`}
            >
              {statusLabel}
            </span>
            <span className="ml-auto text-xs text-(--ui-text-secondary)">Flo number · {status.sendingNumber}</span>
          </div>
          <p className="m-0 text-sm text-(--ui-text-secondary)">
            Flo sends through Twilio’s REST API and checks message history locally. ARIVE’s incoming-message webhook
            remains the owner of Twilio webhooks.
          </p>
          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium">Account SID</span>
            <input
              autoComplete="off"
              className={fieldClass}
              onChange={event => setAccountSid(event.target.value)}
              placeholder={status.accountSid ?? 'AC…'}
              value={accountSid}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium">API Key SID</span>
            <input
              autoComplete="off"
              className={fieldClass}
              onChange={event => setApiKeySid(event.target.value)}
              placeholder={status.apiKeySid ?? 'SK…'}
              value={apiKeySid}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium">API Key Secret</span>
            <input
              autoComplete="new-password"
              className={fieldClass}
              onChange={event => setApiKeySecret(event.target.value)}
              type="password"
              value={apiKeySecret}
            />
            <span className="text-(--ui-text-tertiary)">
              Encrypted by Windows secure storage on this PC. Flo never displays it after saving.
            </span>
          </label>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              disabled={busy || !accountSid.trim() || !apiKeySid.trim() || !apiKeySecret}
              onClick={() => void saveCredentials()}
              size="sm"
            >
              {busy ? 'Connecting…' : 'Connect Twilio'}
            </Button>
            {status.lastSyncAt ? (
              <span className="text-xs text-(--ui-text-tertiary)">
                Last checked {new Date(status.lastSyncAt).toLocaleString()}
              </span>
            ) : null}
          </div>
          <div className="rounded-md bg-(--ui-bg-quaternary) p-3 text-xs text-(--ui-text-secondary)">
            Twilio currently shows US A2P 10DLC registration as required for this number. US outbound texting may be
            restricted until the number is registered. Flo will display Twilio’s actual result; this setting does not
            change A2P registration.
          </div>
          {status.lastSyncError ? (
            <p className="m-0 text-xs text-(--ui-text-warning)">Message sync needs attention: {status.lastSyncError}</p>
          ) : null}
        </section>

        <section className="flex flex-col gap-3 rounded-lg border border-(--ui-stroke-tertiary) p-4">
          <h2 className="m-0 text-base font-semibold">Ashley</h2>
          <p className="m-0 text-sm text-(--ui-text-secondary)">
            Save Ashley’s mobile number here if Flo should offer it as a message recipient.
          </p>
          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium">Mobile number</span>
            <input
              autoComplete="off"
              className={fieldClass}
              onChange={event => setAshleyMobile(event.target.value)}
              placeholder="+1 904 555 0100"
              value={ashleyMobile}
            />
          </label>
          <div>
            <Button disabled={busy} onClick={() => void saveAshleyMobile()} size="sm" variant="secondary">
              Save Ashley’s number
            </Button>
          </div>
        </section>

        <section className="flex flex-col gap-3 rounded-lg border border-(--ui-stroke-tertiary) p-4">
          <div className="flex items-center gap-2">
            <h2 className="m-0 text-base font-semibold">Needs Review</h2>
            <span className="text-xs text-(--ui-text-tertiary)">{unmatched.length}</span>
            <Button
              className="ml-auto"
              disabled={busy || status.state !== 'connected'}
              onClick={async () => {
                setBusy(true)
                await bridge.smsSync()
                await refresh()
                setBusy(false)
              }}
              size="xs"
              variant="secondary"
            >
              Sync now
            </Button>
          </div>
          <p className="m-0 text-sm text-(--ui-text-secondary)">
            Incoming messages attach automatically only when one contact in one file matches the number. Ambiguous texts
            stay here until you assign them.
          </p>
          {unmatched.length === 0 ? (
            <p className="m-0 text-sm text-(--ui-text-tertiary)">No messages need review.</p>
          ) : null}
          {unmatched.map(message => {
            const selected = assignment[message.sid] ?? { workspaceId: '', contactId: '' }
            const contacts = contactMap[selected.workspaceId] ?? []

            return (
              <article
                className="flex flex-col gap-2 rounded-md border border-(--ui-stroke-tertiary) p-3"
                key={message.sid}
              >
                <div className="flex flex-wrap items-center gap-2 text-xs text-(--ui-text-secondary)">
                  <span>{message.from}</span>
                  <span>{new Date(message.timestamp).toLocaleString()}</span>
                  {message.matchStatus === 'needs_review' ? (
                    <span>Possible matches: {(message.candidates ?? []).map(item => item.displayName).join(', ')}</span>
                  ) : null}
                </div>
                <p className="m-0 whitespace-pre-wrap text-sm">{message.body || 'Attachment received'}</p>
                {message.media?.length ? (
                  <p className="m-0 text-xs text-(--ui-text-secondary)">
                    Attachment received · {message.media.length} media item(s). Flo has not opened or analyzed it.
                  </p>
                ) : null}
                <div className="grid gap-2 sm:grid-cols-2">
                  <select
                    aria-label="Assign to Customer File"
                    className={fieldClass}
                    onChange={event =>
                      setAssignment(rows => ({
                        ...rows,
                        [message.sid]: { workspaceId: event.target.value, contactId: '' }
                      }))
                    }
                    value={selected.workspaceId}
                  >
                    <option value="">Choose a Customer File…</option>
                    {files.map(file => (
                      <option key={file.workspace_id} value={file.workspace_id}>
                        {fileNames.get(file.workspace_id)}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="Match contact"
                    className={fieldClass}
                    disabled={!selected.workspaceId}
                    onChange={event =>
                      setAssignment(rows => ({
                        ...rows,
                        [message.sid]: { ...selected, contactId: event.target.value }
                      }))
                    }
                    value={selected.contactId}
                  >
                    <option value="">Choose the matching contact…</option>
                    {contacts
                      .filter(contact => contact.mobile.replace(/[\s().-]/g, '') === message.from)
                      .map(contact => (
                        <option key={contact.contactId} value={contact.contactId}>
                          {contact.displayName} · {contact.role}
                        </option>
                      ))}
                  </select>
                </div>
                <div>
                  <Button
                    disabled={!selected.workspaceId || !selected.contactId}
                    onClick={() => void assign(message)}
                    size="xs"
                  >
                    Assign message
                  </Button>
                </div>
              </article>
            )
          })}
        </section>
      </div>
    </div>
  )
}
