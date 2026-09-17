/**
 * FloOnboarding — Ashley's first-launch flow.
 *
 * Replaces the default Hermes provider-onboarding experience with a Flo-
 * branded welcome screen and a small set of connector cards. Each
 * card has only three states:
 *
 *   Ready  — connector is wired and verified end-to-end
 *   Set up — connector is wired but Ashley hasn't done her part
 *   Off    — connector isn't wired; the card hides the status text
 *
 * Backend reachability is checked via the dedicated `hermes:flo:*` IPC
 * handlers (see apps/desktop/electron/main.ts). Secrets are stored
 * via Electron's safeStorage when available; never written to Git,
 * never written in plain text to a tracked file.
 *
 * No provider plumbing, no model IDs, no JSON — Ashley sees only the
 * verbs she needs: Connect / Set up / Continue.
 */

import { Button, cn, host, Loader } from '@hermes/plugin-sdk'
import { useCallback, useEffect, useState } from 'react'

import floBadge from './flo-badge.png'

export type ConnectionStatus = {
  gmail: { configured: boolean; identifier: string | null }
  drive: { configured: boolean }
  calendar: { configured: boolean }
  zapier: { configured: boolean }
  signing: { configured: boolean }
  localAi: { configured: boolean; models: string[] }
}

const INITIAL_STATUS: ConnectionStatus = {
  gmail:    { configured: false, identifier: null },
  drive:    { configured: false },
  calendar: { configured: false },
  zapier:   { configured: false },
  signing:  { configured: false },
  localAi:  { configured: false, models: [] }
}

export const FLO_ONBOARDING_ROUTE = '/flo/onboarding'

interface FloOnboardingProps {
  /** Storage primitive from `ctx.storage` — same one used for LANDED_KEY. */
  storage: { get<T>(key: string, fallback: T): T; set(key: string, value: unknown): void }
}

