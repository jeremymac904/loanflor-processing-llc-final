import { describe, expect, it } from 'vitest'

import {
  activeEsignRequest,
  approvalView,
  borrowerRequestWaiting,
  documentBoard,
  documentGroups,
  documentsReceived,
  eligibleEsignTemplate,
  esignBoard,
  esignCancelPrompt,
  esignCompletedLine,
  esignReminderPrompt,
  type FileRecord,
  fileSummary,
  greeting,
  missingDocumentDraft,
  missingDocuments,
  newLoanCard,
  newLoanLine,
  orderPrompt,
  plainStatus,
  prefillSignRecipients,
  readinessLabel,
  requestedMissingItems,
  requestPrompt,
  reviewLine,
  sendForSignaturePrompt,
  teamHints,
  todayModel,
  uploadDocumentsPrompt,
  whyPrompt
} from './ashley'
import type { ApprovalCard, TaskRow } from './data'

const okafor: FileRecord = {
  workspace_id: 'loan_okafor',
  display_name: 'Okafor',
  milestone: 'Processing',
  program: 'fha',
  blockers: [],
  orders: [],
  conditions: [],
  drafts: [{ draft_id: 'draft_1', status: 'draft', audience: 'borrower', purpose: '2024 W-2 request', body: 'Hi …' }],
  readiness: {
    status: 'IN_PROGRESS',
    score: 58,
    missing_count: 1,
    missing: [{ item: '2024 W-2', owner: 'borrower' }],
    aus_findings: 'present',
    best_next_move: 'Only blocker right now: 2024 W-2 from borrower. One clean follow-up.',
    income_assets: { income_prep_complete: true, assets_prep_complete: false }
  },
  updated_at: '2026-09-09T14:00:00+00:00'
}

const bell: FileRecord = {
  workspace_id: 'loan_bell',
  display_name: 'Bell',
  milestone: 'Conditional Approval',
  orders: [
    { order_id: 'ord_1', order_type: 'title', state: 'overdue', vendor_or_destination: 'Approved Title Vendor' }
  ],
  readiness: { status: 'IN_PROGRESS', score: 70, missing_count: 0, missing: [], aus_findings: 'present' },
  updated_at: '2026-09-09T15:00:00+00:00'
}

const mason: FileRecord = {
  workspace_id: 'loan_mason',
  display_name: 'Mason',
  milestone: 'Processing',
  readiness: { status: 'READY_FOR_NEXT_STEP', score: 100, missing_count: 0, missing: [], aus_findings: 'present' }
}

const approval: ApprovalCard = {
  proposal_id: 'prop_1',
  workspace_id: 'loan_mason',
  agent: 'whisper',
  action_type: 'email_send',
  tool_name: 'flo_email_send',
  recipient_or_destination: 'borrower (Mason)',
  summary: 'Send the missing-paystub request to the borrower',
  payload_hash: 'abc123',
  payload_preview: { subject: 'Quick item', body: 'Hi John, quick item to keep us moving…', audience: 'borrower' },
  policy_result: 'confirm',
  status: 'pending',
  created_at: '2026-09-09T15:30:00+00:00',
  expires_at: '2099-01-01T00:00:00+00:00'
}

describe('plain-English status', () => {
  it('never shows an internal state', () => {
    expect(plainStatus(okafor)).toBe('Needs Ashley') // a Whisper draft is waiting for her
    expect(plainStatus(bell)).toBe('At Risk') // overdue title
    expect(plainStatus(mason)).toBe('Done')
    expect(plainStatus({ ...okafor, drafts: [], blockers: [{ text: 'Lender portal locked' }] })).toBe('Blocked')
    expect(plainStatus({ ...okafor, drafts: [] })).toBe('Waiting') // missing item owned by the borrower
    const working: TaskRow = {
      task_id: 't',
      from_agent: 'flo',
      to_agent: 'malcolm',
      objective: 'review',
      status: 'sent',
      depth: 1,
      max_depth: 1,
      workspace_id: 'loan_okafor'
    }
    expect(plainStatus({ ...okafor, drafts: [], readiness: null }, [], [working])).toBe('Working')
    expect(plainStatus(mason, [approval])).toBe('Needs Ashley')
  })

  it('labels readiness in words, not scores', () => {
    expect(readinessLabel(okafor)).toBe('Needs 1 item')
    expect(readinessLabel({ ...okafor, readiness: { ...okafor.readiness, missing_count: 0, missing: [] } })).toBe(
      'Almost ready'
    )
    expect(readinessLabel(mason)).toBe('Ready')
    expect(readinessLabel({ ...okafor, readiness: null })).toBe('Not checked yet')
  })
})

