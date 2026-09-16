/**
 * Flo Team data access — pure helpers over the shared team state the
 * `flo-team` backend plugin writes under `<hermes root>/flo/team/`:
 *
 *   workspaces/<id>.json   Loan Workspaces / Deal Rooms
 *   tasks/<id>.json        handoffs (parent/child, depth, status)
 *   approvals/<id>.json    Ashley Approval Center cards
 *   activity/*.jsonl       team activity timeline
 *   knowledge-registry.json  Sage's source registry (copied by the installer)
 *
 * Reads go through `window.hermesDesktop.readDir/readFileText` (renderer
 * preview reads; no new IPC). Everything here is side-effect free and
 * unit-testable; the React page in plugin.tsx is a thin view.
 */

export interface TeamMember {
  name: string
  displayName: string
  title: string
  description: string
  color: string
  pinned: boolean
  hasAvatar: boolean
  lastSessionAt: null | number
  busy: boolean
}

export interface WorkspaceRow {
  workspace_id: string
  display_name?: string
  program?: null | string
  agency?: null | string
  milestone?: string
  status_summary?: null | string
  next_action?: null | string
  members?: string[]
  blockers?: unknown[]
  orders?: Array<{ order_id?: string; order_type?: string; state?: string }>
  drafts?: Array<{ draft_id?: string; status?: string }>
  readiness?: null | { score?: number; status?: string; missing_count?: number }
  agent_tasks?: string[]
  approvals?: Array<{ proposal_id: string; agent: string; status: string }>
  activity?: Array<{ timestamp: string; actor: string; event: string }>
  updated_at?: string
}

export interface TaskRow {
  task_id: string
  from_agent: string
  to_agent: string
  objective: string
  status: string
  depth: number
  max_depth: number
  workspace_id?: null | string
  urgency?: null | string
  updated_at?: string
}

export interface ApprovalCard {
  proposal_id: string
  workspace_id?: null | string
  agent: string
  action_type: string
  tool_name: string
  recipient_or_destination?: null | string
  summary: string
  payload_hash: string
  payload_preview?: Record<string, unknown>
  data_categories?: string[]
  policy_result: string
  status: string
  created_at: string
  expires_at?: string
  decided_by?: null | string
  execution_ref?: null | string
  session_id?: null | string
}

export interface ActivityRow {
  timestamp?: string
  actor?: string
  event?: string
  workspace_id?: string
  task_id?: string
  proposal_id?: string
  tool?: string
  decision?: string
  layer?: string
}

export interface KnowledgeSource {
  source_id: string
  title?: string
  program?: string
  lifecycle?: string
  status?: string
  checked_at?: string
  publication_date?: null | string
  official_url?: string
}

/** One section revision in the Knowledge Center (`<team root>/knowledge/center.json`, built by scripts/flo/knowledge_center.py). */
export interface KnowledgeCenterRow {
  program: string
  program_display: string
  source: string
  section: string
  section_number: string
  title?: string
  version?: null | string
  current_version?: null | string
  resolution?: null | string
  published?: null | string
  effective?: null | string
  mandatory_date?: null | string
  status: string
  usable: boolean
  checksum: string
  revision_id: string
  official_url?: string
  rules_extracted: number
  regression: { ok: boolean | null; checked: number; failed: string[]; receipt: null | string }
  human_approval?: null | {
    approved_by_user_id?: string
    approved_by_display_name?: string
    approved_at?: string
    approval_reason?: string
    environment?: string
    identity_source?: string
  }
  supersedes: string[]
  pending_update: Array<{ key: string; effective?: null | string; status: string }>
  impact: { calculators: string[]; workflows: string[]; tests: string[]; summary: string }
  actions: Record<string, string>
  capture_method?: string
  retrieved_at?: string
}

export interface KnowledgeCenterData {
  generated_at: string
  rows: KnowledgeCenterRow[]
  guidance_pending: Array<{ guidance_id: string; text: string; scope: string; workspace_id?: null | string; source_ref: string; status: string }>
  overlays: Array<{ overlay_id: string; lender: string; program: string; lifecycle: string; ae_confirmation_status: string; text: string }>
  note?: string
}

export type KnowledgeCenterAction =
  | 'view_source_metadata'
  | 'view_extracted_rules'
  | 'compare_versions'
  | 'run_regression'
  | 'approve'
  | 'reject'
  | 'activate'
  | 'archive'

export const KNOWLEDGE_CENTER_ACTIONS: Array<[KnowledgeCenterAction, string]> = [
  ['view_source_metadata', 'View Source Metadata'],
  ['view_extracted_rules', 'View Extracted Rules'],
  ['compare_versions', 'Compare Versions'],
  ['run_regression', 'Run Regression'],
  ['approve', 'Approve'],
  ['reject', 'Reject'],
  ['activate', 'Activate'],
  ['archive', 'Archive']
]

/** Which lifecycle actions make sense for a row (the CLI still enforces the state machine). */
export function availableActions(row: KnowledgeCenterRow): KnowledgeCenterAction[] {
  const base: KnowledgeCenterAction[] = ['view_source_metadata', 'view_extracted_rules']

  if (row.pending_update.length > 0 || row.supersedes.length > 0) {
    base.push('compare_versions')
  }

  switch (row.status) {
    case 'detected':

    case 'pending_review':
      return [...base, 'run_regression', 'reject']

    case 'regression':
      return [...base, 'approve', 'reject']

    case 'approval':
      return [...base, 'activate', 'reject']

    case 'active':
      return [...base, 'run_regression', 'archive']

    case 'STALE_SOURCE':
      return [...base, 'run_regression', 'archive']

    default:
      return base
  }
}

