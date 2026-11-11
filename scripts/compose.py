#!/usr/bin/env python3
"""
Store Screenshot Composer (scaffold generator)

Composites a headline (action verb + benefit descriptor), a programmatic device
frame and an app screenshot into a pixel-exact store image for any preset in
devices.py: iPhone, iPad, Android phone, Android 7"/10" tablet, iPhone Duo —
portrait or landscape, with selectable frame skins and any custom background colour
(#hex, rgb(), hsl() or a CSS colour name — set per set, per device or per screenshot).

Single image:
    python3 compose.py --device iphone-6.9 --bg "#2563EB" --verb TRACK \
        --desc "TRADING CARD PRICES" --screenshot sim.png --output out.png

Batch (one command for a whole set across devices):
    python3 compose.py --batch screenshots/compose.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image, ImageDraw  # noqa: E402

import devices as D  # noqa: E402
import fonts  # noqa: E402
import frames as F  # noqa: E402
from colors import auto_text_colour, check_contrast, parse_color, to_hex  # noqa: E402


# ── helpers ─────────────────────────────────────────────────────────

_MEASURE = ImageDraw.Draw(Image.new("RGB", (1, 1)))


def text_w(text: str, font) -> float:
    return _MEASURE.textlength(text, font=font)


def cap_h(font) -> int:
    box = font.getbbox("H", anchor="ls")
    return -box[1]


def wrap(text: str, font, max_w: float) -> list:
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if text_w(test, font) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def layout_text(verb: str, desc: str, max_w: float, verb_max: int, verb_min: int,
                desc_size: int, font_override: str | None) -> tuple:
    """Return ([(line, font, cap_height)], total_height, verb_desc_gap_px, line_gaps)."""
    verb, desc = verb.upper().strip(), desc.upper().strip()

    size = verb_max
    while size > verb_min and text_w(verb, fonts.load(size, "black", font_override)) > max_w:
        size -= 4
    vfont = fonts.load(size, "black", font_override)
    vlines = wrap(verb, vfont, max_w)

    dsize = desc_size
    dfont = fonts.load(dsize, "black", font_override)
    dlines = wrap(desc, dfont, max_w) if desc else []
    while len(dlines) > 3 and dsize > desc_size * 0.7:
        dsize -= 4
        dfont = fonts.load(dsize, "black", font_override)
        dlines = wrap(desc, dfont, max_w)

    vcap, dcap = cap_h(vfont), cap_h(dfont)
    rows = [(l, vfont, vcap, int(vcap * 0.22)) for l in vlines]
    if dlines:
        rows[-1] = (*rows[-1][:3], int(vcap * 0.24))
        rows += [(l, dfont, dcap, int(dcap * 0.32)) for l in dlines]
    total = sum(r[2] for r in rows) + sum(r[3] for r in rows[:-1])
    return rows, total


def draw_text(canvas: Image.Image, rows: list, cx: float, top: float, colour: tuple) -> float:
    d = ImageDraw.Draw(canvas)
    y = top
    for i, (line, font, ch, gap) in enumerate(rows):
        y += ch
        d.text((cx, y), line, font=font, fill=(*colour, 255), anchor="ms")
        if i < len(rows) - 1:
            y += gap
    return y


def warn(msg: str) -> None:
    print(f"⚠ {msg}", file=sys.stderr)


# ── composition ─────────────────────────────────────────────────────

def compose(device_id: str, bg_color: str, verb: str, desc: str, screenshot: str | None, output: str,
            orientation: str = "portrait", size: str | None = None, skin_id: str = D.DEFAULT_SKIN,
            text_colour: str | None = None, font: str | None = None, layout: str = "auto",
            bleed: bool = True, shadow: bool | None = None, frame_image: str | None = None) -> str:
    dev = D.get_device(device_id)
    if dev.frame is None:
        raise SystemExit(f"{dev.id} has no device frame — use feature_graphic.py instead")
    W, H = D.resolve_size(dev, orientation, size)
    orientation = "portrait" if H >= W else "landscape"
    spec = D.get_frame(dev.frame)
    skin = D.get_skin(skin_id)
    if shadow is None:
        shadow = skin.frameless
    if layout == "auto":
        layout = "top" if orientation == "portrait" else "side"

    bg = parse_color(bg_color)
    fg = parse_color(text_colour) if text_colour else auto_text_colour(bg)
    check_contrast(bg, fg, "/".join(Path(output).parts[-3:]))
    canvas = Image.new("RGBA", (W, H), (*bg, 255))

    shot = None
    if screenshot:
        shot = Image.open(screenshot)
        if orientation == "portrait" and shot.width > shot.height * 1.1:
            warn(f"{screenshot} is landscape but the target is portrait — it will be cropped")
        if orientation == "landscape" and shot.height > shot.width * 1.1:
            warn(f"{screenshot} is portrait but the target is landscape — capture a landscape screenshot")
        if not frame_image:
            shot_aspect = max(shot.size) / min(shot.size)
            if abs(shot_aspect / spec.screen_aspect - 1) > 0.12:
                warn(f"{screenshot} aspect {shot_aspect:.2f} differs from the {spec.label} screen "
                     f"({spec.screen_aspect:.2f}) — it will be cropped to fill. Capture it on a matching "
                     f"simulator/emulator for best results.")

    custom = F.load_custom_frame(frame_image) if frame_image else None
    aspect = (custom[0].height / custom[0].width) if custom else F.body_aspect(spec, orientation)

    if layout == "top":
        u = min(W, H * 0.46)
        rows, th = layout_text(verb, desc, W * 0.86, int(u * 0.20), int(u * 0.11), int(u * 0.096), font)
        text_top = H * 0.07
        draw_text(canvas, rows, W / 2, text_top, fg)
        dev_y = max(H * 0.2575, text_top + th + u * 0.06)
        avail = H - dev_y
        lo = 0.60 if orientation == "portrait" else 0.40
        if bleed:
            dev_w = min(max((avail / 0.93) / aspect, W * lo), W * 0.90)
        else:
            dev_w = min((avail - H * 0.04) / aspect, W * 0.84)
        dev_h = dev_w * aspect
        dev_x = (W - dev_w) / 2
    else:  # side: text column on the left, device bleeding off the right edge
        col0, col1 = W * 0.05, W * 0.41
        cw = col1 - col0
        vmax = int(min(H * 0.15, cw * 0.24))
        rows, th = layout_text(verb, desc, cw, vmax, int(vmax * 0.55), int(vmax * 0.48), font)
        draw_text(canvas, rows, (col0 + col1) / 2, (H - th) / 2, fg)
        dev_h = H * 0.80
        dev_w = dev_h / aspect
        dev_x = W * 0.45
        if (W - dev_x) / dev_w < 0.75:  # keep at least 75% of the device visible
            dev_w = (W - dev_x) / 0.75
            dev_h = dev_w * aspect
        if not bleed and dev_x + dev_w > W * 0.96:
            dev_w = W * 0.96 - dev_x
            dev_h = dev_w * aspect
        dev_y = (H - dev_h) / 2

    if custom:
        frame_img, sbox, smask = custom
        scale = dev_w / frame_img.width
        size = (int(round(dev_w)), int(round(frame_img.height * scale)))
        fimg = frame_img.resize(size, Image.LANCZOS)
        sx0, sy0, sx1, sy1 = (int(round(v * scale)) for v in sbox)
        x, y = int(round(dev_x)), int(round(dev_y))
        if shadow:
            F.drop_shadow(canvas, (x, y, x + fimg.width, y + fimg.height), int(fimg.width * 0.1), min(fimg.size))
        layer = Image.new("RGBA", size, (0, 0, 0, 255))
        if shot is not None:
            layer.alpha_composite(F.fit_cover(shot.convert("RGBA"), sx1 - sx0, sy1 - sy0,
                                              "top" if orientation == "portrait" else "center"), dest=(sx0, sy0))
        layer.putalpha(smask.resize(size, Image.LANCZOS))
        F.paste_rgba(canvas, layer, x, y)
        F.paste_rgba(canvas, fimg, x, y)
    else:
        short = dev_w if orientation == "portrait" else dev_h
        F.place_device(canvas, spec, skin, orientation, int(round(short)),
                       int(round(dev_x)), int(round(dev_y)), shot, shadow)

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    rgb = canvas.convert("RGB")
    if out.suffix.lower() in (".jpg", ".jpeg"):
        rgb.save(out, "JPEG", quality=95, subsampling=0)
    else:
        rgb.save(out, "PNG", optimize=True)
    print(f"✓ {out}  ({W}×{H}, {dev.id}, {orientation}, bg={to_hex(bg)}, "
          f"skin={skin.id if not custom else 'custom'})")
    return str(out)


# ── batch ───────────────────────────────────────────────────────────

def _group_keys(dev: D.Device, orientation: str) -> tuple:
    return (f"{dev.id}:{orientation}", dev.id, f"{dev.platform}:{orientation}", dev.platform, "default")


def _pick_screenshot(item: dict, dev: D.Device, orientation: str) -> str | None:
    shots = item.get("screenshots", {})
    for key in _group_keys(dev, orientation):
        if key in shots:
            return shots[key]
    return item.get("screenshot")


def _pick_value(key: str, item: dict, target: dict, cfg: dict, dev: D.Device, orientation: str):
    """Resolve a per-screenshot setting. Precedence: item (string, or dict keyed by
    device:orientation → device → platform:orientation → platform → default) → target → top level."""
    v = item.get(key)
    if isinstance(v, dict):
        for k in _group_keys(dev, orientation):
            if k in v:
                return v[k]
    elif v is not None:
        return v
    return target.get(key, cfg.get(key))


def run_batch(path: str) -> None:
    cfg = json.loads(Path(path).read_text())
    base = Path(path).parent
    out_dir = Path(cfg.get("out_dir", "screenshots"))
    targets = cfg.get("targets") or [{"device": "iphone-6.9", "orientation": "portrait"}]
    done = 0
    for t in targets:
        dev = D.get_device(t["device"])
        orient = t.get("orientation", "portrait")
        for item in cfg["items"]:
            shot = _pick_screenshot(item, dev, orient)
            if shot and not Path(shot).is_absolute() and not Path(shot).exists():
                shot = str(base / shot)
            out = out_dir / f"{dev.id}-{orient}" / item["slug"] / t.get("filename", cfg.get("filename", "scaffold.png"))
            bg = _pick_value("bg", item, t, cfg, dev, orient)
            if not bg:
                raise SystemExit(f"{item['slug']}: no background colour — set \"bg\" at the top level, "
                                 f"on the target or on the item")
            compose(dev.id, bg, item.get("verb", ""), item.get("desc", ""), shot, str(out),
                    orientation=orient, size=t.get("size"), skin_id=t.get("skin", cfg.get("skin", D.DEFAULT_SKIN)),
                    text_colour=_pick_value("text_color", item, t, cfg, dev, orient), font=cfg.get("font"),
                    layout=t.get("layout", cfg.get("layout", "auto")),
                    bleed=t.get("bleed", cfg.get("bleed", True)), shadow=t.get("shadow", cfg.get("shadow")),
                    frame_image=t.get("frame_image", cfg.get("frame_image")))
            done += 1
    print(f"✓ batch complete — {done} image(s)")


def main(argv=None):
    p = argparse.ArgumentParser(description="Compose a store screenshot scaffold for any device preset")
    p.add_argument("--batch", help="JSON batch file (see README → compose.py batch format)")
    p.add_argument("--device", default="iphone-6.9", help="Device preset id (python3 devices.py lists them)")
    p.add_argument("--orientation", choices=["portrait", "landscape"], default="portrait")
    p.add_argument("--size", help="Alternate accepted size: index (0,1,..) or WxH, e.g. 1290x2796")
    p.add_argument("--skin", default=D.DEFAULT_SKIN, choices=list(D.SKINS), help="Frame skin")
    p.add_argument("--bg", help="Background colour: #E31837, rgb(227,24,55), hsl(352,81%%,49%%) or a CSS name")
    p.add_argument("--verb", help="Action verb (line 1), e.g. TRACK")
    p.add_argument("--desc", default="", help="Benefit descriptor (line 2), e.g. TRADING CARD PRICES")
    p.add_argument("--screenshot", help="App screenshot (simulator/emulator capture)")
    p.add_argument("--output", help="Output path (.png or .jpg)")
    p.add_argument("--text-color", help="Headline colour (default: auto white/near-black by contrast)")
    p.add_argument("--font", help="Path or file name of a heavy font (default: SF Pro Display Black → Inter Black)")
    p.add_argument("--layout", choices=["auto", "top", "side"], default="auto",
                   help="auto = top for portrait, side for landscape")
    p.add_argument("--no-bleed", action="store_true", help="Show the whole device instead of bleeding off the edge")
    p.add_argument("--shadow", dest="shadow", action="store_true", default=None, help="Soft drop shadow under device")
    p.add_argument("--no-shadow", dest="shadow", action="store_false")
    p.add_argument("--frame-image", help="Custom frame PNG with a transparent screen (overrides --skin)")
    a = p.parse_args(argv)

    if a.batch:
        run_batch(a.batch)
        return
    missing = [n for n in ("bg", "verb", "output") if not getattr(a, n)]
    if missing:
        p.error("missing required arguments: " + ", ".join("--" + m for m in missing))
    compose(a.device, a.bg, a.verb, a.desc, a.screenshot, a.output, a.orientation, a.size, a.skin,
            a.text_color, a.font, a.layout, not a.no_bleed, a.shadow, a.frame_image)


if __name__ == "__main__":
    main()
