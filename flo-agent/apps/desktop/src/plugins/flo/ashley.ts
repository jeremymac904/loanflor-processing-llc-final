/**
 * Ashley-facing presentation of the team state — plain English only.
 *
 * Everything the Today / Pipeline / File / Approvals screens show is derived
 * here from the same files the backend writes (`<team root>/workspaces`,
 * `approvals`, `tasks`, `activity`). The rules mirror `plugins/flo-team/today.py`
 * so Flo's chat answers ("what should I work on next?", "where are we on Bell?")
 * and the screens agree. Internal states (pending_review, handoff_open,
 * provider_degraded, …) never reach a label here.
 */

import type { ActivityRow, ApprovalCard, TaskRow, WorkspaceRow } from './data'
import { isExpired, pendingApprovals } from './data'

export type PlainStatus = 'Done' | 'Needs Ashley' | 'Waiting' | 'Working' | 'At Risk' | 'Blocked'

export const STATUS_TONE: Record<PlainStatus, 'muted' | 'warn' | 'bad' | 'good'> = {
  Done: 'good',
  'Needs Ashley': 'warn',
  Waiting: 'muted',
  Working: 'muted',
  'At Risk': 'bad',
  Blocked: 'bad'
}

interface ReadinessItem {
  item: string
  state?: string
  owner?: string
}

interface Readiness {
  status?: string
  score?: number
  missing?: ReadinessItem[]
  missing_count?: number
  discrepancies?: string[]
  aus_findings?: string
  best_next_move?: string
  income_assets?: { income_prep_complete?: boolean | null; assets_prep_complete?: boolean | null }
}

/** Condition object on a workspace. The shape is curated by the backend
 * normalizer (plugins/flo-team/conditions_normalize.py); older files may
 * have only ``text`` / ``state`` populated. Ashley-facing helpers below
 * tolerate both shapes. */
export interface FileCondition {
  id?: string
  text?: string
  /** Original lender / UW line, preserved verbatim for audit. */
  original_text?: string
  /** Plain-English rendering for Ashley. Falls back to ``text`` if absent. */
  plain_english?: string
  /** Canonical short noun phrase ("most recent paystub"). */
  required_item?: string
  /** paystub / w2 / bank_statement / insurance_declaration / … */
  condition_type?: string
  /** income / assets / insurance / … */
  category?: string
  /** Borrower / Loan Officer / Title / Insurance / Employer / Appraiser /
   * Lender/UW / Processor / Other. */
  owner?: string
  /** Source of the condition (lender_email / aus / manual / approval_letter). */
  source?: string
  source_date?: string
  /** Whether guideline interpretation is required (Sage). */
  needs_sage?: boolean
  /** Legacy / canonical state field. */
  state?: string
  /** Display label status ("Open" / "Waiting" / "Cleared" / "Needs Review"). */
  status?: string
  needs_review?: boolean
  needs_review_reason?: string
  needs_review_at?: string
  cleared_at?: string
  cleared_by?: string
  cleared_by_document_id?: string
  cleared_reason?: string
  waiting_at?: string
  waiting_by?: string
  waiting_reason?: string
  added_by?: string
  added_at?: string
}

export interface DocumentRef {
  ref?: string
  document_id?: string
  category?: string
  subcategory?: null | string
  borrower_ref?: null | string
  display_name?: string
  status?: string
  note?: string
  pages?: null | number
  local_path?: null | string
  text_path?: null | string
  added_at?: string
}

/** One signer's completion, as Documenso reports it — kept opaque, never re-derived client-side. */
export interface EsignRecipientStatus {
  name?: string
  email?: string
  signing_status?: string
}

/** A "Send for Signature" request on one document (`plugins/flo-team/esign.py`). Mirrors `esign.board()`. */
export interface EsignRequest {
  request_id?: string
  document_id?: string
  status?: string
  status_label?: string
  explanation?: null | string
  recipients?: Array<{ name?: string; email?: string; role?: string }>
  signed_document_id?: null | string
}

export interface FileRecord extends WorkspaceRow {
  aus?: null | string
  /** Website loan submission (lfprocessing.net) that opened this file. */
  submission?: null | {
    submission_id?: string
    loan_officer?: { name?: string; company?: string }
    borrowers?: Array<{ role?: string; name?: string; email?: string; phone?: string }>
    transaction_label?: string
    program_label?: string
    expected_closing_date?: null | string
    review_status?: string
  }
  conditions?: FileCondition[]
  /** Documents pulled into the Deal Room at intake (`plugins/flo-team/documents.py`). */
  document_refs?: DocumentRef[]
  documents_summary?: null | {
    received?: number
    duplicates?: number
    missing?: string[]
    needs_clarification?: string[]
  }
  /** Signature requests on this file's documents (`plugins/flo-team/esign.py`). */
  esign_requests?: EsignRequest[]
  readiness?: null | Readiness
  drafts?: Array<{
    draft_id?: string
    status?: string
    audience?: string
    purpose?: string
    body?: string
    urgency?: string
    needed?: string
  }>
  orders?: Array<{
    order_id?: string
    order_type?: string
    state?: string
    vendor_or_destination?: string
    purpose?: string
  }>
  blockers?: Array<{ text?: string } | string>
  /** CTC audit fields — only set when Ashley confirmed a real lender
   * CTC notice. Flo itself never writes these from inference. */
  ctc_confirmed_by?: string
  ctc_confirmed_at?: string
  ctc_source?: string
  ctc_source_ref?: string
  ctc_evidence?: string
}

const OPEN_ORDER_STATES = new Set(['requested', 'approved', 'ordered', 'vendor_confirmed', 'pending', 'overdue'])
const OPEN_TASK_STATES = new Set(['proposed', 'sent', 'received', 'in_progress'])
const OTHERS = new Set(['borrower', 'lo', 'lender', 'realtor', 'title', 'vendor', 'ae', 'uw', 'underwriter'])

export function fileName(ws: WorkspaceRow): string {
  return ws.display_name ?? ws.workspace_id
}

function blockerText(b: { text?: string } | string): string {
  return typeof b === 'string' ? b : (b.text ?? 'Blocked')
}

export function openOrders(ws: FileRecord) {
  return (ws.orders ?? []).filter(o => OPEN_ORDER_STATES.has(o.state ?? ''))
}

export function missingItems(ws: FileRecord): ReadinessItem[] {
  return (ws.readiness?.missing ?? []).filter(m => Boolean(m.item))
}

export function draftsForReview(ws: FileRecord) {
  return (ws.drafts ?? []).filter(d => d.status === 'draft' || d.status === 'proposed')
}

/** Canonical owner order for Ashley-facing grouping. UI consumers iterate
 * through this list and stop when a group is empty. Matches the backend
 * group_by_owner() order in plugins/flo-team/conditions_normalize.py. */
export const OWNER_ORDER = [
  'Borrower',
  'Loan Officer',
  'Title',
  'Insurance',
  'Employer',
  'Appraiser',
  'Lender/UW',
  'Processor',
  'Other'
] as const

