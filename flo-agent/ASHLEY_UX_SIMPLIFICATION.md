# Ashley-facing UX simplification (2026-09-09)

Principle: Ashley has one assistant, Flo. The backend (six profiles, handoffs, source lifecycle, provider routing, idempotency, approvals policy) is untouched and still enforces everything; only the presentation changed. Every screen must pass the five-second test: what matters, what do I do, what is being handled, what are we waiting on, is anything at risk, is there anything to approve.

## Before → after

| Before (two plugins, 9 surfaces) | After |
|---|---|
| Sidebar: **Flo** (six prompt buttons + raw audit log), **Team** (Team Floor · Deal Rooms · Approvals · Activity · Pipeline · Knowledge · Knowledge Center · Health), plus Kanban / Bots from upstream | Sidebar: **Today** · **Pipeline** · **Approvals** (one plugin, `apps/desktop/src/plugins/flo/`) |
| Home = list of prompts and tool names from the audit log | Home = Today command screen |
| Pipeline = six heat-map buckets of file names | Pipeline = one plain row per file; open a file for one summary |
| Deal Rooms tab (members, blockers/orders/drafts counts, raw activity events) | Inside the file view, in words; raw view kept under Advanced |
| Approval card: bot avatar, capability slug, workspace id, JSON payload preview, data categories, payload hash, "Open whisper's chat to decide" | What will happen · To · Flo proposes · text preview · **Approve / Edit / Not Now** |
| Team Floor, Activity log, Knowledge, Knowledge Center, Health | **Advanced** page (`/flo-team`), not in the sidebar: reachable from a small link at the bottom of Today or the command palette |

### Screens removed from Ashley's path
Team Floor, Activity, Pipeline heat map (as a screen), Knowledge, Knowledge Center, Health, the raw audit "Recent activity" list, the "viewing as <profile>" chrome, bot avatars on approval cards.

### Screens combined
* Pipeline heat map + Today priorities + risk = the **Today** screen (Top 3 / Fastest win / Biggest risk / Needs you / Waiting on others).
* Deal Rooms + File Readiness + drafts + orders = the **file view** inside Pipeline.
* Approval Center + draft review + order proposals = one **Approvals** queue (drafts still waiting for Ashley also count in "Needs you" and show inside the file with Review & Send).

### Hidden under Advanced
Team roster and direct bot chat, raw Deal Rooms, activity log, Sage's source registry, Knowledge Center (source lifecycle, checksums, activation commands, guidance, overlays), provider/model per bot. Also still hidden by construction: model routing, preflight boards, provider health states, Zapier scopes, tool names, task ids, payload hashes, policy vocabulary.

## New primary navigation

```
Today        /flo         (opens here)
Pipeline     /pipeline    (?file=<id> opens one file)
Approvals    /approvals
—
Advanced     /flo-team    (link on Today + palette; never in the sidebar)
```

## Today (home)

```
Morning Ash ☕
I’ve got the messy stuff sorted. Here’s what matters.

TOP 3
1. Bell        At Risk        Title is overdue                       [Open File]
2. Okafor      Needs Ashley   Only blocker right now: 2024 W-2 …     [Open File]
3. Mason       Needs Ashley   Checklist is clean …                   [Open File]

Fastest win: Approve: Send borrower email for Mason.
Biggest risk: Bell: Title is overdue.
Needs you: 2 things to approve or review
Waiting on others: 2 items

Everything else can wait.
[Review Approvals] [Open Pipeline] [Ask Flo]

Flo’s team is handling
  Sage is checking a guideline on Bell.
  Whisper drafted a message for Okafor.
  Malcolm checked the Okafor file.

Morning brief · End-of-day recap · Blank chat                      Advanced
```

Rules (identical in `apps/desktop/src/plugins/flo/ashley.ts` and `plugins/flo-team/today.py`, both tested):
* Status per file, worst news wins: **Blocked** (blockers / readiness BLOCKED) → **At Risk** (overdue order, Clear to Close with items missing) → **Needs Ashley** (pending approval card or a draft waiting for her) → **Done** (Closed, or ready with nothing out) → **Working** (a specialist has an open task) → **Waiting** (orders out or items owned by borrower/LO/lender/title).
* Top 3 = highest priority first (Blocked 100, At Risk 80, Needs Ashley 60, Working 20, Waiting 10; +15 when one item from done, +10 Clear to Close, +5 has a next action), most recently updated breaks ties.
* Fastest win = the newest pending approval, else the file that is one item from done.
* Biggest risk = the first Blocked / At Risk file and its reason.
* Needs you = pending approvals + drafts waiting for review. Waiting on others = orders out + missing items owned by other people.
* Team hints come only from outcome events (`readiness.updated`, `draft.added`, `order.updated`, `handoff.created/completed`, `approval.proposed`); provider transitions, role policy and task ids never appear.
* Long reasons are cut to the first sentence (≤140 chars).

## Pipeline

One row per file: `Okafor · Needs Ashley · Processing · Almost ready · Missing: 1 item / Next: … / Risk: None`. Click = the file.

## File view

