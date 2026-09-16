/**
 * Approvals — one queue. Each card: what will happen, who it goes to, what
 * Flo is proposing, a text preview, and Approve / Edit / Not Now. Hashes,
 * tool names, policy engines and JSON stay on the Advanced page.
 *
 * Approve opens the bot's chat where Hermes' native one-click confirmation is
 * waiting (the approval binds to that exact payload — no new IPC is needed).
 */

import { Button, formatAgo, host, Loader } from '@hermes/plugin-sdk'
import { useState } from 'react'

import { approvalView, editApprovalPrompt } from './ashley'
import { pendingApprovals } from './data'
import { useAsk } from './pipeline'
import { useTeamState } from './state'
import { AGO, Pill } from './ui'

export const APPROVALS_ROUTE = '/approvals'
const NOT_NOW_KEY = 'flo.approvals.not-now'
const NOT_NOW_MS = 8 * 60 * 60 * 1000

function loadNotNow(): Record<string, number> {
  try {
    const raw = window.localStorage.getItem(NOT_NOW_KEY)
    const parsed = raw ? (JSON.parse(raw) as Record<string, number>) : {}
    const now = Date.now()

    return Object.fromEntries(Object.entries(parsed).filter(([, until]) => until > now))
  } catch {
    return {}
  }
}

function decidedLabel(status: string): string {
  switch (status) {
    case 'executed':
      return 'Done'

    case 'rejected':

    case 'denied':
      return 'Declined'

    case 'expired':
      return 'Expired'

    default:
      return status
  }
}

export function ApprovalsPage() {
  const { state } = useTeamState(10_000)
  const { ask, busy } = useAsk(state)
  const [notNow, setNotNow] = useState<Record<string, number>>(loadNotNow)
  const [showSnoozed, setShowSnoozed] = useState(false)
  const names = new Map((state?.workspaces ?? []).map(w => [w.workspace_id, w.display_name ?? w.workspace_id] as const))

  const snooze = (id: string) => {
    const next = { ...notNow, [id]: Date.now() + NOT_NOW_MS }
    setNotNow(next)

    try {
      window.localStorage.setItem(NOT_NOW_KEY, JSON.stringify(next))
    } catch {
      // storage unavailable; the card simply stays visible next time
    }
  }

  const pending = state ? pendingApprovals(state.approvals).map(c => approvalView(c)) : []
  const visible = pending.filter(v => showSnoozed || !notNow[v.proposalId])
  const snoozedCount = pending.filter(v => notNow[v.proposalId]).length
  const decided = state ? state.approvals.filter(c => c.status !== 'pending').slice(0, 10) : []

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 px-6 py-8">
      <header className="flex items-center gap-3">
        <h1 className="m-0 text-lg font-semibold tracking-wide">Approvals</h1>
        <span className="text-xs text-(--ui-text-tertiary)">Nothing leaves the building without your okay.</span>
      </header>
      {!state ? <Loader /> : null}
      {state && visible.length === 0 ? <p className="m-0 text-sm text-(--ui-text-secondary)">Nothing waiting on you. 💚</p> : null}
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {visible.map(v => (
          <li className="flex flex-col gap-2 rounded-md border border-(--ui-stroke-tertiary) p-4" key={v.proposalId}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold">{v.what}</span>
              {v.workspaceId ? <Pill>{names.get(v.workspaceId) ?? v.workspaceId}</Pill> : null}
              {v.expired ? <Pill tone="bad">expired</Pill> : null}
              <span className="ml-auto text-xs text-(--ui-text-tertiary)">{formatAgo(Date.parse(v.createdAt), AGO)}</span>
            </div>
            {v.who ? (
              <p className="m-0 text-sm">
                <span className="text-(--ui-text-tertiary)">To: </span>
                {v.who}
              </p>
            ) : null}
            <p className="m-0 text-sm">
              <span className="text-(--ui-text-tertiary)">Flo proposes: </span>
              {v.proposing}
            </p>
            {v.preview ? (
              <pre className="m-0 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-(--ui-bg-quaternary) p-2 font-sans text-xs">{v.preview}</pre>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button disabled={v.expired} onClick={() => host.newChat(v.agent)} size="sm">
                Approve
              </Button>
              <Button
                disabled={busy !== null}
                onClick={() => ask(`edit:${v.proposalId}`, `Edit · ${v.what}`, editApprovalPrompt(v))}
                size="sm"
                variant="secondary"
              >
                Edit
              </Button>
              <Button onClick={() => snooze(v.proposalId)} size="sm" variant="secondary">
                Not Now
              </Button>
            </div>
            <p className="m-0 text-[0.6875rem] text-(--ui-text-quaternary)">
              Approve opens the chat where the one-click confirmation is waiting; it binds to exactly this content.
            </p>
          </li>
        ))}
      </ul>
      {snoozedCount > 0 ? (
        <button className="self-start text-xs text-(--ui-text-tertiary) hover:underline" onClick={() => setShowSnoozed(s => !s)} type="button">
          {showSnoozed ? 'Hide' : 'Show'} {snoozedCount} set aside for later
        </button>
      ) : null}
      {decided.length > 0 ? (
        <details>
          <summary className="cursor-pointer text-xs text-(--ui-text-secondary)">Recently decided ({decided.length})</summary>
          <ul className="m-0 mt-2 flex list-none flex-col gap-1 p-0 text-xs">
            {decided.map(card => (
              <li className="flex gap-2" key={card.proposal_id}>
                <span>{approvalView(card).what}</span>
                <Pill tone={card.status === 'executed' ? 'good' : card.status === 'rejected' || card.status === 'blocked' ? 'bad' : 'muted'}>
                  {decidedLabel(card.status)}
                </Pill>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  )
}