describe('file summary', () => {
  it('shows only what Ashley needs and never says approved', () => {
    const s = fileSummary(okafor)
    expect(s).toMatchObject({
      name: 'Okafor',
      status: 'Needs Ashley',
      readiness: 'Needs 1 item',
      aus: 'Findings on file',
      income: 'Reviewed',
      assets: 'Needs attention',
      orders: 'Nothing ordered yet',
      conditions: 'None open'
    })
    expect(s.nextMove).toBe('Request the missing documents.')
    expect(fileSummary({ ...okafor, blockers: [{ text: 'Lender portal locked' }] }).nextMove).toContain('2024 W-2')
    expect(JSON.stringify(s).toLowerCase()).not.toContain('approved')
    expect(fileSummary(bell).risk).toBe('Title is overdue')
    expect(fileSummary(bell).orders).toBe('Title: overdue')
  })
})

describe('today', () => {
  const state = {
    workspaces: [okafor, bell, mason],
    approvals: [approval],
    tasks: [],
    activity: [
      {
        timestamp: '2026-09-09T14:12:49+00:00',
        actor: 'malcolm',
        event: 'readiness.updated',
        workspace_id: 'loan_okafor'
      },
      { timestamp: '2026-09-09T14:21:36+00:00', actor: 'whisper', event: 'draft.added', workspace_id: 'loan_okafor' },
      {
        timestamp: '2026-09-09T14:30:00+00:00',
        actor: 'flo',
        event: 'handoff.created',
        workspace_id: 'loan_bell',
        to: 'sage'
      } as never,
      { timestamp: '2026-09-09T14:31:00+00:00', actor: 'provider_state', event: 'provider.transition' }
    ]
  }

  it('ranks the top three, names the fastest win and biggest risk, counts needs-you and waiting', () => {
    const model = todayModel(state, new Date('2026-09-09T13:00:00'))
    expect(model.greeting).toBe('Afternoon Ash')
    // Bell is at risk; Okafor needs Ashley and is one item from done; Mason only needs an approval.
    expect(model.top.map(t => t.name)).toEqual(['Bell', 'Okafor', 'Mason'])
    expect(model.top[0].line).toBe('Title is overdue')
    expect(model.biggestRisk?.line).toBe('Bell: Title is overdue.')
    expect(model.fastestWin?.line).toBe('Approve: Send borrower email for Mason.')
    expect(model.needsYou).toBe(2) // one approval + one draft
    expect(model.waitingOnOthers).toBe(2) // overdue title + borrower W-2
    expect(greeting(new Date('2026-09-09T08:00:00'))).toBe('Morning Ash ☕')
  })

  it('turns activity into quiet team hints and drops technical events', () => {
    const hints = teamHints(state.activity, state.workspaces)
    expect(hints).toEqual([
      'Sage is checking a guideline on Bell.',
      'Whisper drafted a message for Okafor.',
      'Malcolm checked the Okafor file.'
    ])
  })
})

