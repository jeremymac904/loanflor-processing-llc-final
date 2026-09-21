"""Build Flo's bundled Petdex-compatible sprite atlas.

The source illustration is the approved Flo identity translated into a compact
full-body sidekick. This deterministic pass creates the nine existing Hermes
rows from that source without introducing a second pet renderer or agent.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance


CELL_W = 192
CELL_H = 208
COLS = 8
ROWS = 9
BASE = Path(__file__).resolve().parents[2] / "apps/desktop/src/plugins/flo/assets/flo-pet-base.png"
OUT = Path(__file__).resolve().parents[2] / "apps/desktop/src/plugins/flo/assets/flo-pet-spritesheet.png"


def fitted_base() -> Image.Image:
    source = Image.open(BASE).convert("RGBA")
    source.thumbnail((174, 194), Image.Resampling.LANCZOS)
    cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    cell.alpha_composite(source, ((CELL_W - source.width) // 2, CELL_H - source.height - 5))
    return cell


def frame(base: Image.Image, row: int, index: int) -> Image.Image:
    # Small, quiet motion keeps the pet alive without making work surfaces busy.
    dx = round(((index % 3) - 1) * 2)
    dy = -2 if index in (1, 4) else 0
    angle = 0.0
    if row in (1, 2, 7):
        angle = (-3.0, 0.0, 3.0, 1.5, -1.5, 0.0)[index % 6]
    elif row == 4:
        dy = -8 + (index % 3) * 3
        angle = (-4.0, -2.0, 0.0, 2.0, 4.0, 2.0)[index % 6]
    elif row == 5:
        angle = (-1.0, 0.0, 1.0, 0.0, -1.0, 0.0)[index % 6]
    elif row == 6:
        dx = 0
        dy = 1 if index % 2 else 0
    elif row == 8:
        dy = -1 if index % 2 else 0

    if angle:
        result = base.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)
    else:
        result = base.copy()
    if dx or dy:
        shifted = Image.new("RGBA", result.size, (0, 0, 0, 0))
        shifted.alpha_composite(result, (dx, dy))
        result = shifted

    if row == 4:  # celebration / CTC: a gentle gold-green lift
        result = ImageEnhance.Brightness(result).enhance(1.06)
    if row == 5:  # error: mildly less glow, never a sad or alarming red state
        result = ImageEnhance.Color(result).enhance(0.82)
    return result


def main() -> None:
    atlas = Image.new("RGBA", (CELL_W * COLS, CELL_H * ROWS), (0, 0, 0, 0))
    base = fitted_base()
    for row in range(ROWS):
        for index in range(COLS):
            atlas.alpha_composite(frame(base, row, index), (index * CELL_W, row * CELL_H))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(OUT, optimize=True)
    print(f"wrote {OUT} ({atlas.width}x{atlas.height})")


if __name__ == "__main__":
    main()
