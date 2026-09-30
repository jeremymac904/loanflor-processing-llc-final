import { useEffect, useRef, useState } from 'react'

import { flashPetActivity } from '@/store/pet'

import type { ActivityRow } from './data'
import floSprites from './assets/flo-pet-spritesheet.png'
import { useTeamState } from './state'

type MomentKind = 'new-loan' | 'approval' | 'ctc' | 'success'

export interface FloMoment {
  id: string
  kind: MomentKind
  title: string
  detail: string
}

export function activityId(row: ActivityRow): string {
  return [row.event, row.timestamp, row.workspace_id, row.proposal_id].join('|')
}

const MOMENT_EVENTS: Record<string, Omit<FloMoment, 'id'>> = {
  'workspace.created': { kind: 'new-loan', title: 'New loan just landed. 🌿', detail: 'Want me to prep it?' },
  'approval.proposed': {
    kind: 'approval',
    title: 'Ready for your approval, Ash.',
    detail: 'Take a look when you’re ready.'
  },
  'ctc.confirmed': { kind: 'ctc', title: 'CTC. Boom. 💚', detail: 'Clear to Close is confirmed.' }
}

const SMALL_MOMENTS: Record<string, Omit<FloMoment, 'id'>> = {
  'readiness.updated': { kind: 'success', title: 'Malcolm finished the prep.', detail: 'Done and filed.' },
  'draft.added': { kind: 'success', title: 'Whisper’s draft is ready.', detail: 'Review it when you’re ready.' }
}

function momentFor(row: ActivityRow): Omit<FloMoment, 'id'> | null {
  const event = row.event ?? ''
  if (MOMENT_EVENTS[event]) return MOMENT_EVENTS[event]
  if (SMALL_MOMENTS[event]) return SMALL_MOMENTS[event]
  const fields = row as ActivityRow & { state?: string; status?: string }
  if (event === 'order.updated' && fields.state === 'proposed')
    return { kind: 'success', title: 'Order proposed.', detail: 'Waiting on your approval.' }
  if (event === 'esign.updated' && fields.status === 'completed')
    return { kind: 'success', title: 'Signature completed.', detail: 'Done and filed.' }
  return null
}

/** Only backend-confirmed new activity counts. Initial history is a baseline,
 * never a reason to celebrate an old milestone on startup/restart. */
export function nextFloMoment(rows: ActivityRow[], seen: Set<string>): FloMoment | null {
  const fresh = rows
    .filter(row => row.timestamp && momentFor(row) && !seen.has(activityId(row)))
    .sort((a, b) => (b.timestamp ?? '').localeCompare(a.timestamp ?? ''))

  for (const row of rows) seen.add(activityId(row))
  const row = fresh[0]
  if (!row || !row.event) return null
  return { id: activityId(row), ...momentFor(row)! }
}

export function FloMomentObserver() {
  const { state } = useTeamState(8_000)
  const seen = useRef<Set<string> | null>(null)
  const [moment, setMoment] = useState<FloMoment | null>(null)

  useEffect(() => {
    if (!state?.root) return
    if (!seen.current) {
      seen.current = new Set(state.activity.map(activityId))
      return
    }
    const next = nextFloMoment(state.activity, seen.current)
    if (!next) return
    setMoment(next)
    flashPetActivity(
      {
        celebrate: next.kind === 'ctc' || next.kind === 'new-loan',
        justCompleted: next.kind === 'approval' || next.kind === 'success'
      },
      1600
    )
  }, [state])

  useEffect(() => {
    if (!moment) return
    const timer = window.setTimeout(
      () => setMoment(null),
      moment.kind === 'ctc' ? 4200 : moment.kind === 'success' ? 2200 : 3000
    )
    return () => window.clearTimeout(timer)
  }, [moment])

  if (!moment) return null
  return (
    <aside
      aria-live="polite"
      className={`flo-moment flo-moment--${moment.kind}`}
      data-testid={`flo-moment-${moment.kind}`}
    >
      <span
        aria-hidden
        className={`flo-moment__sticker flo-moment__sticker--${moment.kind}`}
        style={{ backgroundImage: `url(${floSprites})` }}
      />
      <div className="min-w-0">
        <strong className="flo-display block text-base leading-tight">{moment.title}</strong>
        <span className="text-xs text-(--ui-text-secondary)">{moment.detail}</span>
      </div>
      <span aria-hidden className="flo-moment__leaf">
        ✦
      </span>
      <button
        aria-label="Dismiss"
        className="ml-auto self-start rounded p-1 text-xs text-(--ui-text-secondary) hover:bg-(--chrome-action-hover) focus-visible:outline-2 focus-visible:outline-(--ui-accent)"
        onClick={() => setMoment(null)}
        type="button"
      >
        ✕
      </button>
    </aside>
  )
}
