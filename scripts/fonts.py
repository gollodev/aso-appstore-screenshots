#!/usr/bin/env python3
"""
Cross-platform font resolver.

Resolution order for each weight:
  1. explicit path (--font / ASO_FONT_PATH / ASO_FONT_REGULAR_PATH)
  2. SF Pro Display (macOS, if installed from developer.apple.com/fonts)
  3. Inter bundled with this skill (assets/fonts, SIL OFL)
  4. common system heavy fonts (Arial Black, Helvetica Bold, DejaVu Sans Bold, Segoe UI Black)
  5. Pillow's built-in scalable default font
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

SKILL_DIR = Path(__file__).resolve().parent.parent
BUNDLED = SKILL_DIR / "assets" / "fonts"

_HOME = Path.home()
_FONT_DIRS = [
    Path("/Library/Fonts"), _HOME / "Library/Fonts", Path("/System/Library/Fonts"),
    Path("/System/Library/Fonts/Supplemental"),
    Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), _HOME / ".local/share/fonts", _HOME / ".fonts",
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
    _HOME / "AppData/Local/Microsoft/Windows/Fonts",
]

CANDIDATES = {
    "black": [
        "SF-Pro-Display-Black.otf", "SF-Pro-Display-Heavy.otf",
        str(BUNDLED / "Inter-Black.ttf"),
        "Inter-Black.ttf", "Inter-Black.otf", "InterDisplay-Black.ttf",
        "Arial Black.ttf", "ariblk.ttf", "seguibl.ttf",
        "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Helvetica.ttc",
    ],
    "regular": [
        "SF-Pro-Display-Regular.otf",
        str(BUNDLED / "Inter-Regular.ttf"),
        "Inter-Regular.ttf", "Inter-Regular.otf",
        "Arial.ttf", "arial.ttf", "segoeui.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf",
    ],
}

ENV_OVERRIDE = {"black": "ASO_FONT_PATH", "regular": "ASO_FONT_REGULAR_PATH"}


def _search(name: str) -> Path | None:
    p = Path(name)
    if p.is_absolute():
        return p if p.exists() else None
    for d in _FONT_DIRS:
        if not d.exists():
            continue
        direct = d / name
        if direct.exists():
            return direct
        # Linux distros nest fonts in sub-folders
        if str(d).startswith("/usr") or ".local" in str(d) or ".fonts" in str(d):
            for hit in d.rglob(name):
                return hit
    return None


@lru_cache(maxsize=None)
def font_path(weight: str = "black", override: str | None = None) -> str | None:
    """Return the path of the best available font for `weight`, or None for Pillow's default."""
    explicit = override or os.environ.get(ENV_OVERRIDE.get(weight, ""), "")
    if explicit:
        if Path(explicit).expanduser().exists():
            return str(Path(explicit).expanduser())
        hit = _search(explicit)
        if hit:
            return str(hit)
        print(f"⚠ font '{explicit}' not found — falling back to defaults", file=sys.stderr)
    for name in CANDIDATES[weight]:
        hit = _search(name)
        if hit:
            return str(hit)
    return None


def load(size: int, weight: str = "black", override: str | None = None) -> ImageFont.FreeTypeFont:
    path = font_path(weight, override)
    if path:
        return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


if __name__ == "__main__":
    for w in ("black", "regular"):
        print(f"{w:8} → {font_path(w) or 'Pillow default'}")
