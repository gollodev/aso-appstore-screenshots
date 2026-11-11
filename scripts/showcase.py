#!/usr/bin/env python3
"""
Showcase image generator — a shareable preview of a finished screenshot set.

Places screenshots side-by-side at the same height (mixed devices and orientations are fine)
on a light background, with an optional caption/link underneath.

    python3 showcase.py --screenshots screenshots/final/iphone-6.9-portrait/*.png \
        --caption "github.com/you" --output screenshots/showcase.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image, ImageDraw  # noqa: E402

import fonts  # noqa: E402
import frames as F  # noqa: E402
from colors import auto_text_colour, parse_color  # noqa: E402

PADDING = 60
GAP = 40
BOTTOM_BAR_H = 100


def create_showcase(paths: list, output: str, caption: str | None = None, height: int = 800,
                    bg: str = "#FFFFFF", max_items: int = 6, radius: int = 0) -> None:
    images = [Image.open(p).convert("RGBA") for p in paths[:max_items]]
    if not images:
        raise SystemExit("no screenshots given")
    scaled = [im.resize((round(im.width * height / im.height), height), Image.LANCZOS) for im in images]

    total_w = sum(s.width for s in scaled) + GAP * (len(scaled) - 1) + PADDING * 2
    total_h = height + PADDING * 2 + (BOTTOM_BAR_H if caption else 0)
    bgc = parse_color(bg)
    canvas = Image.new("RGBA", (total_w, total_h), (*bgc, 255))

    x = PADDING
    for s in scaled:
        if radius:
            s.putalpha(F.rounded_mask(s.size, (0, 0, *s.size), radius))
        F.paste_rgba(canvas, s, x, PADDING)
        x += s.width + GAP

    if caption:
        d = ImageDraw.Draw(canvas)
        size = 48
        font = fonts.load(size, "regular")
        while d.textlength(caption, font=font) > total_w - PADDING * 2 and size > 16:
            size -= 2
            font = fonts.load(size, "regular")
        d.text((total_w // 2, PADDING + height + BOTTOM_BAR_H // 2), caption,
               fill=auto_text_colour(bgc), font=font, anchor="mm")

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, "PNG")
    print(f"✓ {output} ({total_w}×{total_h})")


def main(argv=None):
    p = argparse.ArgumentParser(description="Generate a showcase image")
    p.add_argument("--screenshots", nargs="+", required=True, help="Final screenshots (up to --max)")
    p.add_argument("--output", required=True)
    p.add_argument("--caption", "--github", dest="caption", help="Caption or link shown under the set")
    p.add_argument("--height", type=int, default=800, help="Height of each screenshot in the showcase")
    p.add_argument("--bg", default="#FFFFFF", help="Showcase background: #hex, rgb(), hsl() or a CSS name")
    p.add_argument("--max", type=int, default=6, dest="max_items")
    p.add_argument("--radius", type=int, default=24, help="Corner radius for each screenshot (0 = square)")
    a = p.parse_args(argv)
    create_showcase(a.screenshots, a.output, a.caption, a.height, a.bg, a.max_items, a.radius)


if __name__ == "__main__":
    main()
