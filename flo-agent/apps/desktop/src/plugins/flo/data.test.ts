import { describe, expect, it } from 'vitest'

import {
  freshnessLabel,
  heatMap,
  isExpired,
  openTasksByAgent,
  parseJsonl,
  pendingApprovals,
  rosterFromProfiles,
  teamRootFromHome
} from './data'

describe('Flo Team data helpers', () => {
  it('resolves the shared team root from a profile home or the default home', () => {
    expect(teamRootFromHome('C:\\Users\\x\\AppData\\Local\\hermes\\profiles\\sage')).toBe(
      'C:\\Users\\x\\AppData\\Local\\hermes\\flo\\team'
    )
    expect(teamRootFromHome('/home/x/.hermes/profiles/flo/')).toBe('/home/x/.hermes/flo/team')
    expect(teamRootFromHome('/home/x/.hermes')).toBe('/home/x/.hermes/flo/team')
  })

  it('builds the roster in team order from profiles.list rows and ignores non-team profiles', () => {
    const roster = rosterFromProfiles([
      { name: 'ashley', display_name: 'Ashley' },
      {
        name: 'sage',
        display_name: 'Sage',
        ui_meta: {
          'hermes-bots': { title: 'Sage', description: 'Underwriting: source-backed answers', color: '#123d2a' }
        },
        has_avatar: true
      },
      {
        name: 'flo',
        display_name: 'Flo',
        ui_meta: { 'hermes-bots': { title: 'Flo', description: 'Team Leader: triage', pinned: true } },
        last_session: { updated_at: 1_700_000_000_000, busy: true }
      },
      { name: 'default' }
    ])

    expect(roster.map(m => m.name)).toEqual(['flo', 'sage'])
    expect(roster[0]).toMatchObject({
      displayName: 'Flo',
      title: 'Team Leader',
      pinned: true,
      busy: true,
      lastSessionAt: 1_700_000_000_000
    })
    expect(roster[1]).toMatchObject({
      title: 'Underwriting',
      description: 'source-backed answers',
      color: '#123d2a',
      hasAvatar: true
    })
  })

  it('parses jsonl leniently and groups open tasks by assignee', () => {
    const rows = parseJsonl<{ a: number }>('{"a":1}\nnot json\n\n{"a":2}\n')
    expect(rows).toEqual([{ a: 1 }, { a: 2 }])

    const tasks = openTasksByAgent([
      { task_id: 't1', from_agent: 'flo', to_agent: 'sage', objective: 'x', status: 'sent', depth: 1, max_depth: 1 },
      {
        task_id: 't2',
        from_agent: 'flo',
        to_agent: 'sage',
        objective: 'y',
        status: 'completed',
        depth: 1,
        max_depth: 1
      },
      {
        task_id: 't3',
        from_agent: 'flo',
        to_agent: 'malcolm',
        objective: 'z',
        status: 'received',
        depth: 1,
        max_depth: 1
      }
    ])

    expect(Object.keys(tasks).sort()).toEqual(['malcolm', 'sage'])
    expect(tasks.sage).toHaveLength(1)
  })

  it('derives the pipeline heat map like the backend', () => {
    const map = heatMap([
      { workspace_id: 'a', blockers: [{}], milestone: 'Clear to Close', next_action: 'call' },
      { workspace_id: 'b', orders: [{ state: 'overdue' }] },
      { workspace_id: 'c', orders: [{ state: 'pending' }], readiness: { missing_count: 1 } },
      { workspace_id: 'd' }
    ])

    expect(map.blocked.map(w => w.workspace_id)).toEqual(['a'])
    expect(map.closing_pressure.map(w => w.workspace_id)).toEqual(['a'])
    expect(map.at_risk.map(w => w.workspace_id)).toEqual(['b'])
    expect(map.waiting.map(w => w.workspace_id)).toEqual(['c'])
    expect(map.fastest_wins.map(w => w.workspace_id)).toEqual(['c'])
    expect(map.today.map(w => w.workspace_id)).toEqual(['a'])
  })

  it('lists pending approvals newest first and detects expiry', () => {
    const base = {
      agent: 'whisper',
      action_type: 'email_send',
      tool_name: 't',
      summary: 's',
      payload_hash: 'h',
      policy_result: 'confirm'
    }

    const cards = pendingApprovals([
      { ...base, proposal_id: 'p1', status: 'pending', created_at: '2026-09-08T10:00:00Z' },
      { ...base, proposal_id: 'p2', status: 'executed', created_at: '2026-09-08T11:00:00Z' },
      {
        ...base,
        proposal_id: 'p3',
        status: 'pending',
        created_at: '2026-09-08T12:00:00Z',
        expires_at: '2026-09-08T12:30:00Z'
      }
    ])

    expect(cards.map(c => c.proposal_id)).toEqual(['p3', 'p1'])
    expect(isExpired(cards[0], Date.parse('2026-09-08T13:00:00Z'))).toBe(true)
    expect(isExpired(cards[1])).toBe(false)
  })

  it('labels knowledge freshness without ever calling a pending source current', () => {
    expect(freshnessLabel({ source_id: 'a', lifecycle: 'active' })).toBe('active')
    expect(freshnessLabel({ source_id: 'b', lifecycle: 'pending_review' })).toBe('pending review')
    expect(freshnessLabel({ source_id: 'c' })).toBe('unknown')
  })
})

import { availableActions, effectiveLabel, type KnowledgeCenterRow } from './data'

const row = (over: Partial<KnowledgeCenterRow>): KnowledgeCenterRow => ({
  program: 'fha',
  program_display: 'FHA',
  source: 'Handbook 4000.1',
  section: 'II.A.4.c@update-18',
  section_number: 'II.A.4.c',
  version: 'update-18',
  status: 'active',
  usable: false,
  checksum: 'abc',
  revision_id: 'fha-ii.a.4.c_update-18-abc',
  rules_extracted: 9,
  regression: { ok: true, checked: 9, failed: [], receipt: 'regr_x' },
  supersedes: [],
  pending_update: [],
  impact: { calculators: [], workflows: [], tests: [], summary: '' },
  actions: {},
  ...over
})

describe('Knowledge Center helpers', () => {
  it('labels CURRENT / FUTURE / SUPERSEDED from the resolution', () => {
    expect(effectiveLabel(row({ resolution: 'FUTURE' }))).toBe('FUTURE — NOT YET EFFECTIVE')
    expect(effectiveLabel(row({ resolution: 'CURRENT', usable: true }))).toBe('CURRENT')
    expect(effectiveLabel(row({ resolution: 'SUPERSEDED' }))).toBe('SUPERSEDED')
    expect(effectiveLabel(row({ resolution: null, usable: false, status: 'detected' }))).toBe('—')
  })

  it('offers only lifecycle-appropriate actions and never a casual activate', () => {
    expect(availableActions(row({ status: 'detected' }))).toEqual(['view_source_metadata', 'view_extracted_rules', 'run_regression', 'reject'])
    expect(availableActions(row({ status: 'regression' }))).toContain('approve')
    expect(availableActions(row({ status: 'regression' }))).not.toContain('activate')
    expect(availableActions(row({ status: 'approval' }))).toContain('activate')
    expect(availableActions(row({ status: 'active', supersedes: ['II.A.4.c@update-17'] }))).toContain('compare_versions')
    expect(availableActions(row({ status: 'STALE_SOURCE' }))).toContain('run_regression')
  })
})
