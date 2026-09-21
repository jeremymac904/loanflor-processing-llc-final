# Flo pet

Flo uses Hermes’ existing Petdex renderer, activity store, floating window, and pop-out overlay. There is no second mascot agent or pet chatbot.

## Product-owned fallback

- `flo-badge.png` is the canonical portrait reference.
- `flo-pet-base.png` is the approved botanical Flo full-body source.
- `flo-pet-spritesheet.png` is a 9-row Petdex-compatible atlas generated from that source.
- The fallback is bundled so Flo can be visible before a local Petdex gallery is configured. A real gateway Petdex pet still wins when one is active.

## State mapping

| Flo activity | Petdex pose |
| --- | --- |
| Idle | relaxed breathing / leaf motion |
| Thinking | attentive review pose |
| Working | purposeful run pose |
| Waiting for Ashley | patient clipboard/waiting pose |
| Success | wave |
| CTC | jump / celebration |
| Error | failed / mildly annoyed pose |
| Listening | attentive review pose while voice is active |
| Speaking | active work/review pose while playback is active |

The existing activity priority remains authoritative: error, celebration, completion, waiting, tool work, reasoning, busy, idle.

## Interaction

The existing floating pet remains draggable. Shift-click uses the existing popped-out desktop overlay. Clicking the pet opens the existing small Ask Flo composer and submits through the same normal Flo session routing. Quick actions stay limited to Ask Flo, Today, Approvals, and Listen surfaces already present in Hermes.
