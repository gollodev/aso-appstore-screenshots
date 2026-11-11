#!/usr/bin/env python3
"""
Export programmatic device frames as PNGs and build preview galleries.

    python3 generate_frames.py                      # galleries → assets/frames/gallery-*.jpg
    python3 generate_frames.py --export out/frames  # every frame × skin × orientation as transparent PNGs
    python3 generate_frames.py --export out --device android-tablet-7 --skin silver --orientation landscape

Exported frames have a transparent screen, so they can also be used in Figma/Sketch
or passed back to compose.py with --frame-image.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image, ImageDraw  # noqa: E402

import devices as D  # noqa: E402
import fonts  # noqa: E402
import frames as F  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "frames"


def placeholder(w: int, h: int) -> Image.Image:
    g = Image.linear_gradient("L").resize((w, h))
    return Image.merge("RGB", (g.point(lambda i: 40 + i // 3), g.point(lambda i: 90 + i // 4), Image.new("L", (w, h), 230)))


def export(out: Path, device_ids: list, skins: list, orientations: list, short: int | None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    seen = set()
    for did in device_ids:
        dev = D.get_device(did)
        if not dev.frame:
            continue
        spec = D.get_frame(dev.frame)
        for orient in orientations:
            if orient == "landscape" and not dev.landscape:
                continue
            cw, ch = dev.size(orient)
            s = short or int(min(cw, ch) * 0.8)
            for sk in skins:
                key = (spec.id, orient, sk, s)
                if key in seen:
                    continue
                seen.add(key)
                rd = F.render_overlay(spec, D.get_skin(sk), s, orient)
                path = out / f"{spec.id}-{sk}-{orient}.png"
                rd.overlay.save(path)
                print(f"✓ {path}  {rd.overlay.size}  screen={rd.screen_box}")


def gallery(orientation: str, path: Path, cell: int = 260) -> None:
    specs = list(D.FRAMES.values())
    skins = list(D.SKINS.values())
    label_w, head_h, pad = 360, 70, 40
    sizes = [F.body_size(sp, cell, orientation) for sp in specs]
    row_h = [int(s[1]) + pad for s in sizes]
    col_w = int(max(s[0] for s in sizes)) + pad
    W = label_w + col_w * len(skins) + pad
    H = head_h + sum(row_h) + pad
    img = Image.new("RGBA", (W, H), (236, 238, 243, 255))
    d = ImageDraw.Draw(img)
    fb, fr = fonts.load(26, "black"), fonts.load(22, "regular")
    for j, sk in enumerate(skins):
        d.text((label_w + j * col_w + col_w // 2, head_h // 2), sk.id, font=fb, fill=(30, 30, 30), anchor="mm")
    y = head_h
    for sp, (bw, bh), rh in zip(specs, sizes, row_h):
        d.text((24, y + rh // 2 - 14), sp.id, font=fb, fill=(30, 30, 30), anchor="lm")
        d.text((24, y + rh // 2 + 18), sp.label, font=fr, fill=(90, 90, 90), anchor="lm")
        for j, sk in enumerate(skins):
            x = label_w + j * col_w + (col_w - int(bw)) // 2
            short = cell
            screen = placeholder(int(bw), int(bh))
            F.place_device(img, sp, sk, orientation, short, x, y + (rh - int(bh)) // 2, screen, sk.frameless)
        y += rh
    path.parent.mkdir(parents=True, exist_ok=True)
    rgb = img.convert("RGB")
    if path.suffix.lower() in (".jpg", ".jpeg"):
        rgb.thumbnail((1600, 2400), Image.LANCZOS)
        rgb.save(path, "JPEG", quality=86, optimize=True)
    else:
        rgb.save(path, optimize=True)
    print(f"✓ {path}  ({W}×{H})")


def main(argv=None):
    p = argparse.ArgumentParser(description="Export device frames / build galleries")
    p.add_argument("--export", help="Directory for transparent frame PNGs")
    p.add_argument("--device", action="append", help="Device id (repeatable; default: all)")
    p.add_argument("--skin", action="append", help="Skin id (repeatable; default: all)")
    p.add_argument("--orientation", action="append", choices=["portrait", "landscape"])
    p.add_argument("--short", type=int, help="Short-side size in px (default: 80%% of the device canvas)")
    p.add_argument("--gallery-dir", default=str(ASSETS), help="Where to write gallery images")
    a = p.parse_args(argv)

    if a.export:
        export(Path(a.export), a.device or list(D.DEVICES), a.skin or list(D.SKINS),
               a.orientation or ["portrait", "landscape"], a.short)
        return
    gallery("portrait", Path(a.gallery_dir) / "gallery-portrait.jpg")
    gallery("landscape", Path(a.gallery_dir) / "gallery-landscape.jpg", cell=200)


if __name__ == "__main__":
    main()