export type ConditionOwner = (typeof OWNER_ORDER)[number]

/** Plain-English phrase Ashley sees for a waiting condition grouped by
 * owner. Mirrors conditions.waiting_label() on the backend. */
export function waitingLabel(owner: string | null | undefined): string {
  switch ((owner ?? '').trim()) {
    case 'Borrower':
      return 'Waiting on borrower'
    case 'Loan Officer':
      return 'Waiting on loan officer'
    case 'Title':
      return 'Waiting on title'
    case 'Insurance':
      return 'Waiting on insurance'
    case 'Employer':
      return 'Waiting on employer'
    case 'Appraiser':
      return 'Waiting on appraiser'
    case 'Lender/UW':
      return 'Waiting on lender'
    case 'Processor':
      return 'Waiting on processor'
    case 'Other':
      return 'Waiting on third party'
    default:
      return owner ? `Waiting on ${owner.toLowerCase()}` : 'Waiting'
  }
}

/** Short noun phrase Ashley sees on a condition card. Falls back to the
 * raw text when the curated ``required_item`` is missing. */
export function conditionItem(c: FileCondition): string {
  const item = (c.required_item ?? '').trim()
  if (item) return item
  const text = (c.text ?? '').trim()
  return text.length > 80 ? text.slice(0, 77).trimEnd() + '…' : text
}

/** Plain-English line Ashley sees for a condition. Falls back to the raw
 * text when ``plain_english`` hasn't been back-filled. */
export function conditionPlainEnglish(c: FileCondition): string {
  const pe = (c.plain_english ?? '').trim()
  if (pe) return pe
  const text = (c.text ?? '').trim()
  if (!text) return conditionItem(c)
  return text.length > 160 ? text.slice(0, 157).trimEnd() + '…' : text
}

export type ConditionStatus = 'Open' | 'Waiting' | 'Needs Ashley' | 'Needs Review' | 'Cleared'

/** Per-condition status for the Conditions section inside the file view.
 * Maps the workspace condition's ``state`` (open / cleared / waiting) and
 * the ``needs_review`` flag into the five values Ashley sees. */
export function conditionStatus(c: FileCondition): ConditionStatus {
  const state = String(c.state ?? c.status ?? 'open').toLowerCase()
  if (state === 'cleared') return 'Cleared'
  if (state === 'waiting') return 'Waiting'
  if (c.needs_review) return 'Needs Review'
  // Anything not cleared / waiting / needs_review is "Open". A condition
  // that needs Sage is flagged here so the file view shows [Why?] for it
  // (Sage is the path for guideline-interpretation items).
  return 'Open'
}

const CONDITION_TONE: Record<ConditionStatus, 'muted' | 'warn' | 'bad' | 'good'> = {
  Open: 'warn',
  Waiting: 'muted',
  'Needs Review': 'bad',
  'Needs Ashley': 'warn',
  Cleared: 'good'
}

export function conditionStatusTone(s: ConditionStatus) {
  return CONDITION_TONE[s]
}

/** All non-cleared conditions on the workspace, with their canonical
 * status. Used by the Conditions section inside the file view and by
 * Today. Preserves insertion order. */
export function allConditions(ws: FileRecord): FileCondition[] {
  return (ws.conditions ?? []).filter(
    (c): c is FileCondition => typeof c === 'object' && c !== null
  )
}

export function openConditions(ws: FileRecord): FileCondition[] {
  return allConditions(ws).filter(c => conditionStatus(c) !== 'Cleared')
}

/** Conditions owned by a particular owner that are still actionable for
 * Ashley (open or needs review — not already waiting, not cleared). */
export function openConditionsByOwner(ws: FileRecord, owner: string): FileCondition[] {
  const want = (owner ?? '').trim().toLowerCase()
  return openConditions(ws).filter(
    c => String(c.owner ?? '').trim().toLowerCase() === want
  )
}

/** Conditions owned by a particular owner that are currently waiting on
 * someone. Drives the "Waiting on …" lines in Today / Pipeline. */
export function waitingConditionsByOwner(ws: FileRecord, owner: string): FileCondition[] {
  const want = (owner ?? '').trim().toLowerCase()
  return allConditions(ws).filter(
    c =>
      conditionStatus(c) === 'Waiting' &&
      String(c.owner ?? '').trim().toLowerCase() === want
  )
}

/** Open conditions grouped by owner, in the canonical OWNER_ORDER. Drops
 * empty buckets. Used by the Conditions section inside the file view. */
export function conditionsByOwner(ws: FileRecord): Array<{ owner: string; items: FileCondition[] }> {
  const grouped = new Map<string, FileCondition[]>()
  for (const owner of OWNER_ORDER) grouped.set(owner, [])
  for (const c of openConditions(ws)) {
    const o = String(c.owner ?? 'Other').trim() || 'Other'
    if (!grouped.has(o)) grouped.set(o, [])
    grouped.get(o)!.push(c)
  }
  const out: Array<{ owner: string; items: FileCondition[] }> = []
  for (const owner of OWNER_ORDER) {
    const items = grouped.get(owner) ?? []
    if (items.length > 0) out.push({ owner, items })
  }
  return out
}

/** Owner categories that currently have at least one Waiting condition,
 * in canonical order. Used by Today's "Waiting on …" lines. */
export function waitingOwners(ws: FileRecord): string[] {
  const set = new Set<string>()
  for (const c of allConditions(ws)) {
    if (conditionStatus(c) === 'Waiting' && c.owner) set.add(String(c.owner))
  }
  return OWNER_ORDER.filter(o => set.has(o))
}

/** The one borrower-request draft that powers Ashley's inline request panel. */
export function missingDocumentDraft(ws: FileRecord) {
  return (ws.drafts ?? []).find(
    d =>
      d.audience === 'borrower' &&
      (/missing document|missing item|document request|request/i.test(d.purpose ?? '') || Boolean(d.needed)) &&
      (d.status === 'draft' || d.status === 'proposed')
  )
}

/** A sent borrower request turns the same missing rows into a waiting state. */
export function requestedMissingItems(ws: FileRecord): string[] {
  const sent = (ws.drafts ?? []).filter(
    d =>
      d.audience === 'borrower' &&
      d.status === 'sent' &&
      (/missing document|missing item|document request|request/i.test(d.purpose ?? '') || Boolean(d.needed))
  )
  const latest = sent[sent.length - 1]

  return latest?.needed
    ? latest.needed
        .split(/\n|\s*;\s*/)
        .map(item => item.replace(/^[-•]\s*/, '').trim())
        .filter(Boolean)
    : []
}

export function borrowerRequestWaiting(ws: FileRecord): boolean {
  return requestedMissingItems(ws).length > 0
}

