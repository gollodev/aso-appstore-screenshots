#!/usr/bin/env python3
"""
Colour parsing and contrast helpers shared by every script.

Accepted colour formats (case-insensitive):
  #2563EB · 2563EB · #26E · rgb(37, 99, 235) · hsl(221, 83%, 53%) · CSS names (tomato, navy, rebeccapurple …)

CLI — normalise colours and check headline contrast:
    python3 colors.py "#2563EB" tomato "rgb(15,118,110)" "hsl(45, 100%, 60%)"
    python3 colors.py --text "#FFFFFF" "#FDE68A"
"""

from __future__ import annotations

import argparse
import re
import sys

from PIL import ImageColor

DARK_TEXT = (17, 17, 17)
LIGHT_TEXT = (255, 255, 255)
MIN_CONTRAST = 3.0   # WCAG AA for large text — headlines are always large


def parse_color(value) -> tuple:
    """Return an (r, g, b) tuple for any supported colour notation."""
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return tuple(int(v) for v in value[:3])
    s = str(value).strip()
    if re.fullmatch(r"[0-9a-fA-F]{3}|[0-9a-fA-F]{6}", s):
        s = "#" + s
    try:
        rgb = ImageColor.getrgb(s)
    except ValueError:
        raise SystemExit(f"Invalid colour '{value}'. Use #RRGGBB, rgb(r, g, b), hsl(h, s%, l%) or a CSS colour name.")
    return tuple(rgb[:3])


def to_hex(rgb: tuple) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb[:3])


def luminance(rgb: tuple) -> float:
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: tuple, b: tuple) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def auto_text_colour(bg: tuple) -> tuple:
    """White or near-black, whichever reads better on `bg`."""
    return DARK_TEXT if contrast_ratio(bg, DARK_TEXT) > contrast_ratio(bg, LIGHT_TEXT) else LIGHT_TEXT


def check_contrast(bg: tuple, fg: tuple, label: str = "") -> float:
    """Warn on stderr when headline contrast is below WCAG AA for large text."""
    ratio = contrast_ratio(bg, fg)
    if ratio < MIN_CONTRAST:
        where = f" ({label})" if label else ""
        better = to_hex(auto_text_colour(bg))
        print(f"⚠ low contrast{where}: text {to_hex(fg)} on {to_hex(bg)} is {ratio:.1f}:1 "
              f"(aim for ≥ {MIN_CONTRAST:.0f}:1) — try --text-color {better} or a different background",
              file=sys.stderr)
    return ratio


def main(argv=None):
    p = argparse.ArgumentParser(description="Normalise colours and check headline contrast")
    p.add_argument("colors", nargs="+", help="Background colours in any supported format")
    p.add_argument("--text", help="Headline colour to check against (default: automatic white/near-black)")
    a = p.parse_args(argv)
    for c in a.colors:
        bg = parse_color(c)
        fg = parse_color(a.text) if a.text else auto_text_colour(bg)
        ratio = contrast_ratio(bg, fg)
        status = "OK " if ratio >= MIN_CONTRAST else "LOW"
        print(f"{c:<24} → {to_hex(bg)}  text {to_hex(fg)}  contrast {ratio:4.1f}:1  [{status}]")


if __name__ == "__main__":
    main()