export function FloOnboarding({ storage }: FloOnboardingProps) {
  const [status, setStatus] = useState<ConnectionStatus>(INITIAL_STATUS)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [gmailDraft, setGmailDraft] = useState<{ email: string; password: string }>(
    () => ({ email: '', password: '' })
  )

  const [zapierUrl, setZapierUrl] = useState('')
  const [showGmail, setShowGmail] = useState(false)
  const [showZapier, setShowZapier] = useState(false)
  const [busySigning, setBusySigning] = useState(false)
  const [busyAi, setBusyAi] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const next = await (window as any).hermesDesktop.flo.connectionStatus()

      if (next && typeof next === 'object') {
        setStatus(next as ConnectionStatus)
      }
    } catch {
      // Status probe is best-effort; UI degrades to "off" cards.
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const saveGmail = useCallback(async () => {
    if (!gmailDraft.email.trim() || !gmailDraft.password.trim()) {
      setError('Email and password are both required.')

      return
    }

    setBusy('gmail')
    setError(null)

    try {
      const r = await (window as any).hermesDesktop.flo.saveGmail({
        account: 'gmail',
        identifier: gmailDraft.email.trim(),
        secret: gmailDraft.password
      })

      if (!r?.ok) {
        setError(r?.error ?? 'Could not save Gmail credentials.')

        return
      }

      setGmailDraft({ email: '', password: '' })
      setShowGmail(false)
      await refresh()
    } finally {
      setBusy(null)
    }
  }, [gmailDraft, refresh])

  const saveZapier = useCallback(async () => {
    if (!/^https?:\/\//.test(zapierUrl)) {
      setError('Zapier URL must start with http:// or https://.')

      return
    }

    setBusy('zapier')
    setError(null)

    try {
      const r = await (window as any).hermesDesktop.flo.saveZapier({ url: zapierUrl.trim() })

      if (!r?.ok) {
        setError(r?.error ?? 'Could not save Zapier URL.')

        return
      }

      setZapierUrl('')
      setShowZapier(false)
      await refresh()
    } finally {
      setBusy(null)
    }
  }, [zapierUrl, refresh])

  const startDocumenso = useCallback(async () => {
    setBusySigning(true)
    setError(null)

    try {
      const r = await (window as any).hermesDesktop.flo.startDocumenso()

      if (!r?.ok) {
        setError(r?.error ?? 'Flo Signatures launcher did not start.')

        return
      }

      // Wait briefly for containers to come up, then recheck.
      await new Promise(r => setTimeout(r, 4000))
      await refresh()
    } finally {
      setBusySigning(false)
    }
  }, [refresh])

  const refreshLocalAi = useCallback(async () => {
    setBusyAi(true)
    setError(null)

    try {
      await refresh()
    } finally {
      setBusyAi(false)
    }
  }, [refresh])

  const finish = useCallback(() => {
    storage.set('flo-onboarding-done', true)
    host.navigate('/flo')
  }, [storage])

  const allRequiredReady =
    status.gmail.configured &&
    status.drive.configured &&
    status.signing.configured

  return (
    <div className="mx-auto flex w-full max-w-xl flex-col gap-6 px-6 py-8" data-testid="flo-onboarding">
      <header className="flex items-center gap-4">
        <img alt="" aria-hidden className="size-16 shrink-0 select-none" draggable={false} src={floBadge} />
        <div className="flex flex-col gap-1">
          <h1 className="m-0 text-xl font-semibold">Welcome to Flo 💚</h1>
          <p className="m-0 text-sm text-(--ui-text-secondary)">Let&rsquo;s get you ready.</p>
        </div>
      </header>

      {error ? (
        <div className="rounded-md border border-destructive p-3 text-sm text-destructive" role="alert">
          {error}
        </div>
      ) : null}

      <section className="flex flex-col gap-3">
        <ConnectCard
          actionLabel={showGmail ? 'Cancel' : status.gmail.configured ? 'Update' : 'Connect Gmail'}
          busy={busy === 'gmail'}
          description="Read lender / UW emails so Flo can pull conditions into the right file."
          onAction={() => setShowGmail(v => !v)}
          ready={status.gmail.configured}
          readyLabel={status.gmail.identifier ? `Connected · ${maskEmail(status.gmail.identifier)}` : 'Connected'}
          title="Gmail"
        >
          {showGmail ? (
            <div className="flex flex-col gap-2 rounded-md border border-(--ui-stroke-tertiary) p-3">
              <label className="flex flex-col gap-1 text-xs">
                <span className="font-medium">Gmail address</span>
                <input
                  className="rounded border border-(--ui-stroke-tertiary) bg-(--ui-bg-quaternary) px-2 py-1 text-sm"
                  data-testid="gmail-email-input"
                  onChange={e => setGmailDraft(s => ({ ...s, email: e.target.value }))}
                  placeholder="ashley@loanflowprocessing.com"
                  type="email"
                  value={gmailDraft.email}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs">
                <span className="font-medium">App password</span>
                <input
                  className="rounded border border-(--ui-stroke-tertiary) bg-(--ui-bg-quaternary) px-2 py-1 text-sm"
                  data-testid="gmail-password-input"
                  onChange={e => setGmailDraft(s => ({ ...s, password: e.target.value }))}
                  placeholder="abcd efgh ijkl mnop"
                  type="password"
                  value={gmailDraft.password}
                />
                <span className="text-[0.6875rem] text-(--ui-text-tertiary)">
                  Generate at myaccount.google.com/apppasswords &middot; stored encrypted via Electron safeStorage.
                </span>
              </label>
              <div className="flex justify-end gap-2">
                <Button disabled={busy === 'gmail'} onClick={saveGmail} size="xs">Save</Button>
              </div>
            </div>
          ) : null}
        </ConnectCard>

        <ConnectCard
          actionLabel="Connect Google Drive"
          description="Flo uses these when a file or event explicitly needs them. Sign in once; Flo asks before using them."
          onAction={async () => {
            // The existing google-workspace skill runs the OAuth dance from
            // the terminal. Ashley's path: open the skill's setup page,
            // click through, then come back. We surface a copyable URL.
            try {
              await navigator.clipboard.writeText(
                'https://hermes-agent.nousresearch.com/docs/'
              )
            } catch {
              // ignore
            }

            setError('Copied docs link. Open it, run setup.py, then return here — Flo detects the connection.')
          }}
          ready={status.drive.configured && status.calendar.configured}
          readyLabel={status.drive.configured ? 'Connected' : 'Not signed in'}
          title="Google Drive & Calendar"
          busy={false}
        />

        <ConnectCard
          actionLabel={showZapier ? 'Cancel' : status.zapier.configured ? 'Update' : 'Connect Zapier'}
          busy={busy === 'zapier'}
          description="Flo uses Zapier MCP to reach any web app with no special integration."
          onAction={() => setShowZapier(v => !v)}
          ready={status.zapier.configured}
          readyLabel={status.zapier.configured ? 'Connected' : 'Not connected'}
          title="Zapier"
        >
          {showZapier ? (
            <div className="flex flex-col gap-2 rounded-md border border-(--ui-stroke-tertiary) p-3">
              <label className="flex flex-col gap-1 text-xs">
                <span className="font-medium">Zapier MCP URL</span>
                <input
                  className="rounded border border-(--ui-stroke-tertiary) bg-(--ui-bg-quaternary) px-2 py-1 text-sm"
                  data-testid="zapier-url-input"
                  onChange={e => setZapierUrl(e.target.value)}
                  placeholder="https://nla.zapier.com/…"
                  type="url"
                  value={zapierUrl}
                />
              </label>
              <div className="flex justify-end gap-2">
                <Button disabled={busy === 'zapier'} onClick={saveZapier} size="xs">Save</Button>
              </div>
            </div>
          ) : null}
        </ConnectCard>

        <ConnectCard
          actionLabel={status.signing.configured ? 'Re-check' : 'Set Up Local Signing'}
          busy={busySigning}
          description="Flo signs lender / borrower docs through local Documenso. No data leaves this machine."
          onAction={status.signing.configured ? refresh : startDocumenso}
          ready={status.signing.configured}
          readyLabel={status.signing.configured ? 'Ready' : 'Not running'}
          title="Local Signing"
        />

        <ConnectCard
          actionLabel={status.localAi.configured ? 'Re-check' : 'Set Up Local AI'}
          busy={busyAi}
          description="Flo's reasoning runs on a local model. No data leaves this machine."
          onAction={refreshLocalAi}
          ready={status.localAi.configured}
          readyLabel={
            status.localAi.configured
              ? status.localAi.models.length > 0
                ? `Ready · ${status.localAi.models.length} model${status.localAi.models.length === 1 ? '' : 's'}`
                : 'Ready'
              : 'Not running'
          }
          title="Local AI"
        />
      </section>

      <div className="flex flex-col gap-2 border-t border-(--ui-stroke-tertiary) pt-4">
        <Button disabled={busy !== null} onClick={finish} size="lg">
          Continue
        </Button>
        <p className="m-0 text-xs text-(--ui-text-tertiary)">
          {allRequiredReady
            ? 'All required connectors are ready. You can revisit these later from Settings.'
            : 'Gmail and Local Signing are required. You can finish the rest any time from Settings.'}
        </p>
      </div>
    </div>
  )
}

