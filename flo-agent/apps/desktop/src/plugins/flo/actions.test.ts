import { describe, expect, it } from 'vitest'

import { FLO_ACTIONS } from './actions'

describe('Flo home actions', () => {
  it('covers the six Ashley work modes with unique ids and prompts', () => {
    expect(FLO_ACTIONS.map(a => a.id)).toEqual([
      'morning-brief',
      'file-check',
      'translate-conditions',
      'draft-message',
      'escalation',
      'eod-recap'
    ])
    expect(new Set(FLO_ACTIONS.map(a => a.prompt)).size).toBe(FLO_ACTIONS.length)
  })

  it('every prompt carries Ashley’s communication contract and names a Flo skill', () => {
    for (const action of FLO_ACTIONS) {
      expect(action.prompt).toMatch(/flo-[a-z-]+ skill/)
      expect(action.prompt.length).toBeGreaterThan(80)
      expect(action.title.length).toBeLessThan(24)
    }
  })

  it('drafting never sends and guideline work stays SOURCE_GAP-honest', () => {
    const draft = FLO_ACTIONS.find(a => a.id === 'draft-message')!
    const conditions = FLO_ACTIONS.find(a => a.id === 'translate-conditions')!

    expect(draft.prompt).toContain('Do not send anything')
    expect(conditions.prompt).toContain('SOURCE_GAP')
  })
})
