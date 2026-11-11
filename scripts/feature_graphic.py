#!/usr/bin/env python3
"""
Google Play feature graphic composer (exactly 1024×500, RGB, no alpha).

    python3 feature_graphic.py --bg "#2563EB" --verb TRACK --desc "TRADING CARD PRICES" \
        --icon app-icon.png --output screenshots/final/play-feature-graphic.png
    python3 feature_graphic.py --bg "#2563EB" --verb TRACK --desc "CARD PRICES" \
        --screenshot sim.png --output fg.png      # adds a frameless app screen on the right

Google Play may overlay a play button in the centre when a promo video exists and crops
edges in some placements — keep the message large and away from the outer edges.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image, ImageDraw  # noqa: E402

import frames as F  # noqa: E402
from colors import auto_text_colour, check_contrast, parse_color  # noqa: E402
from compose import draw_text, layout_text  # noqa: E402

W, H = 1024, 500


def main(argv=None):
    p = argparse.ArgumentParser(description="Compose a Google Play feature graphic (1024×500)")
    p.add_argument("--bg", required=True, help="Background colour: #hex, rgb(), hsl() or a CSS name")
    p.add_argument("--verb", required=True)
    p.add_argument("--desc", default="")
    p.add_argument("--icon", help="App icon (square PNG) shown left of the headline")
    p.add_argument("--screenshot", help="Optional app screen shown on the right (frameless)")
    p.add_argument("--text-color")
    p.add_argument("--font")
    p.add_argument("--output", required=True)
    a = p.parse_args(argv)

    bg = parse_color(a.bg)
    fg = parse_color(a.text_color) if a.text_color else auto_text_colour(bg)
    check_contrast(bg, fg, "feature graphic")
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    text_x0, text_x1 = 70, W - 70
    if a.screenshot:
        text_x1 = int(W * 0.60)
        sw, sh = 300, 560
        sx, sy = W - sw - 70, 70
        shot = F.fit_cover(Image.open(a.screenshot).convert("RGBA"), sw, sh, "top")
        F.drop_shadow(canvas, (sx, sy, sx + sw, sy + sh), 34, sw)
        shot.putalpha(F.rounded_mask((sw, sh), (0, 0, sw, sh), 34))
        F.paste_rgba(canvas, shot, sx, sy)

    icon = None
    if a.icon:
        isz = 150
        icon = Image.open(a.icon).convert("RGBA").resize((isz, isz), Image.LANCZOS)
        icon.putalpha(F.rounded_mask((isz, isz), (0, 0, isz, isz), isz * 0.22))

    gap = 36
    text_w = (text_x1 - text_x0) - ((icon.width + gap) if icon else 0)
    rows, th = layout_text(a.verb, a.desc, text_w, 110, 60, 52, a.font)
    widths = [ImageDraw.Draw(canvas).textlength(r[0], font=r[1]) for r in rows]
    block_w = max(widths) + ((icon.width + gap) if icon else 0)
    x = text_x0 + ((text_x1 - text_x0) - block_w) / 2
    if icon:
        F.drop_shadow(canvas, (int(x), (H - icon.height) // 2, int(x) + icon.width, (H + icon.height) // 2),
                      int(icon.width * 0.22), icon.width, 0.3)
        F.paste_rgba(canvas, icon, int(x), (H - icon.height) // 2)
        x += icon.width + gap
    draw_text(canvas, rows, x + max(widths) / 2, (H - th) / 2, fg)

    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    rgb = canvas.convert("RGB")
    rgb.save(out, "JPEG", quality=95) if out.suffix.lower() in (".jpg", ".jpeg") else rgb.save(out, "PNG")
    print(f"✓ {out}  ({W}×{H}, Google Play feature graphic)")


if __name__ == "__main__":
    main()
