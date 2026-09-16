/**
 * The six Flo work modes from the Ashley product spec, as ready-to-submit
 * prompts. Each prompt names the bundled skill that carries the source-backed
 * rules and Ashley's communication contract, so the agent loads it and stays
 * SOURCE_GAP-honest.
 */

export interface FloAction {
  blurb: string
  codicon: string
  id: string
  prompt: string
  title: string
}

const CONTRACT =
  'Use the flo-communication skill: lead with what matters most, then status, the action needed, urgency, and the cleanest next move or a ready-to-send draft. Top three first, short and plain, no filler.'

export const FLO_ACTIONS: readonly FloAction[] = [
  {
    id: 'morning-brief',
    title: 'Morning brief',
    codicon: 'sun',
    blurb: 'Top three moves, biggest risk, fastest win.',
    prompt: `Good morning. Give me my morning command brief. ${CONTRACT} Check my recent email, notes, calendar and any file status you can reach (use the google-workspace skill if it is set up), then give me: the top three moves for today, the biggest risk, and the fastest win. If you cannot reach a source, say so in one line and work with what you have.`
  },
  {
    id: 'file-check',
    title: 'File check',
    codicon: 'checklist',
    blurb: 'Where a loan stands and what moves it next.',
    prompt: `Let's check a file. Ask me which file (borrower display name) if I have not said. Then, using the flo-processing-workflow and flo-milestones skills, tell me the current milestone, what is complete, what is waiting and on whom, the only blocker right now, and the best next move. ${CONTRACT}`
  },
  {
    id: 'translate-conditions',
    title: 'Translate conditions',
    codicon: 'list-ordered',
    blurb: 'Messy lender conditions into a plain action list.',
    prompt: `I am going to paste lender or underwriter conditions. Turn each one into plain English: what they want, which document or action satisfies it, who owns it (me, borrower, LO, lender, title), and urgency. Group by owner. Use the flo-tpo-guidelines skill: if a condition depends on a guideline or overlay we do not have on file, say SOURCE_GAP and suggest the one-line AE confirmation instead of guessing. ${CONTRACT}`
  },
  {
    id: 'draft-message',
    title: 'Draft a message',
    codicon: 'mail',
    blurb: 'Borrower, LO, lender, realtor or portal note in my voice.',
    prompt: `Draft a message for me. Ask who it is for (borrower, LO, lender/AE, realtor, title, or a portal note) and what it needs to say if I have not told you. Use the flo-notes-and-emails skill for tone, and flo-compliance-messaging for anything borrower-facing that should stay to the approved template. Give me the ready-to-send version first, then one line on anything I should double-check. Do not send anything; I will.`
  },
  {
    id: 'escalation',
    title: 'Escalation help',
    codicon: 'flame',
    blurb: 'Neutral, solution-focused wording when there is friction.',
    prompt: `I have friction with a lender, LO, borrower, title company or realtor. Ask me for the short version if I have not given it. Then ground me in one line (what is actually in my control), give me one clean escalation message that is neutral and solution-focused, and tell me what to move on to next. ${CONTRACT}`
  },
  {
    id: 'eod-recap',
    title: 'End-of-day recap',
    codicon: 'moon',
    blurb: 'What moved, what is open, tomorrow set up.',
    prompt: `Give me my end-of-day wrap-up. ${CONTRACT} Look at what we worked on today (this session, recent chats, my notes and email if reachable) and tell me: what moved forward, what got cleared, what is still open and on whom, and the main carryover for tomorrow. Acknowledge the wins if they are real. Keep it to a clean summary.`
  }
]