describe('website submissions', () => {
  it('shows a new loan card until Malcolm has reviewed it', () => {
    const johnson: FileRecord = {
      workspace_id: 'loan_johnson',
      display_name: 'Johnson',
      milestone: 'Intake',
      submission: {
        submission_id: 'sub_x',
        loan_officer: { name: 'Matt Combs' },
        transaction_label: 'Purchase',
        program_label: 'FHA',
        expected_closing_date: '2026-09-23'
      }
    }

    const working: TaskRow = {
      task_id: 't',
      from_agent: 'flo',
      to_agent: 'malcolm',
      objective: 'review',
      status: 'sent',
      depth: 1,
      max_depth: 1,
      workspace_id: 'loan_johnson'
    }
    const s = fileSummary(johnson, [], [working])
    expect(s.status).toBe('Working')
    expect(s.readiness).toBe('New submission')
    expect(s.nextMove).toBe(
      'Submitted by Matt Combs • FHA • Purchase • Expected closing September 23. Malcolm is reviewing it.'
    )
    const model = todayModel({ workspaces: [johnson], approvals: [], tasks: [working], activity: [] })
    expect(model.newLoans).toEqual([
      {
        workspaceId: 'loan_johnson',
        name: 'Johnson',
        submittedBy: 'Matt Combs',
        program: 'FHA • Purchase',
        expectedClosing: 'September 23',
        documentsReceived: 0,
        line: 'Malcolm is reviewing it.'
      }
    ])
    // After Malcolm's review: plain counts and labels, and the one obvious move.
    const reviewed = fileSummary({
      ...johnson,
      readiness: {
        ...okafor.readiness,
        missing_count: 3,
        missing: [
          { item: 'Updated paystub', owner: 'borrower' },
          { item: 'Bank statement page 4', owner: 'borrower' },
          { item: 'HOI contact', owner: 'lo' }
        ]
      }
    })
    expect(reviewed.readiness).toBe('Needs 3 items')
    expect(reviewed.income).toBe('Reviewed')
    expect(reviewed.assets).toBe('Needs attention')
    expect(reviewed.nextMove).toBe('Request the missing documents.')
  })

  it('shows the documents grouped in plain words, with ✓/⚠ and no storage keys (mirrors documents.py)', () => {
    const johnson: FileRecord = {
      workspace_id: 'loan_johnson',
      display_name: 'Johnson',
      milestone: 'Intake',
      submission: {
        submission_id: 'sub_x',
        loan_officer: { name: 'Matt Combs' },
        transaction_label: 'Purchase',
        program_label: 'FHA',
        expected_closing_date: '2026-09-23'
      },
      documents_summary: {
        received: 8,
        duplicates: 1,
        missing: ['Most recent paystub(s)'],
        needs_clarification: ['2026-09-09_bank_statement_01.pdf: Missing pages — Pages 3 of 4 not in the file']
      },
      document_refs: [
        {
          ref: 'doc://d1',
          document_id: 'd1',
          category: 'assets',
          subcategory: 'bank_statement',
          borrower_ref: 'borrower',
          display_name: '2026-09-09_bank_statement_01.pdf',
          status: 'missing_pages',
          note: 'Pages 3 of 4 not in the file',
          pages: 3,
          local_path: 'C:\\private\\loan_johnson\\assets\\borrower1\\2026-09-09_bank_statement_01.pdf',
          added_at: '2026-09-09T20:00:00+00:00'
        },
        {
          ref: 'doc://d2',
          document_id: 'd2',
          category: 'loan_application',
          display_name: '2026-09-09_loan_application_01.pdf',
          status: 'received',
          pages: 1,
          added_at: '2026-09-09T20:00:00+00:00'
        },
        {
          ref: 'doc://d3',
          document_id: 'd3',
          category: 'income',
          subcategory: 'w2',
          display_name: '2026-09-09_w2_01.pdf',
          status: 'duplicate',
          added_at: '2026-09-09T20:00:00+00:00'
        }
      ]
    }

    const card = newLoanCard(johnson)
    expect(card?.documentsReceived).toBe(8)
    expect(card?.line).toBe('8 documents received. Malcolm is reviewing it.')
    expect(documentsReceived(johnson)).toBe(8)
    const groups = documentGroups(johnson)
    expect(groups.map(g => g.label)).toEqual(['Application', 'Income', 'Assets'])
    const bank = groups[2].documents[0]
    expect(bank.attention).toBe(true)
    expect(bank.statusLabel).toBe('Missing pages')
    expect(bank.subtype).toBe('Bank statement')
    expect(bank.borrower).toBe('Borrower')
    expect(bank.received).toBe('September 9')
    expect(groups[0].documents[0].attention).toBe(false)
    expect(groups[2].attention).toBe(1)
    expect(missingDocuments(johnson)).toEqual(['Most recent paystub(s)'])
    // The board: missing items sit inside their group; insurance / title read "Waiting" until something arrives.
    const board = documentBoard({
      ...johnson,
      readiness: {
        missing: [
          { item: 'Most recent paystub', owner: 'borrower' },
          { item: 'Bank statement page 4', owner: 'borrower' },
          { item: 'HOI declarations page', owner: 'lo' }
        ],
        missing_count: 3
      }
    })
    expect(board.map(g => [g.label, g.documents.length, g.missing, g.waiting])).toEqual([
      ['Application', 1, [], false],
      ['Income', 1, ['Most recent paystub'], false],
      ['Assets', 1, ['Bank statement page 4'], false],
      ['Title / Property', 0, [], true],
      ['Insurance', 0, ['HOI declarations page'], false]
    ])
    // Malcolm's readiness list wins once it exists.
    expect(
      missingDocuments({
        ...johnson,
        readiness: { missing: [{ item: 'Updated paystub', owner: 'borrower' }], missing_count: 1 }
      })
    ).toEqual(['Updated paystub'])
    const visible = JSON.stringify(
      groups.map(g => ({ ...g, documents: g.documents.map(({ path: _path, ...rest }) => rest) }))
    )
    expect(visible).not.toContain('doc://')
    expect(visible).not.toContain('private')
    expect(
      uploadDocumentsPrompt(johnson, ['C:\\Users\\ashley\\Downloads\\paystub.pdf'], 'the most recent paystub')
    ).toContain('flo_documents action=add')
    expect(reviewLine(johnson)).toBeNull()
    expect(
      reviewLine({
        ...johnson,
        readiness: {
          missing: [
            { item: 'Most recent paystub', owner: 'borrower' },
            { item: 'Bank statement page 3', owner: 'borrower' }
          ],
          missing_count: 2
        }
      })
    ).toBe(
      "Johnson is reviewed.\n\n8 documents received.\n\nWe're missing 2 items.\n\nBiggest blocker:\nMost recent paystub.\n\nBest next move:\nRequest the missing docs."
    )
    expect(newLoanLine('Johnson', 12)).toBe(
      'New loan came in — Johnson.\n\n12 documents came with it.\n\nMalcolm is reviewing everything now. 💚'
    )
  })

  it('protects the one-click borrower request and shows sent items as waiting', () => {
    const draft = {
      draft_id: 'draft_request',
      status: 'draft',
      audience: 'borrower',
      purpose: 'Missing document request',
      body: 'Hi John',
      needed: 'Updated paystub\nBank statement page 4'
    }
    expect(missingDocumentDraft({ ...okafor, drafts: [draft] })?.draft_id).toBe('draft_request')
    expect(borrowerRequestWaiting({ ...okafor, drafts: [{ ...draft, status: 'sent' }] })).toBe(true)
    expect(requestedMissingItems({ ...okafor, drafts: [{ ...draft, status: 'sent' }] })).toEqual([
      'Updated paystub',
      'Bank statement page 4'
    ])
    expect(missingDocumentDraft({ ...okafor, drafts: [{ ...draft, status: 'sent' }] })).toBeUndefined()
  })
})