/** One plain-English state per file. Order of precedence matters: the worst news wins. */
export function plainStatus(ws: FileRecord, approvals: ApprovalCard[] = [], tasks: TaskRow[] = []): PlainStatus {
  const r = ws.readiness ?? null
  const blocked = (ws.blockers ?? []).length > 0 || r?.status === 'BLOCKED'

  if (blocked) {
    return 'Blocked'
  }

  const overdue = (ws.orders ?? []).some(o => o.state === 'overdue')
  const closingWithGaps = ws.milestone === 'Clear to Close' && (r?.missing_count ?? 0) > 0

  if (overdue || closingWithGaps) {
    return 'At Risk'
  }

  const needsAshley =
    pendingApprovals(approvals).some(c => c.workspace_id === ws.workspace_id && !isExpired(c)) ||
    draftsForReview(ws).length > 0

  if (needsAshley) {
    return 'Needs Ashley'
  }

  if (ws.milestone === 'Closed' || (r?.status === 'READY_FOR_NEXT_STEP' && openOrders(ws).length === 0)) {
    return 'Done'
  }

  const working = tasks.some(t => t.workspace_id === ws.workspace_id && OPEN_TASK_STATES.has(t.status))

  if (working) {
    return 'Working'
  }

  const waitingOnOthers =
    openOrders(ws).length > 0 || missingItems(ws).some(m => OTHERS.has((m.owner ?? '').toLowerCase()))

  return waitingOnOthers ? 'Waiting' : 'Working'
}

/** '2026-09-23' -> 'September 23' (what Ashley reads on a card). */
export function longDate(value: null | string | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value ?? '')

  if (!m) {
    return value ?? ''
  }

  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric'
  })
}

export interface NewLoanCard {
  workspaceId: string
  name: string
  submittedBy: string
  program: string
  expectedClosing: null | string
  documentsReceived: number
  line: string
}

/** "12 documents" / "1 document". */
function docCount(n: number): string {
  return `${n} ${n === 1 ? 'document' : 'documents'}`
}

/** The NEW LOAN card for a website submission Malcolm has not reviewed yet. Mirrors today.py `new_loan_card`. */
export function newLoanCard(ws: FileRecord): null | NewLoanCard {
  const sub = ws.submission

  if (!sub || ws.readiness) {
    return null
  }

  const docs = ws.documents_summary?.received ?? 0

  return {
    workspaceId: ws.workspace_id,
    name: fileName(ws),
    submittedBy: sub.loan_officer?.name ?? 'the loan officer',
    program: [sub.program_label, sub.transaction_label].filter(Boolean).join(' • '),
    expectedClosing: sub.expected_closing_date ? longDate(sub.expected_closing_date) : null,
    documentsReceived: docs,
    line: `${docs > 0 ? `${docCount(docs)} received. ` : ''}Malcolm is reviewing it.`
  }
}

// ── Documents (what Ashley sees on the file) ─────────────────────────────────

export const DOCUMENT_CATEGORY_LABEL: Record<string, string> = {
  loan_application: 'Application',
  credit_report: 'Credit',
  aus_findings: 'AUS',
  income: 'Income',
  assets: 'Assets',
  purchase_contract: 'Contract',
  title_property: 'Title / Property',
  insurance: 'Insurance',
  identification: 'ID',
  other: 'Other'
}

const DOCUMENT_CATEGORY_ORDER = Object.keys(DOCUMENT_CATEGORY_LABEL)

export const DOCUMENT_SUBTYPE_LABEL: Record<string, string> = {
  paystub: 'Paystub',
  w2: 'W-2',
  '1099': '1099',
  tax_return: 'Tax return',
  profit_and_loss: 'P&L',
  k1: 'K-1',
  bank_statement: 'Bank statement',
  retirement_statement: 'Retirement statement',
  gift_documentation: 'Gift documentation',
  other: 'Other'
}

export const DOCUMENT_STATUS_LABEL: Record<string, string> = {
  received: 'Received',
  needs_review: 'Needs review',
  reviewed: 'Reviewed',
  missing_pages: 'Missing pages',
  unreadable: 'Unreadable',
  duplicate: 'Duplicate',
  not_needed: 'Not needed',
  listed: 'Listed, not received'
}

export const DOCUMENT_BORROWER_LABEL: Record<string, string> = {
  borrower: 'Borrower',
  co_borrower: 'Co-borrower',
  both: 'Both'
}

/** ⚠ statuses; everything else is ✓ (Not needed and Duplicate stay quiet). */
const DOCUMENT_ATTENTION = new Set(['needs_review', 'missing_pages', 'unreadable', 'listed'])

export interface DocumentView {
  id: string
  name: string
  category: string
  categoryLabel: string
  subtype: null | string
  borrower: null | string
  status: string
  statusLabel: string
  attention: boolean
  note: string
  pages: null | number
  received: null | string
  /** Private copy on this machine — used for preview/open only, never shown. */
  path: null | string
}

export interface DocumentGroup {
  category: string
  label: string
  documents: DocumentView[]
  attention: number
}

function documentView(d: DocumentRef): DocumentView {
  const status = d.status ?? 'received'

  return {
    id: d.document_id ?? d.ref ?? d.display_name ?? '',
    name: d.display_name ?? 'Document',
    category: d.category ?? 'other',
    categoryLabel: DOCUMENT_CATEGORY_LABEL[d.category ?? 'other'] ?? 'Other',
    subtype: d.subcategory ? (DOCUMENT_SUBTYPE_LABEL[d.subcategory] ?? d.subcategory) : null,
    borrower: d.borrower_ref ? (DOCUMENT_BORROWER_LABEL[d.borrower_ref] ?? d.borrower_ref) : null,
    status,
    statusLabel: DOCUMENT_STATUS_LABEL[status] ?? 'Received',
    attention: DOCUMENT_ATTENTION.has(status),
    note: d.note ?? '',
    pages: d.pages ?? null,
    received: d.added_at ? longDate(d.added_at.slice(0, 10)) : null,
    path: d.local_path ?? null
  }
}

/** Documents grouped the way the file screen shows them (Application, Credit, AUS, Income, …). Mirrors documents.py `ashley_documents`. */
export function documentGroups(ws: FileRecord): DocumentGroup[] {
  const views = (ws.document_refs ?? []).map(documentView)
  const byCategory = new Map<string, DocumentView[]>()

  for (const v of views) {
    byCategory.set(v.category, [...(byCategory.get(v.category) ?? []), v])
  }

  const order = [
    ...DOCUMENT_CATEGORY_ORDER,
    ...[...byCategory.keys()].filter(c => !DOCUMENT_CATEGORY_ORDER.includes(c))
  ]

  return order
    .filter(c => (byCategory.get(c) ?? []).length > 0)
    .map(c => {
      const documents = byCategory.get(c) ?? []

      return {
        category: c,
        label: DOCUMENT_CATEGORY_LABEL[c] ?? c,
        documents,
        attention: documents.filter(d => d.attention).length
      }
    })
}