interface ConnectCardProps {
  title: string
  description: string
  ready: boolean
  readyLabel: string
  actionLabel: string
  onAction: () => void
  busy: boolean
  children?: React.ReactNode
}

function ConnectCard({
  title,
  description,
  ready,
  readyLabel,
  actionLabel,
  onAction,
  busy,
  children
}: ConnectCardProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-2 rounded-md border p-3',
        ready
          ? 'border-(--ui-accent) bg-(--ui-bg-quaternary)'
          : 'border-(--ui-stroke-tertiary)'
      )}
      data-testid={`connect-card-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-col">
          <span className="text-sm font-semibold">{title}</span>
          <span className="text-xs text-(--ui-text-tertiary)">{description}</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'text-xs font-medium',
              ready ? 'text-(--ui-accent)' : 'text-(--ui-text-tertiary)'
            )}
            data-status={ready ? 'ready' : 'off'}
          >
            {readyLabel}
          </span>
          <Button
            data-testid={`connect-action-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
            disabled={busy}
            onClick={onAction}
            size="xs"
            variant={ready ? 'secondary' : 'default'}
          >
            {busy ? <Loader /> : actionLabel}
          </Button>
        </div>
      </div>
      {children}
    </div>
  )
}

function maskEmail(email: string): string {
  const [local, domain] = email.split('@')

  if (!domain) {return email}
  const visible = local.slice(0, 2)

  return `${visible}${'•'.repeat(Math.max(local.length - 2, 1))}@${domain}`
}
