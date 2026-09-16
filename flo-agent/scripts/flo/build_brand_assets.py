"""Cut the owner-supplied Flo / LoanFlow branding sheet into app assets.

Input: a 2x2 sheet with transparent background — top-left Flo with laptop,
top-right Flo face, bottom-left circular Flo badge, bottom-right LoanFlow
Processing LLC logo. Output (all PNG with alpha unless noted):

  .flo/assets/originals/<sheet>.png            untouched copy
  .flo/assets/flo-full.png / flo-face.png / flo-badge.png / loanflow-logo.png
  apps/desktop/assets/icon.png (1024)  icon.ico  icon.icns      app icon = badge
  apps/desktop/public/apple-touch-icon.png (512)                 window icon
  apps/desktop/public/flo-face.png (512)                         BrandMark tile
  apps/desktop/public/flo-badge.png (512)                        empty state / home
  apps/desktop/public/loanflow-logo.png                          about / onboarding
  apps/desktop/src/plugins/flo/flo-badge.png (512)               Flo home header
  .flo/assets/palette.json                                       colours sampled from the logo

Usage: python scripts/flo/build_brand_assets.py <sheet.png>
"""

from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
DESKTOP = REPO / "apps" / "desktop"
FLO_ASSETS = REPO / ".flo" / "assets"


def trim(img: Image.Image) -> Image.Image:
    """Drop the low-alpha halo the generator left around each element, then crop."""
    r, g, b, a = img.split()
    cleaned = Image.merge("RGBA", (r, g, b, a.point(lambda v: 0 if v < 40 else v)))
    bbox = cleaned.split()[-1].point(lambda v: 255 if v > 64 else 0).getbbox()
    return cleaned.crop(bbox) if bbox else cleaned


def square(img: Image.Image, size: int, pad: float = 0.0) -> Image.Image:
    """Fit onto a transparent square canvas of `size`, keeping aspect."""
    w, h = img.size
    scale = (size * (1 - pad)) / max(w, h)
    resized = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(resized, ((size - resized.width) // 2, (size - resized.height) // 2), resized)
    return canvas


def palette(img: Image.Image, n: int = 8) -> list[str]:
    small = img.convert("RGBA").resize((160, 160))
    counts: Counter[tuple[int, int, int]] = Counter()
    for r, g, b, a in small.getdata():
        if a < 200:
            continue
        counts[(r // 8 * 8, g // 8 * 8, b // 8 * 8)] += 1
    return ["#%02x%02x%02x" % rgb for rgb, _ in counts.most_common(n)]


def main(sheet_path: str) -> None:
    sheet = Image.open(sheet_path).convert("RGBA")
    w, h = sheet.size
    quads = {
        "flo-full": sheet.crop((0, 0, w // 2, h // 2)),
        "flo-face": sheet.crop((w // 2, 0, w, h // 2)),
        "flo-badge": sheet.crop((0, h // 2, w // 2, h)),
        "loanflow-logo": sheet.crop((w // 2, h // 2, w, h)),
    }
    parts = {name: trim(img) for name, img in quads.items()}

    (FLO_ASSETS / "originals").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(sheet_path, FLO_ASSETS / "originals" / Path(sheet_path).name)
    for name, img in parts.items():
        img.save(FLO_ASSETS / f"{name}.png")
        print(f"{name}: {img.size}")

    badge = parts["flo-badge"]
    icon_1024 = square(badge, 1024)
    (DESKTOP / "assets").mkdir(exist_ok=True)
    icon_1024.save(DESKTOP / "assets" / "icon.png")
    icon_1024.save(DESKTOP / "assets" / "icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    square(badge, 512).save(DESKTOP / "assets" / "icon.icns", format="ICNS")

    public = DESKTOP / "public"
    square(badge, 512).save(public / "apple-touch-icon.png")
    square(parts["flo-face"], 512, pad=0.04).save(public / "flo-face.png")
    square(badge, 512).save(public / "flo-badge.png")
    logo = parts["loanflow-logo"]
    logo.save(public / "loanflow-logo.png")
    square(badge, 512).save(DESKTOP / "src" / "plugins" / "flo" / "flo-badge.png")

    pal = {
        "logo": palette(logo),
        "flo": palette(parts["flo-face"]),
        "chosen": {
            "green_deep": "#1f5a2d",
            "green_leaf": "#3f8f3a",
            "green_light": "#8fbf8a",
            "gold": "#b8964a",
            "gold_light": "#d8c08a",
            "cream": "#f3ead6",
            "bark": "#a7794a",
        },
    }
    (FLO_ASSETS / "palette.json").write_text(json.dumps(pal, indent=2), encoding="utf-8")
    print("palette:", pal["logo"][:6])


if __name__ == "__main__":
    main(sys.argv[1])