/** Which group a missing item belongs to, from its wording. Mirrors today.py `_missing_category`. Order matters. */
const MISSING_ROUTES: Array<[string, RegExp]> = [
  ['insurance', /insurance|\bhoi\b|hazard|flood/i],
  ['title_property', /\btitle\b|appraisal|survey/i],
  ['purchase_contract', /contract|purchase agreement/i],
  ['aus_findings', /\baus\b|\bdu\b|findings|\blpa\b|\btotal\b|\bgus\b/i],
  ['credit_report', /credit/i],
  ['loan_application', /1003|application/i],
  ['income', /paystub|pay stub|w-?2|1099|tax return|income|k-?1|p&l|profit|award letter|\bvoe\b/i],
  ['assets', /bank|statement|asset|retirement|gift|funds/i],
  ['identification', /identification|license|passport|\bid\b/i]
]

export function missingCategory(item: string): string {
  return MISSING_ROUTES.find(([, re]) => re.test(item))?.[0] ?? 'other'
}

/** Categories that read "Waiting" on a website file until something arrives. */
const WAITING_CATEGORIES = ['insurance', 'title_property']

export interface DocumentBoardGroup extends DocumentGroup {
  /** Missing items routed into this group ("⚠ Most recent paystub missing"). */
  missing: string[]
  /** Nothing received and nothing missing yet: "Waiting". */
  waiting: boolean
}

/** The DOCUMENTS section as Ashley reads it: received docs ✓/⚠ and missing items inside their group. Mirrors today.py `document_board`. */
export function documentBoard(ws: FileRecord): DocumentBoardGroup[] {
  const groups: DocumentBoardGroup[] = documentGroups(ws).map(g => ({ ...g, missing: [], waiting: false }))
  const byCategory = new Map(groups.map(g => [g.category, g]))

  for (const item of missingDocuments(ws)) {
    const category = missingCategory(item)
    let group = byCategory.get(category)

    if (!group) {
      group = {
        category,
        label: DOCUMENT_CATEGORY_LABEL[category] ?? 'Other',
        documents: [],
        attention: 0,
        missing: [],
        waiting: false
      }
      byCategory.set(category, group)
      groups.push(group)
    }

    group.missing.push(item)
  }

  if (ws.submission) {
    for (const category of WAITING_CATEGORIES) {
      if (!byCategory.has(category)) {
        const group = {
          category,
          label: DOCUMENT_CATEGORY_LABEL[category],
          documents: [],
          attention: 0,
          missing: [],
          waiting: true
        }
        byCategory.set(category, group)
        groups.push(group)
      }
    }
  }

  const order = [
    ...DOCUMENT_CATEGORY_ORDER,
    ...groups.map(g => g.category).filter(c => !DOCUMENT_CATEGORY_ORDER.includes(c))
  ]

  return groups.sort((a, b) => order.indexOf(a.category) - order.indexOf(b.category))
}

export function documentsReceived(ws: FileRecord): number {
  const summary = ws.documents_summary?.received

  if (typeof summary === 'number') {
    return summary
  }

  return (ws.document_refs ?? []).filter(d => d.status !== 'duplicate' && d.status !== 'listed').length
}

/** What is still missing on the file: Malcolm's readiness list first, then the intake inventory before his review. */
export function missingDocuments(ws: FileRecord): string[] {
  const fromReadiness = missingItems(ws).map(m => m.item)

  if (fromReadiness.length > 0) {
    return fromReadiness
  }

  return ws.documents_summary?.missing ?? []
}

export function uploadDocumentsPrompt(ws: FileRecord, paths: string[], note = ''): string {
  const files = paths.map(p => `"${p}"`).join(', ')

  return `Add ${paths.length === 1 ? 'this file' : 'these files'} to ${fileName(ws)} (Deal Room ${ws.workspace_id}): ${files}. ${note ? `It is ${note}. ` : ''}File each one under the right category (ask me if it is not obvious) with flo_documents action=add, then tell me in one line what landed and whether anything is still missing.`
}

export function reclassifyDocumentPrompt(ws: FileRecord, doc: DocumentView): string {
  return `Reclassify "${doc.name}" on ${fileName(ws)} (Deal Room ${ws.workspace_id}, document ${doc.id}). It is filed under ${doc.categoryLabel}${doc.subtype ? ` / ${doc.subtype}` : ''} right now. Ask me what it actually is (category, type, which borrower), then update it with flo_documents action=update and confirm in one line.`
}

export function notNeededDocumentPrompt(ws: FileRecord, doc: DocumentView): string {
  return `Mark "${doc.name}" on ${fileName(ws)} (Deal Room ${ws.workspace_id}, document ${doc.id}) as not needed with flo_documents action=update status=not_needed, then tell me in one line whether the file still has anything missing.`
}

// ── Electronic signatures (Documenso; plugins/flo-team/esign.py) ────────────
// Owner decision 2026-09-10: Documenso, self-hosted, one approved LOE template to start. This is Ashley's
// only new surface for this feature — inside the existing Documents section, no new dashboard.

export interface EsignTemplate {
  key: string
  label: string
  /** Only a document in this category is eligible — mirrors `esign.py` `eligible_templates` structurally
   *  (category + page count), since the desktop cannot inspect Documenso's own template fields without a
   *  live instance. Kept in sync with `knowledge/esign_templates.json` by test, same as `today.py`/`ashley.ts`. */
  category: string
  expectedPageCount: null | number
}

/** Exactly one template this phase (owner directive): the approved Letter of Explanation. */
export const ESIGN_TEMPLATES: EsignTemplate[] = [
  { key: 'loe', label: 'Letter of Explanation', category: 'other', expectedPageCount: 1 }
]

export const ESIGN_STATUS_LABEL: Record<string, string> = {
  draft: 'Ready to send',
  sent: 'Waiting for signature',
  partially_signed: 'Waiting for signature',
  signed: 'Signed',
  retrieved: 'Signed',
  declined: 'Needs attention',
  cancelled: 'Needs attention',
  needs_attention: 'Needs attention'
}

/** Which configured template (if any) a document could be sent through. Mirrors `esign.py` `eligible_templates`. */
export function eligibleEsignTemplate(doc: DocumentView): null | EsignTemplate {
  return (
    ESIGN_TEMPLATES.find(
      t => t.category === doc.category && (t.expectedPageCount === null || t.expectedPageCount === doc.pages)
    ) ?? null
  )
}

/** A document that already has a live (not cancelled/declined) signature request. */
export function activeEsignRequest(ws: FileRecord, documentId: string): null | EsignRequest {
  return (
    (ws.esign_requests ?? []).find(
      r => r.document_id === documentId && r.status !== 'cancelled' && r.status !== 'declined'
    ) ?? null
  )
}

/** Ashley's board for the Documents section — status in plain words, mirrors `esign.py` `board()`. */
export function esignBoard(ws: FileRecord): EsignRequest[] {
  return (ws.esign_requests ?? []).map(r => ({
    ...r,
    status_label: ESIGN_STATUS_LABEL[r.status ?? 'draft'] ?? 'Needs attention'
  }))
}