```
OKAFOR   Needs Ashley   Processing                        Back to pipeline
Readiness  Almost ready   AUS  Findings on file [What does this mean?]
Income     Complete       Assets  Needs work
Orders     Nothing ordered yet     Conditions  None open

BEST NEXT MOVE  Only blocker right now: 2024 W-2 from borrower. One clean follow-up.

[Request From Borrower] [Order Title] [Order HOI] [Ask Flo]

Malcolm checked the Okafor file.  Whisper drafted a message for Okafor.

▸ Documents · 1 missing      2024 W-2  borrower  [Why?]
▸ Income & Assets            Income: Complete [Why?]  Assets: Needs work [Why?]  <discrepancies> [Why?]
▸ Conditions                 … [Why?]
▸ Orders
▸ Communication · 1 ready    borrower · 2024 W-2 request · needs attention today   [Review & Send]
```

Readiness in words (Ready / Almost ready / In progress / Not started / Blocked / Not checked yet), AUS as "Findings on file" (never "approved"), income/assets as Complete / Needs work / Not checked yet.

## Contextual actions (all go through Flo)

| Button | Ashley sees | Flo does |
|---|---|---|
| **Request From Borrower** (or Request Missing Items) | one chat opens with the draft, then a send in Approvals | Whisper drafts (`flo_draft`, idempotent), Flo proposes the send |
| **Order Title / Order HOI** (shown only when not yet ordered) | one card to approve | Chadwick proposes (`flo_order`), Ashley approves in the prompt |
| **Why?** on a missing item, condition, discrepancy, income or asset line; **What does this mean?** on AUS | why it matters, source & section, what satisfies it, any overlay, anything uncertain | Flo hands the question to Sage; Sage answers only from activated sources with the validated-response gate |
| **Ask Flo** | one clean summary | `flo_team action=file_summary` |
| **Review & Send** on a draft | the draft, then "send" → approval | Flo shows Whisper's draft and proposes the send |
| **Approve** on an approval card | the chat with the one-click confirmation waiting | Hermes' native approval prompt (binds to the exact payload) |
| **Edit** | Flo asks what to change and re-proposes | `flo_approvals action=edit` (old card invalidated) |
| **Not Now** | the card steps aside for 8 hours | local only; the card still expires on its own |

The prompts are fixed strings in `ashley.ts` (`requestPrompt`, `orderPrompt`, `whyPrompt`, `askFloPrompt`, `reviewDraftPrompt`, `editApprovalPrompt`, `NEXT_MOVE_PROMPT`) and every one opens a chat with the **flo** profile (`chat.ts: preferFloProfile`), never a specialist.

## Approvals

One queue. Card = What will happen (Send borrower email / Place an order / Publish a post / …) · file · To · Flo proposes · text preview (subject/body only) · Approve / Edit / Not Now · "Recently decided" collapsed with Done / Declined / Expired. No hashes, tool names, policy results, data categories or JSON.

## Flo's chat behaviour (SOUL + tools)

* `flo_team action=today` and `flo_team action=file_summary` give Flo the same answers as the screens, with a ready-to-say paragraph (`say_it_like`).
* SOUL: one assistant; Ashley never names a bot; "Why?" goes to Sage silently; "Request…" and "Order…" are buttons, not conversations; status words are the six plain ones; no internal machinery unless she asks; "What should I work on next?" = ONE best next move + two priorities; "Where are we on Bell?" = one clean summary.
* Morning and midday routines now call `flo_team action=today`.

## Technical/admin surfaces moved out of Ashley's way

Team Floor · direct bot chats · raw Deal Rooms · activity log · Sources · Knowledge Center (lifecycle, checksums, approvals, activation commands, diffs, impact, guidance, overlays) · Providers. All reachable at `/flo-team` (Advanced) and in the command palette ("Flo: Advanced"). Nothing was deleted from the backend.

## Still too complicated (honest)

1. **Approve is two clicks.** The card can only deep-link to the chat where Hermes' native confirmation prompt lives; approving from the card itself needs a new IPC/RPC (`approval.decide`) that the SDK does not expose. Until then the button label is "Approve" and the card explains the one extra step.
2. **Upstream chrome is still there**: Chats list, profile switcher, Bots, Kanban, Skills and Settings come from Hermes and cannot be hidden from a plugin. Ashley can ignore them, but they are visible.
3. **Buttons open a chat** rather than acting inline. It is one click plus reading Flo's reply, which is the product model ("Ashley talks to Flo"), but a fully inline "Request → draft appears → Send" would need the desktop to run a bot turn in place.
4. **Marketing** has no Ashley-facing screen (Franklin's queue lives in chat and the marketing store); a one-line "This week: N posts ready" card is the next small win if she uses it.
5. **Readiness text still comes from Malcolm's prose** on real files (first sentence only). Malcolm's SOUL should be tightened to write the `best_next_move` / discrepancy lines as one short plain sentence each.

## Next three simplifications recommended

1. **Inline approve**: a `flo.approvals.decide` RPC in the backend plugin so the Approve button decides on the card (still bound to the payload hash) and the chat prompt closes itself.
2. **Marketing card on Today** ("3 social posts ready · 1 newsletter draft · [Review Content]") fed by `flo_marketing action=calendar`, only if Ashley uses it.
3. **Malcolm's plain-English contract**: cap `best_next_move`, `missing[].item` and `discrepancies[]` to one short sentence at the tool boundary (`flo_readiness`) so the file view never needs truncation.
