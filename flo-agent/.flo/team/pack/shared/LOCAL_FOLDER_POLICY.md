# Local Folder Policy

## Goal

Let agents work on local loan folders without letting every bot roam the entire machine.

## Suggested root

```text
~/FloWorkspace/
  loans/
    <opaque-loan-id>/
      intake/
      aus/
      income/
      assets/
      title/
      insurance/
      conditions/
      correspondence/
      exports/
  marketing/
  templates/
  sources/
  team/
```

Do not use SSNs or full account numbers in folder names.

## Agent access

Flo:
- metadata across assigned workspaces.

Malcolm:
- loan intake, AUS, income, assets, document-review folders.

Chadwick:
- title, insurance, order-outs, approved correspondence references.

Whisper:
- correspondence, approved status facts, templates.

Sage:
- AUS, income, assets, guideline-relevant documents, source registry.

Franklin:
- marketing only.

## File mutation

- Reads may be automatic within allowed roots.
- Renames/moves should use a reversible staging pattern initially.
- Permanent deletes denied.
- External uploads require approval.
- Preserve original borrower-provided documents whenever possible.
