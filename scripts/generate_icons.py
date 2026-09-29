"""Generate the ScamSense PWA icon set.

Run from the repository root:

    python scripts/generate_icons.py

Produces apps/web/public/icons/*.png. Everything is drawn with Pillow only, so
the icons are reproducible and no binary blobs have to be maintained by hand.
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

OUT_DIR = os.path.join("apps", "web", "public", "icons")

BACKGROUND = (11, 18, 32, 255)       # deep navy, matches --card-bg
SHIELD_EDGE = (56, 189, 248, 255)     # sky-400
SHIELD_FILL = (12, 32, 56, 255)
ACCENT = (34, 197, 94, 255)           # green-500 for the check
SIZE = 1024


def _shield_points(margin, inset):
    left = margin + inset
    right = SIZE - margin - inset
    top = margin + inset
    bottom = SIZE - margin - inset
    mid = (left + right) / 2.0
    return [
        (left, top + inset * 0.8),
        (mid, top),
        (right, top + inset * 0.8),
        (right, top + (bottom - top) * 0.52),
        (mid, bottom),
        (left, top + (bottom - top) * 0.52),
    ]


def _scaled_points(points, scale):
    mid = SIZE / 2.0
    return [(mid + (x - mid) * scale, mid + (y - mid) * scale) for x, y in points]


def _draw_icon(size, padding_ratio):
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    radius = int(SIZE * 0.22)
    draw.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=radius, fill=BACKGROUND)

    scale = 1.0 - padding_ratio * 2
    shield = _scaled_points(_shield_points(int(SIZE * 0.22), int(SIZE * 0.04)), scale)

    draw.polygon(shield, fill=SHIELD_FILL, outline=SHIELD_EDGE, width=int(SIZE * 0.035))
    inner = _scaled_points(shield, 0.82)
    draw.polygon(inner, outline=SHIELD_EDGE, width=int(SIZE * 0.012))

    cx, cy = SIZE / 2.0, SIZE * 0.5
    draw.line(
        [
            (cx - SIZE * 0.13, cy - SIZE * 0.01),
            (cx - SIZE * 0.03, cy + SIZE * 0.10),
            (cx + SIZE * 0.16, cy - SIZE * 0.12),
        ],
        fill=ACCENT,
        width=int(SIZE * 0.055),
        joint="curve",
    )

    return image.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    targets = {
        "icon-192.png": (192, 0.0),
        "icon-512.png": (512, 0.0),
        "icon-maskable-512.png": (512, 0.10),
        "apple-touch-icon.png": (180, 0.04),
        "favicon-64.png": (64, 0.0),
    }
    for name, (size, padding) in targets.items():
        path = os.path.join(OUT_DIR, name)
        _draw_icon(size, padding).save(path, "PNG", optimize=True)
        print("wrote", path)


if __name__ == "__main__":
    main()