/** Borrower/co-borrower recipients prefilled from the submission — Ashley must still confirm every one. */
export function prefillSignRecipients(ws: FileRecord): Array<{ name: string; email: string; role: string }> {
  return (ws.submission?.borrowers ?? []).map(b => ({ name: b.name ?? '', email: b.email ?? '', role: 'SIGNER' }))
}

export function sendForSignaturePrompt(
  ws: FileRecord,
  doc: DocumentView,
  templateKey: string,
  recipients: Array<{ name: string; email: string; role: string }>,
  message: string
): string {
  const who = recipients.map(r => `${r.name} <${r.email}>`).join(', ')

  return (
    `Send "${doc.name}" on ${fileName(ws)} (Deal Room ${ws.workspace_id}, document ${doc.id}) for signature. ` +
    `Template: ${templateKey}. Recipients: ${who}. Message: "${message}". ` +
    `Call flo_esign_send with workspace_id, document_id=${doc.id}, document_checksum, template_key=${templateKey}, recipients and message exactly as above — ` +
    `this stops at my approval prompt, so show me what it will send before I confirm. ` +
    `Once I approve, tell me in one line: "Sent for signature. I'll put the signed copy back here when it's ready."`
  )
}

export function esignReminderPrompt(ws: FileRecord, request: EsignRequest): string {
  return `Send an approved reminder for the signature request on ${fileName(ws)} (Deal Room ${ws.workspace_id}, request ${request.request_id}) with flo_esign_remind — this stops at my approval prompt. Confirm in one line once it goes out.`
}

export function esignCancelPrompt(ws: FileRecord, request: EsignRequest): string {
  return `Cancel the signature request on ${fileName(ws)} (Deal Room ${ws.workspace_id}, request ${request.request_id}) with flo_esign_cancel — this stops at my approval prompt. Confirm in one line once it is voided.`
}

const ESIGN_SHORT_NAME: Record<string, string> = { loe: 'LOE' }

/** Flo's one-line completion message. Mirrors the owner's exact wording: "Johnson's signed LOE is back and saved to the file. 💚" */
export function esignCompletedLine(ws: FileRecord, templateKey: string): string {
  return `${fileName(ws)}'s signed ${ESIGN_SHORT_NAME[templateKey] ?? 'document'} is back and saved to the file. 💚`
}

/** "Submitted by Matt Combs • FHA • Purchase • Expected closing September 23. Malcolm is reviewing it." */
export function submissionLine(ws: FileRecord): null | string {
  const card = newLoanCard(ws)

  if (!card) {
    return null
  }

  const parts = [
    `Submitted by ${card.submittedBy}`,
    card.program,
    card.expectedClosing ? `Expected closing ${card.expectedClosing}` : ''
  ].filter(Boolean)

  return `${parts.join(' • ')}. ${card.line}`
}

export function readinessLabel(ws: FileRecord): string {
  const r = ws.readiness

  if (!r) {
    return ws.submission ? 'New submission' : 'Not checked yet'
  }

  if (r.status === 'BLOCKED') {
    return 'Blocked'
  }

  if (r.status === 'READY_FOR_NEXT_STEP') {
    return 'Ready'
  }

  if (r.status === 'NOT_STARTED') {
    return 'Not started'
  }

  const missing = r.missing_count ?? missingItems(ws).length

  if (missing > 0) {
    return `Needs ${missing} ${missing === 1 ? 'item' : 'items'}`
  }

  return (r.score ?? 0) >= 50 ? 'Almost ready' : 'In progress'
}

function ausLabel(ws: FileRecord): string {
  if (ws.aus) {
    return ws.aus
  }

  switch (ws.readiness?.aus_findings) {
    case 'present':
      return 'Findings on file'

    case 'missing':
      return 'Missing'

    default:
      return 'Not checked yet'
  }
}

function prepLabel(flag: boolean | null | undefined): string {
  if (flag === true) {
    return 'Reviewed'
  }

  if (flag === false) {
    return 'Needs attention'
  }

  return 'Not checked yet'
}

export const ORDER_TYPE_LABEL: Record<string, string> = {
  title: 'Title',
  hoi: 'Homeowners insurance',
  wvoe: 'Written VOE',
  voe: 'VOE',
  loe_request: 'Letter of explanation',
  custom: 'Order'
}

export function orderStateLabel(state?: string): string {
  switch (state) {
    case 'requested':
      return 'Proposed, needs your approval'

    case 'approved':
      return 'Approved, placing'

    case 'ordered':

    case 'vendor_confirmed':

    case 'pending':
      return 'Ordered, waiting on vendor'

    case 'overdue':
      return 'Overdue'

    case 'received':
      return 'Received'

    case 'reconciled':
      return 'Done'

    case 'cancelled':
      return 'Cancelled'

    default:
      return 'Not ordered'
  }
}

export function ordersLabel(ws: FileRecord): string {
  const orders = ws.orders ?? []

  if (orders.length === 0) {
    return 'Nothing ordered yet'
  }

  return orders
    .map(o => `${ORDER_TYPE_LABEL[o.order_type ?? 'custom'] ?? 'Order'}: ${orderStateLabel(o.state).toLowerCase()}`)
    .join(' · ')
}

/** First sentence, bounded — Malcolm's reasons can run long; Ashley gets the headline. Mirrors today.py `short`. */
export function short(text: null | string | undefined, limit = 140): string {
  // Malcolm's machine flags ("(verified=false)") never reach Ashley.
  const s = (text ?? '')
    .split(/\s+/)
    .join(' ')
    .replace(/\s*\((?:verified|is_underwriting_decision)=\w+\)/g, '')
    .replace(/[. ]+$/, '')

  if (!s) {
    return ''
  }

  let first = s.split(/(?<=[.;])\s+/)[0].replace(/[. ;]+$/, '')

  if (first.length > limit) {
    first = `${first
      .slice(0, limit - 1)
      .split(' ')
      .slice(0, -1)
      .join(' ')}…`
  }

  return first
}

export function riskLine(ws: FileRecord): null | string {
  const blocker = (ws.blockers ?? [])[0]

  if (blocker) {
    return blockerText(blocker)
  }

  const overdue = (ws.orders ?? []).find(o => o.state === 'overdue')

  if (overdue) {
    return `${ORDER_TYPE_LABEL[overdue.order_type ?? 'custom'] ?? 'An order'} is overdue`
  }

  if (ws.milestone === 'Clear to Close' && (ws.readiness?.missing_count ?? 0) > 0) {
    return 'Clear to Close with items still missing'
  }

  const discrepancy = ws.readiness?.discrepancies?.[0]

  return discrepancy ? short(discrepancy.replace(/^conflicting:\s*/i, '')) : null
}

export function bestNextMove(ws: FileRecord): string {
  const fresh = submissionLine(ws)

  if (fresh) {
    return fresh
  }

  const conflicting = (ws.readiness?.discrepancies ?? []).some(d => /^conflicting/i.test(d))

  if (missingItems(ws).length > 0 && (ws.blockers ?? []).length === 0 && !conflicting) {
    if (borrowerRequestWaiting(ws)) {
      return 'Follow up tomorrow if not received.'
    }

    return 'Request the missing documents.'
  }

  return short(ws.next_action || ws.readiness?.best_next_move, 160) || 'Nothing urgent. Flo will flag the next step.'
}