describe('electronic signatures (Documenso)', () => {
  const withLoe: FileRecord = {
    workspace_id: 'loan_johnson',
    display_name: 'Johnson',
    milestone: 'Processing',
    submission: {
      loan_officer: { name: 'Matt Combs' },
      borrowers: [
        { role: 'borrower', name: 'Ariana Justinvil-Synthetic', email: 'ariana@synthetic.test', phone: '9045550102' }
      ]
    },
    document_refs: [
      {
        ref: 'doc://d9',
        document_id: 'd9',
        category: 'other',
        display_name: '2026-09-10_loe_01.pdf',
        status: 'received',
        pages: 1,
        added_at: '2026-09-10T00:00:00+00:00'
      },
      {
        ref: 'doc://d10',
        document_id: 'd10',
        category: 'income',
        subcategory: 'paystub',
        display_name: '2026-09-10_paystub_01.pdf',
        status: 'received',
        pages: 1,
        added_at: '2026-09-10T00:00:00+00:00'
      }
    ]
  }

  it('is eligible only for a document matching a configured template (category and page count)', () => {
    const all = documentGroups(withLoe).flatMap(g => g.documents)
    const loe = all.find(d => d.id === 'd9')!
    const paystub = all.find(d => d.id === 'd10')!
    expect(eligibleEsignTemplate(loe)?.key).toBe('loe')
    expect(eligibleEsignTemplate(paystub)).toBeNull() // wrong category: "This document needs signing setup." in the UI
  })

  it('prefills recipients from the loan but never invents an email', () => {
    expect(prefillSignRecipients(withLoe)).toEqual([
      { name: 'Ariana Justinvil-Synthetic', email: 'ariana@synthetic.test', role: 'SIGNER' }
    ])
    expect(prefillSignRecipients({ ...withLoe, submission: null })).toEqual([])
  })

  it('builds the send prompt with the exact document, recipients and message, routed through flo_esign_send', () => {
    const loe = documentGroups(withLoe)
      .flatMap(g => g.documents)
      .find(d => d.id === 'd9')!
    const prompt = sendForSignaturePrompt(
      withLoe,
      loe,
      'loe',
      [{ name: 'Ariana Justinvil-Synthetic', email: 'ariana@synthetic.test', role: 'SIGNER' }],
      'Please sign this LOE.'
    )
    expect(prompt).toContain('flo_esign_send')
    expect(prompt).toContain('ariana@synthetic.test')
    expect(prompt).toContain('Please sign this LOE.')
    expect(prompt).toContain('this stops at my approval prompt')
  })

  it('shows the plain-English board and the active request for a document, mirroring esign.py board()', () => {
    const ws: FileRecord = {
      ...withLoe,
      esign_requests: [
        {
          request_id: 'esign_1',
          document_id: 'd9',
          status: 'partially_signed',
          recipients: [{ name: 'Ariana Justinvil-Synthetic', email: 'ariana@synthetic.test', role: 'SIGNER' }]
        }
      ]
    }

    const board = esignBoard(ws)
    expect(board[0].status_label).toBe('Waiting for signature')
    const active = activeEsignRequest(ws, 'd9')
    expect(active?.request_id).toBe('esign_1')
    expect(activeEsignRequest(ws, 'd10')).toBeNull() // a different document on the same loan has no active request
    expect(esignReminderPrompt(ws, active!)).toContain('flo_esign_remind')
    expect(esignCancelPrompt(ws, active!)).toContain('flo_esign_cancel')
  })

  it('a cancelled or declined request is no longer "active" (a fresh send is allowed)', () => {
    const ws: FileRecord = {
      ...withLoe,
      esign_requests: [{ request_id: 'esign_1', document_id: 'd9', status: 'cancelled' }]
    }
    expect(activeEsignRequest(ws, 'd9')).toBeNull()
  })

  it("the completed line matches the owner's exact wording", () => {
    expect(esignCompletedLine(withLoe, 'loe')).toBe("Johnson's signed LOE is back and saved to the file. 💚")
  })
})

describe('approvals and one-click prompts', () => {
  it('presents an approval in plain words with a text preview and no hashes', () => {
    const v = approvalView(approval)
    expect(v.what).toBe('Send borrower email')
    expect(v.who).toBe('borrower (Mason)')
    expect(v.preview).toBe('Quick item\n\nHi John, quick item to keep us moving…')
    expect(JSON.stringify(v)).not.toContain('abc123')
  })

  it('routes every button through Flo with the file context', () => {
    expect(requestPrompt(okafor)).toContain('2024 W-2 (borrower)')
    expect(requestPrompt(okafor)).toContain('Whisper')
    expect(orderPrompt(bell, 'hoi')).toContain('homeowners insurance')
    expect(whyPrompt(okafor, '2024 W-2', 'missing')).toContain('Why does Okafor need "2024 W-2"?')
    expect(whyPrompt(okafor, 'Findings on file', 'aus')).toContain('What does "Findings on file" mean')
  })
})
