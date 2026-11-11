#!/usr/bin/env python3
"""
Crop + resize images to exact store dimensions (cross-platform replacement for macOS `sips`).

AI image models generate at preset aspect ratios (9:16, 3:4, 16:9 …), never at Apple's or
Google's exact pixel sizes. This trims the excess (sides first, keeping the headline at the
top intact), resizes with Lanczos, removes any alpha channel and saves alongside the input.

    python3 fit.py --device iphone-6.9 screenshots/iphone-6.9-portrait/01-track/v1.png v2.png v3.png
    python3 fit.py --device ipad-13 --orientation landscape v1.jpg
    python3 fit.py --width 1290 --height 2796 --suffix "" --output final.png raw.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image  # noqa: E402

import devices as D  # noqa: E402
from colors import parse_color  # noqa: E402


def flatten(img: Image.Image, matte: tuple = (0, 0, 0)) -> Image.Image:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (*matte, 255))
        return Image.alpha_composite(bg, rgba).convert("RGB")
    return img.convert("RGB")


def fit(img: Image.Image, tw: int, th: int, anchor: str = "auto") -> tuple:
    """Return (fitted image, fraction of pixels cropped)."""
    w, h = img.size
    src, dst = w / h, tw / th
    if anchor == "auto":
        anchor = "top" if th >= tw else "center"
    if src > dst:  # too wide → trim sides equally
        cw = round(h * dst)
        x0 = (w - cw) // 2
        box = (x0, 0, x0 + cw, h)
    else:          # too tall → trim top/bottom per anchor
        ch = round(w / dst)
        y0 = {"top": 0, "center": (h - ch) // 2, "bottom": h - ch}[anchor]
        box = (0, y0, w, y0 + ch)
    lost = 1 - ((box[2] - box[0]) * (box[3] - box[1])) / (w * h)
    return img.crop(box).resize((tw, th), Image.LANCZOS), lost


def save(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in (".jpg", ".jpeg"):
        img.save(path, "JPEG", quality=95, subsampling=0)
    else:
        img.save(path, "PNG", optimize=True)


def main(argv=None):
    p = argparse.ArgumentParser(description="Crop/resize to exact store dimensions")
    p.add_argument("inputs", nargs="+")
    p.add_argument("--device", help="Device preset id (see devices.py)")
    p.add_argument("--orientation", choices=["portrait", "landscape"], default="portrait")
    p.add_argument("--size", help="Alternate accepted size index or WxH")
    p.add_argument("--width", type=int)
    p.add_argument("--height", type=int)
    p.add_argument("--anchor", choices=["auto", "top", "center", "bottom"], default="auto",
                   help="Where to keep content when trimming height (auto: top for portrait, center for landscape)")
    p.add_argument("--suffix", default="-resized", help="Appended to the file name (default: -resized)")
    p.add_argument("--format", choices=["png", "jpg", "same"], default="same")
    p.add_argument("--output", help="Explicit output path (single input only)")
    p.add_argument("--matte", default="000000", help="Colour used to flatten transparency (use your background colour)")
    a = p.parse_args(argv)

    if a.device:
        dev = D.get_device(a.device)
        tw, th = (dev.sizes[0] if dev.frame is None else D.resolve_size(dev, a.orientation, a.size))
    elif a.width and a.height:
        tw, th = a.width, a.height
    else:
        p.error("give --device or --width/--height")
    if a.output and len(a.inputs) > 1:
        p.error("--output only works with a single input")
    matte = parse_color(a.matte)

    for src in a.inputs:
        sp = Path(src)
        img = flatten(Image.open(sp), matte)
        out_img, lost = fit(img, tw, th, a.anchor)
        ext = sp.suffix if a.format == "same" else "." + a.format
        out = Path(a.output) if a.output else sp.with_name(f"{sp.stem}{a.suffix}{ext}")
        save(out_img, out)
        msg = f"✓ {out}  {img.width}×{img.height} → {tw}×{th}  (cropped {lost:.0%})"
        print(msg)
        ai = D.ai_aspect_ratio(tw, th)
        a_w, a_h = (int(v) for v in ai.split(":"))
        expected = max(0.0, 1 - (tw / th) / (a_w / a_h))
        if lost > expected + 0.05:
            print(f"⚠ {lost:.0%} of {src} was trimmed (expected ≈{expected:.0%}) — request aspect ratio "
                  f"{ai} from the image model next time", file=sys.stderr)


if __name__ == "__main__":
    main()