export function effectiveLabel(row: KnowledgeCenterRow): string {
  if (row.resolution === 'FUTURE') {
    return 'FUTURE — NOT YET EFFECTIVE'
  }

  if (row.resolution === 'SUPERSEDED') {
    return 'SUPERSEDED'
  }

  if (row.resolution === 'CURRENT' || row.resolution === 'EARLY_IMPLEMENTATION') {
    return 'CURRENT'
  }

  return row.usable ? 'CURRENT' : '—'
}

export const TEAM_ORDER = ['flo', 'malcolm', 'chadwick', 'whisper', 'sage', 'franklin'] as const

/** `<hermes_home>` may be a named profile dir; the team root is one per install. */
export function teamRootFromHome(hermesHome: string): string {
  const trimmed = hermesHome.replace(/[\\/]+$/, '')
  const parts = trimmed.split(/[\\/]/)
  const sep = trimmed.includes('\\') ? '\\' : '/'
  const idx = parts.lastIndexOf('profiles')

  if (idx > 0 && idx === parts.length - 2) {
    return [...parts.slice(0, idx), 'flo', 'team'].join(sep)
  }

  return [...parts, 'flo', 'team'].join(sep)
}

interface ProfileRow {
  name: string
  display_name?: string
  description?: string
  ui_meta?: { 'hermes-bots'?: { title?: string; description?: string; color?: string; pinned?: boolean } }
  has_avatar?: boolean
  last_session?: null | { updated_at?: number | string; busy?: boolean }
  worker_session?: null | { busy?: boolean }
}

/** Filter `profiles.list` rows down to the six team members, in roster order. */
export function rosterFromProfiles(rows: ProfileRow[]): TeamMember[] {
  const byName = new Map(rows.map(r => [r.name, r] as const))

  return TEAM_ORDER.filter(name => byName.has(name)).map(name => {
    const row = byName.get(name)!
    const bots = row.ui_meta?.['hermes-bots'] ?? {}
    const [title = '', ...rest] = (bots.description ?? row.description ?? '').split(':')
    const last = row.last_session?.updated_at
    const lastAt = typeof last === 'number' ? last : typeof last === 'string' ? Date.parse(last) : null

    return {
      name,
      displayName: bots.title || row.display_name || name,
      title: title.trim(),
      description: rest.join(':').trim(),
      color: bots.color ?? '#1f5a2d',
      pinned: Boolean(bots.pinned),
      hasAvatar: Boolean(row.has_avatar),
      lastSessionAt: Number.isFinite(lastAt as number) ? (lastAt as number) : null,
      busy: Boolean(row.last_session?.busy || row.worker_session?.busy)
    }
  })
}

export function parseJsonl<T>(text: string): T[] {
  return text
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
    .flatMap(line => {
      try {
        return [JSON.parse(line) as T]
      } catch {
        return []
      }
    })
}

export function openTasksByAgent(tasks: TaskRow[]): Record<string, TaskRow[]> {
  const open = tasks.filter(t => !['completed', 'returned', 'cancelled', 'refused'].includes(t.status))
  const out: Record<string, TaskRow[]> = {}

  for (const task of open) {
    ;(out[task.to_agent] ??= []).push(task)
  }

  return out
}

export interface HeatMap {
  today: WorkspaceRow[]
  at_risk: WorkspaceRow[]
  waiting: WorkspaceRow[]
  blocked: WorkspaceRow[]
  closing_pressure: WorkspaceRow[]
  fastest_wins: WorkspaceRow[]
}

/** Same buckets as the backend `flo_team action=heat_map` (derived, never judged). */
export function heatMap(rows: WorkspaceRow[]): HeatMap {
  const map: HeatMap = { today: [], at_risk: [], waiting: [], blocked: [], closing_pressure: [], fastest_wins: [] }

  for (const ws of rows) {
    const openOrders = (ws.orders ?? []).filter(o => !['reconciled', 'received'].includes(o.state ?? ''))
    const overdue = openOrders.filter(o => o.state === 'overdue')

    if ((ws.blockers ?? []).length > 0) {
      map.blocked.push(ws)
    } else if (overdue.length > 0) {
      map.at_risk.push(ws)
    } else if (openOrders.length > 0) {
      map.waiting.push(ws)
    }

    if (ws.milestone === 'Clear to Close') {
      map.closing_pressure.push(ws)
    }

    if (ws.readiness?.missing_count === 1) {
      map.fastest_wins.push(ws)
    }

    if (ws.next_action) {
      map.today.push(ws)
    }
  }

  return map
}

export function pendingApprovals(cards: ApprovalCard[]): ApprovalCard[] {
  return cards
    .filter(c => c.status === 'pending')
    .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''))
}

export function isExpired(card: ApprovalCard, now = Date.now()): boolean {
  return Boolean(card.expires_at) && Date.parse(card.expires_at!) <= now
}

export function freshnessLabel(source: KnowledgeSource): 'active' | 'pending review' | 'unknown' {
  if (source.lifecycle === 'active') {
    return 'active'
  }

  if (
    source.lifecycle === 'pending_review' ||
    source.lifecycle === 'detected' ||
    source.lifecycle === 'regression' ||
    source.lifecycle === 'approval'
  ) {
    return 'pending review'
  }

  return 'unknown'
}

/** Team activity + role-policy rows, newest first, bounded. */
export function recentActivity(rows: ActivityRow[], limit = 60): ActivityRow[] {
  return [...rows].sort((a, b) => (b.timestamp ?? '').localeCompare(a.timestamp ?? '')).slice(0, limit)
}
