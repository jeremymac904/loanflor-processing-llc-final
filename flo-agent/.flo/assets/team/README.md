# Flo Team visual assets (owner-approved, 2026-09-08)

Source package: `Flo_Team_Agents_Pack/avatars` (report: `GENERATED_ASSET_REPORT.md`,
mappings: `ASSET_MANIFEST.yaml`, inventory: `ASSET_INVENTORY.json`, prompts:
`GENERATION_PROMPTS_*.json`, `GENERATION_SOURCES.json` — all copied here).

Approved direction: warm wood skin, reflective brown eyes, leafy green hair,
friendly dimensional mascot illustration. This supersedes the earlier
semi-realistic green-skinned direction. Characters are not redesigned or
regenerated here; every derivative is a resample or a centered circular crop.

| Path | What | Used by |
|---|---|---|
| `<name>/1024.png` | approved master (`{name}_master_1024.png`) | source of every derivative |
| `<name>/{512,256,128,64}.png` | delivered square sizes | reference |
| `<name>/circle-{512,256,128,64}.png` | centered circular crops (RGBA) | built by `scripts/flo/build_team_avatars.py` |
| `app_icon/flo_app_icon_*.png`, `flo.ico`, `flo.iconset/` | delivered app icon set (transparent) | `apps/desktop/assets/icon.{png,ico,icns}`, `public/apple-touch-icon.png`, `public/flo-badge.png` |
| `flo_team_banner_16x9.png` | delivered 2048x1152 banner | `apps/desktop/public/flo-team-banner.png` (1280x720) |

Installed into the application by `python scripts/flo/build_team_avatars.py`:

- `.flo/profile/<name>/assets/avatar.png` — 512 circular RGBA PNG; the Hermes
  profile avatar (`profiles.get_asset`) shown in the Bots pane roster, group
  chat rows and inter-agent delivery notices. (Not 160x160: that size is
  reserved by upstream for its auto-backfilled SVG faces and would be ignored.)
- `apps/desktop/public/team/<name>-{256,128,64}.png` — circular icons for the
  Team page (Team Floor cards, Approval Center cards).
- `apps/desktop/public/flo-face.png` — brand mark (About panel, install/update
  overlays, first-run form) = circular Flo 256.
- `apps/desktop/src/plugins/flo/flo-badge.png` — Flo home header (app icon 256).
- `apps/desktop/assets/icon.ico` is the delivered multi-frame ICO copied
  verbatim; `icon.icns` is packed by Pillow from the 1024 transparent master
  (the delivered `flo.iconset/` PNGs are retained for `iconutil` on macOS).
  Signing settings in `apps/desktop/package.json` were not touched.

Not shipped: `generated/archive/`, `*_crop_review.png`, review sheets.

Superseded: six portraits generated earlier in the same session with the
owner-connected Higgsfield tool (nano_banana_pro; 12 credits) were replaced by
this approved package and are not retained in the repository.