/** Flo's after-review line for a website submission. Mirrors today.py `review_line`. */
export function reviewLine(ws: FileRecord): null | string {
  if (!ws.submission || !ws.readiness) {
    return null
  }

  const docs = documentsReceived(ws)
  const missing = missingItems(ws)
  const blocker = riskLine(ws) ?? (missing.length > 0 ? short(missing[0].item, 80) : null)
  const n = missing.length
  const move = bestNextMove(ws) === 'Request the missing documents.' ? 'Request the missing docs.' : bestNextMove(ws)
  const parts = [
    `${fileName(ws)} is reviewed.`,
    `${docCount(docs)} received.`,
    n === 0 ? "We're not missing anything." : `We're missing ${n} ${n === 1 ? 'item' : 'items'}.`
  ]

  if (blocker) {
    parts.push(`Biggest blocker:\n${blocker.replace(/\.+$/, '')}.`)
  }

  parts.push(`Best next move:\n${move}`)

  return parts.join('\n\n')
}

/** Flo's line when a website submission lands. Mirrors today.py `new_loan_line`. */
export function newLoanLine(name: string, documents: number): string {
  const middle = documents > 0 ? `${docCount(documents)} came with it.` : 'No documents came with it.'

  return `New loan came in — ${name}.\n\n${middle}\n\nMalcolm is reviewing everything now. 💚`
}

export interface FileSummary {
  workspaceId: string
  name: string
  status: PlainStatus
  milestone: string
  readiness: string
  aus: string
  income: string
  assets: string
  orders: string
  conditions: string
  missing: ReadinessItem[]
  documents: number
  nextMove: string
  risk: null | string
  missingItems: string[]
  importantDiscrepancies: string[]
  ausStatus: string
  incomeStatus: string
  assetStatus: string
  ordersStatus: string
  biggestBlocker: null | string
}

export function fileSummary(ws: FileRecord, approvals: ApprovalCard[] = [], tasks: TaskRow[] = []): FileSummary {
  const open = (ws.conditions ?? []).filter(c => (c.state ?? 'open') !== 'cleared')

  return {
    documents: documentsReceived(ws),
    workspaceId: ws.workspace_id,
    name: fileName(ws),
    status: plainStatus(ws, approvals, tasks),
    milestone: ws.milestone ?? 'Intake',
    readiness: readinessLabel(ws),
    aus: ausLabel(ws),
    income: prepLabel(ws.readiness?.income_assets?.income_prep_complete),
    assets: prepLabel(ws.readiness?.income_assets?.assets_prep_complete),
    orders: ordersLabel(ws),
    conditions: open.length === 0 ? 'None open' : `${open.length} open`,
    missing: missingItems(ws),
    nextMove: bestNextMove(ws),
    risk: riskLine(ws),
    missingItems: missingItems(ws).map(item => short(item.item, 120)),
    importantDiscrepancies: (ws.readiness?.discrepancies ?? []).map(item =>
      short(item.replace(/^conflicting:\s*/i, ''), 120)
    ),
    ausStatus: ausLabel(ws),
    incomeStatus: prepLabel(ws.readiness?.income_assets?.income_prep_complete),
    assetStatus: prepLabel(ws.readiness?.income_assets?.assets_prep_complete),
    ordersStatus: ordersLabel(ws),
    biggestBlocker: riskLine(ws) ?? (missingItems(ws)[0]?.item ? short(missingItems(ws)[0].item, 120) : null)
  }
}

// ── Today ────────────────────────────────────────────────────────────────────

export interface TodayItem {
  workspaceId: string
  name: string
  line: string
  status: PlainStatus
  missingCount: number
  waitingOn: string | null
  nextMove: string
}

export interface TodayModel {
  greeting: string
  newLoans: NewLoanCard[]
  top: TodayItem[]
  fastestWin: null | { line: string; workspaceId?: string; proposalId?: string }
  biggestRisk: null | { line: string; workspaceId: string }
  needsYou: number
  waitingOnOthers: number
  handling: string[]
}

export function greeting(now = new Date()): string {
  const h = now.getHours()

  if (h < 12) {
    return 'Morning Ash ☕'
  }

  if (h < 17) {
    return 'Afternoon Ash'
  }

  return 'Evening Ash'
}

function priorityScore(status: PlainStatus, ws: FileRecord): number {
  const base = { Blocked: 100, 'At Risk': 80, 'Needs Ashley': 60, Working: 20, Waiting: 10, Done: 0 }[status]
  const fastest = ws.readiness?.missing_count === 1 ? 15 : 0
  const closing = ws.milestone === 'Clear to Close' ? 10 : 0
  const next = ws.next_action ? 5 : 0

  return base + fastest + closing + next
}

const OUTCOME_EVENTS: Record<string, (file: string, row: ActivityRow & Record<string, unknown>) => null | string> = {
  'readiness.updated': file => `Malcolm checked the ${file} file.`,
  'draft.added': file => `Whisper drafted a message for ${file}.`,
  'order.updated': (file, row) =>
    `Chadwick is tracking ${ORDER_TYPE_LABEL[String(row.order_type ?? '')]?.toLowerCase() ?? 'an order'} on ${file}.`,
  'handoff.created': (file, row) => {
    switch (row.to) {
      case 'sage':
        return `Sage is checking a guideline on ${file}.`

      case 'malcolm':
        return `Malcolm is reviewing ${file}.`

      case 'whisper':
        return `Whisper is drafting for ${file}.`

      case 'chadwick':
        return `Chadwick is on the orders for ${file}.`

      default:
        return null
    }
  },
  'handoff.completed': (file, row) => (row.actor === 'sage' ? `Sage verified the guideline on ${file}.` : null),
  'approval.proposed': file => `Something on ${file} is ready for your okay.`
}

/** Small contextual hints ("Malcolm checked the file.") — never a raw event feed. */
export function teamHints(activity: ActivityRow[], workspaces: WorkspaceRow[], limit = 5): string[] {
  const names = new Map(workspaces.map(w => [w.workspace_id, fileName(w)] as const))
  const out: string[] = []

  for (const row of [...activity].sort((a, b) => (b.timestamp ?? '').localeCompare(a.timestamp ?? ''))) {
    const make = OUTCOME_EVENTS[row.event ?? '']

    if (!make) {
      continue
    }

    const file = row.workspace_id ? (names.get(row.workspace_id) ?? 'a file') : 'a file'
    const line = make(file, row as ActivityRow & Record<string, unknown>)

    if (line && !out.includes(line)) {
      out.push(line)
    }

    if (out.length >= limit) {
      break
    }
  }

  return out
}

