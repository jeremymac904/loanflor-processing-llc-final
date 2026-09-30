import { describe, expect, it } from 'vitest'

import { activityId, nextFloMoment } from './moment'

const event = (name: string, timestamp: string) => ({ event: name, timestamp, workspace_id: 'synthetic-file' })

describe('Flo milestone moments', () => {
  it('only celebrates an actually new workspace creation', () => {
    const existing = event('workspace.created', '2026-01-01T00:00:00Z')
    const seen = new Set([activityId(existing)])
    expect(nextFloMoment([existing], seen)).toBeNull()
    expect(nextFloMoment([existing, event('workspace.created', '2026-01-02T00:00:00Z')], seen)?.kind).toBe('new-loan')
  })

  it('only celebrates a newly proposed approval', () => {
    const seen = new Set<string>()
    expect(nextFloMoment([event('approval.executed', '2026-01-02T00:00:00Z')], seen)).toBeNull()
    expect(nextFloMoment([event('approval.proposed', '2026-01-03T00:00:00Z')], seen)?.kind).toBe('approval')
  })

  it('never treats cleared conditions as CTC', () => {
    const seen = new Set<string>()
    expect(nextFloMoment([event('condition.cleared', '2026-01-02T00:00:00Z')], seen)).toBeNull()
    expect(nextFloMoment([event('ctc.confirmed', '2026-01-03T00:00:00Z')], seen)?.kind).toBe('ctc')
    expect(nextFloMoment([event('ctc.confirmed', '2026-01-03T00:00:00Z')], seen)).toBeNull()
  })

  it('only treats confirmed signing as success', () => {
    const seen = new Set<string>()
    expect(nextFloMoment([{ ...event('esign.updated', '2026-01-02T00:00:00Z'), status: 'pending' }], seen)).toBeNull()
    expect(
      nextFloMoment([{ ...event('esign.updated', '2026-01-03T00:00:00Z'), status: 'completed' }], seen)?.kind
    ).toBe('success')
  })
})
