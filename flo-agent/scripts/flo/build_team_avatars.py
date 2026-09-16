#!/usr/bin/env python3
"""Integrate the owner-approved Flo Team visual assets into their permanent locations.

    python scripts/flo/build_team_avatars.py

Source of truth (approved 2026-09-08, see .flo/assets/team/GENERATED_ASSET_REPORT.md
and ASSET_MANIFEST.yaml): ``.flo/assets/team/<name>/{1024,512,256,128,64}.png``
(square masters, opaque ivory background), ``.flo/assets/team/app_icon/``
(transparent PNG sizes, ``flo.ico``, ``flo.iconset/``) and
``.flo/assets/team/flo_team_banner_16x9.png``.

Outputs (all derived with a centered circular mask, never regenerated):

* ``.flo/assets/team/<name>/circle-{512,256,128,64}.png`` — RGBA circular crops.
* ``.flo/profile/<name>/assets/avatar.png`` — the Hermes profile avatar
  (512 circular RGBA PNG, < 2MB) served through ``profiles.get_asset`` to the
  Bots pane, chat sender icons and task assignments.
* ``apps/desktop/public/team/<name>-{256,128,64}.png`` — circular icons for
  the Team page and any future chat/task surfaces that need a static path.
* ``apps/desktop/public/flo-team-banner.png`` — 1280x720 copy of the banner.
* App icon: ``apps/desktop/assets/icon.png`` (1024 transparent),
  ``icon.ico`` (the delivered multi-frame ICO, copied verbatim),
  ``icon.icns`` (built from the delivered iconset PNGs with Pillow's ICNS
  writer — the same tooling the brand pass used; signing settings untouched),
  ``apps/desktop/public/apple-touch-icon.png`` (180),
  ``apps/desktop/public/flo-badge.png`` (512) + the Flo home header badge,
  ``apps/desktop/public/flo-face.png`` (brand mark = circular Flo 256).

Nothing here touches crop-review sheets, review sheets or archived artwork.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
TEAM_ASSETS = REPO / ".flo" / "assets" / "team"
PROFILES = REPO / ".flo" / "profile"
DESKTOP = REPO / "apps" / "desktop"
PUBLIC_TEAM = DESKTOP / "public" / "team"
NAMES = ("flo", "malcolm", "chadwick", "whisper", "sage", "franklin")
CIRCLE_SIZES = (512, 256, 128, 64)


def circle_crop(img: Image.Image, size: int) -> Image.Image:
    """Centered circular crop with anti-aliased edge (supersampled mask)."""
    img = img.convert("RGBA")
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    square = img.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
    scale = 4
    mask = Image.new("L", (size * scale, size * scale), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * scale - 1, size * scale - 1), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(square, (0, 0), mask)
    return out


def build_portraits() -> None:
    PUBLIC_TEAM.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        master = TEAM_ASSETS / name / "1024.png"
        if not master.exists():
            raise SystemExit(f"missing approved master {master}")
        src = Image.open(master)
        assert src.size == (1024, 1024), f"{master} is {src.size}, expected 1024x1024"
        for size in CIRCLE_SIZES:
            circle_crop(src, size).save(TEAM_ASSETS / name / f"circle-{size}.png", optimize=True)
        avatar = PROFILES / name / "assets" / "avatar.png"
        avatar.parent.mkdir(parents=True, exist_ok=True)
        circle_crop(src, 512).save(avatar, optimize=True)
        assert avatar.stat().st_size < 2_000_000, f"{avatar} exceeds Hermes' 2MB asset cap"
        for size in (256, 128, 64):
            circle_crop(src, size).save(PUBLIC_TEAM / f"{name}-{size}.png", optimize=True)
        print(f"{name}: avatar {avatar.stat().st_size} bytes; public/team/{name}-{{256,128,64}}.png")


def build_app_icon() -> None:
    icon_dir = TEAM_ASSETS / "app_icon"
    master = Image.open(icon_dir / "flo_app_icon_1024.png").convert("RGBA")
    assert master.size == (1024, 1024)
    assets = DESKTOP / "assets"
    master.save(assets / "icon.png", optimize=True)
    shutil.copyfile(icon_dir / "flo.ico", assets / "icon.ico")
    # ICNS from the delivered iconset sources (Pillow packs the sizes it needs from the 1024 master).
    master.save(assets / "icon.icns", format="ICNS")
    master.resize((180, 180), Image.LANCZOS).save(DESKTOP / "public" / "apple-touch-icon.png", optimize=True)
    master.resize((512, 512), Image.LANCZOS).save(DESKTOP / "public" / "flo-badge.png", optimize=True)
    master.resize((256, 256), Image.LANCZOS).save(DESKTOP / "src" / "plugins" / "flo" / "flo-badge.png", optimize=True)
    # Brand mark (sidebar/About): the circular Flo portrait.
    circle_crop(Image.open(TEAM_ASSETS / "flo" / "1024.png"), 256).save(DESKTOP / "public" / "flo-face.png", optimize=True)
    print("app icon: assets/icon.png, icon.ico (delivered), icon.icns (Pillow), apple-touch-icon, flo-badge, flo-face")


def build_banner() -> None:
    banner = Image.open(TEAM_ASSETS / "flo_team_banner_16x9.png").convert("RGB")
    assert banner.size == (2048, 1152)
    banner.resize((1280, 720), Image.LANCZOS).save(DESKTOP / "public" / "flo-team-banner.png", optimize=True)
    print("banner: public/flo-team-banner.png (1280x720)")


def main() -> int:
    build_portraits()
    build_app_icon()
    build_banner()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