export function todayModel(
  input: { workspaces: WorkspaceRow[]; approvals: ApprovalCard[]; tasks: TaskRow[]; activity: ActivityRow[] },
  now = new Date()
): TodayModel {
  const files = input.workspaces as FileRecord[]
  const pending = pendingApprovals(input.approvals).filter(c => !isExpired(c, now.getTime()))
  const summaries = files.map(ws => ({ ws, status: plainStatus(ws, input.approvals, input.tasks) }))

  const ranked = summaries
    .filter(s => s.status !== 'Done')
    .sort(
      (a, b) =>
        priorityScore(b.status, b.ws) - priorityScore(a.status, a.ws) ||
        (b.ws.updated_at ?? '').localeCompare(a.ws.updated_at ?? '')
    )

  const top = ranked.slice(0, 3).map(s => ({
    workspaceId: s.ws.workspace_id,
    name: fileName(s.ws),
    line:
      s.status === 'Blocked' || s.status === 'At Risk' ? (riskLine(s.ws) ?? bestNextMove(s.ws)) : bestNextMove(s.ws),
    status: s.status,
    missingCount: missingItems(s.ws).length,
    waitingOn: missingItems(s.ws).length > 0 ? 'Borrower documents' : openOrders(s.ws).length > 0 ? 'Others' : null,
    nextMove: bestNextMove(s.ws)
  }))

  const firstApproval = pending[0]
  const oneAway = summaries.find(s => s.ws.readiness?.missing_count === 1 && s.status !== 'Done')

  const fastestWin = firstApproval
    ? {
        line: `Approve: ${approvalWhat(firstApproval)}${firstApproval.workspace_id ? ` for ${fileNameById(files, firstApproval.workspace_id)}` : ''}.`,
        workspaceId: firstApproval.workspace_id ?? undefined,
        proposalId: firstApproval.proposal_id
      }
    : oneAway
      ? {
          line: `${fileName(oneAway.ws)}: one item left — ${missingItems(oneAway.ws)[0]?.item ?? 'see the file'}.`,
          workspaceId: oneAway.ws.workspace_id
        }
      : null

  const risky = ranked.find(s => s.status === 'Blocked' || s.status === 'At Risk')
  const biggestRisk = risky
    ? { line: `${fileName(risky.ws)}: ${riskLine(risky.ws) ?? 'needs a look'}.`, workspaceId: risky.ws.workspace_id }
    : null

  const needsYou = pending.length + files.reduce((n, ws) => n + draftsForReview(ws).length, 0)

  const waitingOnOthers = files.reduce(
    (n, ws) =>
      n + openOrders(ws).length + missingItems(ws).filter(m => OTHERS.has((m.owner ?? '').toLowerCase())).length,
    0
  )

  return {
    greeting: greeting(now),
    newLoans: files.map(newLoanCard).filter((c): c is NewLoanCard => c !== null),
    top,
    fastestWin,
    biggestRisk,
    needsYou,
    waitingOnOthers,
    handling: teamHints(input.activity, input.workspaces)
  }
}

function fileNameById(files: WorkspaceRow[], id: string): string {
  return fileName(files.find(w => w.workspace_id === id) ?? { workspace_id: id })
}

// ── Approvals ────────────────────────────────────────────────────────────────

const CAPABILITY_LABEL: Record<string, string> = {
  email_send: 'Send an email',
  outbound_message: 'Send a message',
  email_modify: 'Change an email',
  drive_upload: 'Upload a file',
  drive_share_external: 'Share a file outside the team',
  calendar_write: 'Update the calendar',
  portal_submit: 'Submit to a portal',
  external_status_change: 'Update a status'
}

export function approvalWhat(card: ApprovalCard): string {
  const key = card.action_type ?? ''

  if (CAPABILITY_LABEL[key]) {
    const audience = String(card.payload_preview?.audience ?? '')

    return key === 'email_send' && audience === 'borrower' ? 'Send borrower email' : CAPABILITY_LABEL[key]
  }

  if (/order/.test(key)) {
    return 'Place an order'
  }

  if (/publish|post|newsletter|social|gbp/.test(key)) {
    return 'Publish a post'
  }

  return key.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase()) || 'Take an action'
}

export interface ApprovalView {
  proposalId: string
  what: string
  who: null | string
  proposing: string
  preview: null | string
  agent: string
  workspaceId: null | string
  createdAt: string
  expired: boolean
}

const PREVIEW_KEYS = ['subject', 'body', 'message', 'text', 'content', 'caption', 'description', 'instructions']

export function approvalView(card: ApprovalCard, now = Date.now()): ApprovalView {
  const preview = PREVIEW_KEYS.map(k => card.payload_preview?.[k])
    .filter((v): v is string => typeof v === 'string' && v.trim().length > 0)
    .join('\n\n')

  return {
    proposalId: card.proposal_id,
    what: approvalWhat(card),
    who: card.recipient_or_destination ?? null,
    proposing: card.summary,
    preview: preview || null,
    agent: card.agent,
    workspaceId: card.workspace_id ?? null,
    createdAt: card.created_at,
    expired: isExpired(card, now)
  }
}

// ── One-click prompts (Flo does the thinking; Ashley never picks a bot) ──────

export function requestPrompt(ws: FileRecord): string {
  const items = missingItems(ws)
  const list =
    items.length > 0
      ? items.map(m => `${m.item}${m.owner ? ` (${m.owner})` : ''}`).join('\n- ')
      : 'whatever is still missing'

  return `Request the missing items on ${fileName(ws)} (Deal Room ${ws}). The exact items are:\n- ${list}\nHave Whisper create exactly one concise borrower message, with these items in the draft's needed field as a newline-separated list. Do not create a duplicate if an active or already-sent borrower request exists. Keep the wording warm and simple; do not explain underwriting rules. Put the draft in the file for Ashley to review. Sending must still stop at Ashley's approval.`
}

export function orderPrompt(ws: FileRecord, orderType: string): string {
  const label = ORDER_TYPE_LABEL[orderType] ?? orderType

  return `Order ${label.toLowerCase()} on ${fileName(ws)} (Deal Room ${ws.workspace_id}). Have Chadwick put the proposal together with the approved vendor and give me one card to approve. If something is missing for the order, tell me in one line.`
}

export type WhyKind = 'missing' | 'condition' | 'warning' | 'income' | 'asset' | 'aus'

export function whyPrompt(ws: FileRecord, subject: string, kind: WhyKind): string {
  const question =
    kind === 'aus' ? `What does "${subject}" mean for ${fileName(ws)}?` : `Why does ${fileName(ws)} need "${subject}"?`

  return `${question} (Deal Room ${ws.workspace_id}${ws.program ? `, ${ws.program}` : ''}). Check with Sage against the current activated source and give me, in plain English: why it matters, the source and section, what satisfies it, any lender overlay, and anything uncertain. Keep it short.`
}

export function askFloPrompt(ws: FileRecord): string {
  return `Where are we on ${fileName(ws)} (Deal Room ${ws.workspace_id})? One clean summary: status, readiness, AUS, income, assets, orders, conditions, and the best next move.`
}

