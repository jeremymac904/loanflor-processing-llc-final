# Knowledge Center / Sage Library (2026-09-09)

An administrator's console for the source lifecycle. Not an Ashley-chat feature: nothing on it activates a source, and the bots' `flo_knowledge action=center` is read-only.

## Data (`plugins/flo-team/knowledge_center.py`, `scripts/flo/knowledge_center.py --build`)

`<team root>/knowledge/center.json`, one row per recorded section revision (57 on this install):

Program · Source · Section (version-qualified key) · Version · Current version (in force today) · Published · Effective (+ mandatory date) · Status (lifecycle; STALE_SOURCE when the cache no longer matches the checksum) · Usable · Checksum · Revision id · Rules extracted · Regression (ok / failed anchors / receipt) · Human approval (structured identity: user id, display name, reason, environment, identity source) · Supersedes · Pending update (later versions marked FUTURE — NOT YET EFFECTIVE, or a diff snapshot) · Impact (calculators, workflows, tests, summary) · Actions.

Plus pending guidance items and overlay records.

## Desktop page (`apps/desktop/src/plugins/flo-team` → tab "Knowledge Center")

Program filter, the table above, a detail panel (source, current version and CURRENT / FUTURE / SUPERSEDED label, supersedes, human approval, impact summary, official link) and action buttons: View Source Metadata, View Extracted Rules, Compare Versions, Run Regression, Approve, Reject, Activate, Archive. Which buttons show depends on the lifecycle (`availableActions`), and each button copies the exact administrator command (the lifecycle and the identity check are enforced by the command, not the page):

```
python scripts/flo/activate_sources.py --program fha --review --only "II.A.4.c@update-18"
python scripts/flo/activate_sources.py --program fha --approve --reason "<why>" --only "II.A.4.c@update-18"
python scripts/flo/activate_sources.py --program fha --activate --only "II.A.4.c@update-18"
python scripts/flo/knowledge_center.py --diff fha
python scripts/flo/knowledge_center.py --rules freddie 5303.1
python scripts/flo/knowledge_center.py --guidance <id> --promote --reason "<why>"
python scripts/flo/knowledge_center.py --overlay <id> --activate
```

The page reads the JSON through the existing preview-read IPC (no new IPC, per the desktop decisions); it is a pure SDK consumer like the rest of the Team page.

## Status

Scaffolded and working as a read-and-copy console: the data, the lifecycle-aware action list, the impact summary and the diff are real; execution of approve/activate remains a terminal command with the approver identity (by design). A future step can wire the buttons to an authenticated desktop RPC once the auth layer exposes user ids.