export function reviewDraftPrompt(ws: FileRecord, draftId: string): string {
  return `Show me Whisper's draft ${draftId} for ${fileName(ws)} (Deal Room ${ws.workspace_id}). If it reads right I will say "send" and you propose the send for my approval; otherwise I will tell you what to change.`
}

export function sendDraftPrompt(ws: FileRecord, draftId: string): string {
  return `Send Whisper's borrower missing-document draft ${draftId} for ${fileName(ws)} (Deal Room ${ws.workspace_id}) exactly as written using the approved borrower-message path. This must stop at Ashley's approval before anything is sent. After the approved send succeeds, mark the draft sent with its execution reference and leave the requested items as waiting on the borrower.`
}

export function editDraftPrompt(ws: FileRecord, draftId: string, body: string): string {
  return `Update Whisper's borrower missing-document draft ${draftId} for ${fileName(ws)} (Deal Room ${ws.workspace_id}) to exactly this concise message, preserving the same requested items and borrower audience. Do not send it: ${body}`
}

export function editApprovalPrompt(view: ApprovalView): string {
  return `I want to edit the pending approval ${view.proposalId} (${view.what.toLowerCase()}${view.who ? ` to ${view.who}` : ''}). Show me what it says now and ask me what to change; re-propose it after the edit.`
}

/** Item lines for one consolidated request draft, plain-English only. */
function _conditionList(items: FileCondition[]): string {
  if (items.length === 0) return 'whatever is still outstanding'
  return items.map(c => `- ${conditionItem(c)}`).join('\n')
}

/** Build the prompt that creates ONE Whisper draft covering every open
 * Borrower-owned condition on this file. Reuses the existing single-request
 * pipeline (flo_draft + Approvals gate); the difference is that the draft
 * is bundled, not per-item. */
export function borrowerRequestPrompt(ws: FileRecord): string {
  const items = openConditionsByOwner(ws, 'Borrower')
  const list = _conditionList(items)
  const flag = items.some(c => c.needs_sage)
    ? ' Some of these look like they need a guideline check; if so, route that part to Sage and tell me what they said before drafting.'
    : ''
  return `Send ONE borrower message for ${fileName(ws)} (Deal Room ${ws.workspace_id}, ${ws.program ?? ''}). The Borrower-owned items are:\n${list}\nHave Whisper put together a single concise message with all of these. Do not create more than one draft; if an active or already-sent borrower request exists for this file, do not create a duplicate. Sending still stops at Ashley's approval. After the approved send, mark each of these items as Waiting on borrower.${flag}`
}

/** Same shape, but for Loan Officer-owned items. */
export function loRequestPrompt(ws: FileRecord): string {
  const items = openConditionsByOwner(ws, 'Loan Officer')
  const list = _conditionList(items)
  return `Send ONE concise loan-officer message for ${fileName(ws)} (Deal Room ${ws.workspace_id}) asking for these items:\n${list}\nKeep borrower requests and loan-officer requests separate. Sending stops at Ashley's approval. After the approved send, mark each of these items as Waiting on loan officer.`
}

/** A short plain-English list of one owner's open conditions — used both
 * as the body of a one-click request draft and as the bullet list shown
 * next to the Request buttons. */
export function conditionBulletList(ws: FileRecord, owner: string): string {
  const items = openConditionsByOwner(ws, owner)
  return _conditionList(items)
}

/** Are there enough open conditions of one owner that the consolidated
 * one-click button is the right primary CTA? Returns the count. The UI
 * shows the consolidated button whenever the count is >= 2 and switches
 * to the per-item pattern only for single-item cases (so existing flow
 * keeps working). */
export function groupedOwnerCount(ws: FileRecord, owner: string): number {
  return openConditionsByOwner(ws, owner).length
}

/** Are any open conditions of this owner currently waiting? Used to
 * disable the consolidated button while a send is in flight. */
export function ownerHasWaiting(ws: FileRecord, owner: string): boolean {
  return waitingConditionsByOwner(ws, owner).length > 0
}

// ── CTC readiness ─────────────────────────────────────────────────────────

export type CtcReadiness = {
  open_count: number
  waiting_count: number
  needs_review_count: number
  cleared_count: number
  all_tracked: boolean
  /** One plain-English line for Ashley. Never says "you are CTC". */
  summary: string
}

/** Plain-English CTC readiness derived from the workspace's conditions.
 * Mirrors plugins/flo-team/ctc.ctc_readiness(). The summary deliberately
 * uses words like "almost there" / "everything is cleared; waiting on
 * the lender" — never "you are clear to close" — because Flo does not
 * grant CTC. */
export function ctcReadiness(ws: FileRecord): CtcReadiness {
  const conditions = (ws.conditions ?? []).filter(
    (c): c is FileCondition => typeof c === 'object' && c !== null
  )
  let openCount = 0
  let waitingCount = 0
  let needsReviewCount = 0
  let clearedCount = 0
  for (const c of conditions) {
    const status = conditionStatus(c)
    if (status === 'Cleared') clearedCount += 1
    else if (status === 'Waiting') waitingCount += 1
    else if (status === 'Needs Review') needsReviewCount += 1
    else openCount += 1
  }
  const total = openCount + waitingCount + needsReviewCount + clearedCount
  const allTracked = total > 0 && openCount + waitingCount + needsReviewCount === 0
  let summary: string
  if (total === 0) {
    summary = 'CTC readiness: nothing tracked yet.'
  } else if (allTracked) {
    summary = "Everything we're tracking is cleared. Waiting on the lender for Clear to Close."
  } else {
    const bits: string[] = []
    if (openCount) bits.push(`${openCount} open`)
    if (waitingCount) bits.push(`${waitingCount} waiting`)
    if (needsReviewCount) {
      bits.push(`${needsReviewCount} need${needsReviewCount === 1 ? 's' : ''} review`)
    }
    summary = `CTC readiness: almost there (${bits.join(', ')}).`
  }
  return {
    open_count: openCount,
    waiting_count: waitingCount,
    needs_review_count: needsReviewCount,
    cleared_count: clearedCount,
    all_tracked: allTracked,
    summary
  }
}

/** Has the lender / UW source actually issued CTC? Reads
 * ``ws.ctc_confirmed_by`` set by the backend ``confirm_clear_to_close``
 * path; only Ashley's confirmation (or another explicit authorized
 * source) flips it. Flo itself never flips this from inference. */
export function isLenderCtcConfirmed(ws: FileRecord): boolean {
  return ws.milestone === 'Clear to Close' && Boolean(ws.ctc_confirmed_at)
}

/** Short celebration message once a real lender CTC lands. Mirrors
 * plugins/flo-team/ctc.ctc_celebration(). */
export function ctcCelebration(ws: FileRecord): string {
  const name = ws.display_name ?? ws.workspace_id ?? 'this file'
  return `${name} is CTC. Boom. 💚`
}

export const NEXT_MOVE_PROMPT =
  'What should I work on next? Give me ONE best next move, then the next two priorities. Short.'
