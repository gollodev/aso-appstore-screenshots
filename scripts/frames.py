#!/usr/bin/env python3
"""
Programmatic device frame renderer.

Frames are generic illustrations (no logos or trademarked artwork) drawn from the
geometry in devices.py. Rendering is fully deterministic, so every screenshot in a
set gets a pixel-identical frame, for every device class, skin and orientation.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from devices import FrameSpec, Skin

SS = 2  # supersampling factor for anti-aliased edges


@dataclass
class RenderedDevice:
    overlay: Image.Image        # RGBA: body + bezel + camera; screen area transparent
    body_box: tuple             # (x0, y0, x1, y1) inside overlay
    screen_box: tuple           # (x0, y0, x1, y1) inside overlay
    screen_radius: int
    body_radius: int


def body_size(spec: FrameSpec, short: float, orientation: str) -> tuple:
    bezel = short * spec.bezel
    long = (short - 2 * bezel) * spec.screen_aspect + 2 * bezel
    return (short, long) if orientation == "portrait" else (long, short)


def body_aspect(spec: FrameSpec, orientation: str) -> float:
    """height / width of the device body."""
    w, h = body_size(spec, 1000.0, orientation)
    return h / w


def rounded_mask(size: tuple, box: tuple, radius: float, ss: int = SS) -> Image.Image:
    """Anti-aliased rounded-rectangle mask."""
    w, h = size
    big = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(big).rounded_rectangle(
        [box[0] * ss, box[1] * ss, box[2] * ss - 1, box[3] * ss - 1],
        radius=max(0, radius * ss), fill=255)
    return big.resize((w, h), Image.LANCZOS)


def _gradient(size: tuple, light: tuple, dark: tuple) -> Image.Image:
    """Diagonal metallic gradient (light top-left → dark bottom-right) with a soft mid sheen."""
    w, h = size
    v = Image.linear_gradient("L").resize((w, h))
    hz = Image.linear_gradient("L").rotate(90, expand=True).transpose(Image.Transpose.FLIP_LEFT_RIGHT).resize((w, h))
    g = ImageChops.add(v.point(lambda i: i * 0.6), hz.point(lambda i: i * 0.4))
    sheen = Image.linear_gradient("L").resize((w, h)).point(lambda i: int(40 * max(0.0, 1 - abs(i - 90) / 40)))
    g = ImageChops.subtract(g, sheen)
    return ImageOps.colorize(g, black=light, white=dark).convert("RGBA")


def _rot_box(box: tuple, src_w: int) -> tuple:
    """Box transform for a 90° counter-clockwise rotation of an image of width src_w."""
    x0, y0, x1, y1 = box
    return (y0, src_w - x1, y1, src_w - x0)


def render_overlay(spec: FrameSpec, skin: Skin, short: int, orientation: str) -> RenderedDevice:
    s = short * SS
    b = s * spec.bezel
    sw = s - 2 * b
    sl = sw * spec.screen_aspect
    L = sl + 2 * b
    prot = max(3.0 * SS, s * 0.006)          # side-button protrusion
    pad = int(round(prot + 2 * SS))
    W, H = int(round(s + 2 * pad)), int(round(L + 2 * pad))

    body = (pad, pad, pad + s, pad + L)
    screen = (pad + b, pad + b, pad + b + sw, pad + b + sl)
    body_r = spec.body_radius * s
    screen_r = spec.screen_radius * s

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    if not skin.frameless:
        d = ImageDraw.Draw(img)
        # Side buttons sit behind the body
        for btn in spec.buttons:
            a0, a1 = btn.start * s, (btn.start + btn.length) * s
            if btn.edge == "left":
                r = (body[0] - prot, body[1] + a0, body[0] + 4 * SS, body[1] + a1)
            elif btn.edge == "right":
                r = (body[2] - 4 * SS, body[1] + a0, body[2] + prot, body[1] + a1)
            else:  # top
                r = (body[0] + a0, body[1] - prot, body[0] + a1, body[1] + 4 * SS)
            d.rounded_rectangle(r, radius=prot, fill=(*skin.button, 255))

        # Metallic rim
        body_mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(body_mask).rounded_rectangle(body, radius=body_r, fill=255)
        img = Image.composite(_gradient((W, H), skin.rim_light, skin.rim_dark), img, body_mask)
        d = ImageDraw.Draw(img)

        # Edge highlight
        hl = tuple(min(255, c + 40) for c in skin.rim_light)
        d.rounded_rectangle(body, radius=body_r, outline=(*hl, 150), width=max(1, int(s * 0.0025)))

        # Inner bezel
        rim_w = max(2.0 * SS, b * spec.rim)
        inner = (body[0] + rim_w, body[1] + rim_w, body[2] - rim_w, body[3] - rim_w)
        d.rounded_rectangle(inner, radius=max(screen_r, body_r - rim_w), fill=(*skin.bezel, 255))

        # Screen cut-out
        hole = Image.new("L", (W, H), 255)
        ImageDraw.Draw(hole).rounded_rectangle(screen, radius=screen_r, fill=0)
        img.putalpha(ImageChops.multiply(img.getchannel("A"), hole))
        d = ImageDraw.Draw(img)

        # Camera
        cam_on_side = orientation == "landscape" and spec.camera_landscape == "top"
        cx = (screen[0] + screen[2]) / 2
        cw, ch = spec.camera_size[0] * s, spec.camera_size[1] * s
        if spec.camera == "island":
            y0 = screen[1] + spec.camera_offset * s
            d.rounded_rectangle((cx - cw / 2, y0, cx + cw / 2, y0 + ch), radius=ch / 2, fill=(0, 0, 0, 255))
            lens = ch * 0.42
            lx = cx + cw / 2 - ch / 2
            d.ellipse((lx - lens / 2, y0 + ch / 2 - lens / 2, lx + lens / 2, y0 + ch / 2 + lens / 2),
                      fill=(18, 20, 30, 255))
        elif spec.camera == "notch":
            r = ch * 0.55
            d.rounded_rectangle((cx - cw / 2, screen[1] - 2 * SS, cx + cw / 2, screen[1] + ch),
                                radius=r, fill=(*skin.bezel, 255), corners=(False, False, True, True))
        elif spec.camera == "punch":
            y0 = screen[1] + spec.camera_offset * s
            d.ellipse((cx - cw / 2, y0, cx + cw / 2, y0 + cw), fill=(4, 4, 6, 255))
            d.ellipse((cx - cw * 0.22, y0 + cw * 0.28, cx + cw * 0.22, y0 + cw * 0.72), fill=(22, 26, 40, 255))
        elif spec.camera == "dot":
            if cam_on_side:  # right edge in portrait becomes the top edge after rotating to landscape
                px, py = (screen[2] + body[2]) / 2, (body[1] + body[3]) / 2
            else:
                px, py = cx, (body[1] + screen[1]) / 2
            d.ellipse((px - cw / 2, py - cw / 2, px + cw / 2, py + cw / 2), fill=(26, 26, 32, 255))
            d.ellipse((px - cw * 0.25, py - cw * 0.25, px + cw * 0.25, py + cw * 0.25), fill=(46, 52, 74, 255))

        # Foldable hinge crease (drawn above the screen, very subtle)
        if spec.crease:
            crease = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            cd = ImageDraw.Draw(crease)
            mid = (screen[0] + screen[2]) / 2
            half = s * 0.006
            cd.rectangle((mid - half, screen[1], mid, screen[3]), fill=(0, 0, 0, 22))
            cd.rectangle((mid, screen[1], mid + half, screen[3]), fill=(255, 255, 255, 18))
            img = Image.alpha_composite(img, crease)

    out_w, out_h = int(round(W / SS)), int(round(H / SS))
    overlay = img.resize((out_w, out_h), Image.LANCZOS)
    sc = lambda box: tuple(int(round(v / SS)) for v in box)
    body_box, screen_box = sc(body), sc(screen)

    if orientation == "landscape":
        overlay = overlay.transpose(Image.Transpose.ROTATE_90)
        body_box, screen_box = _rot_box(body_box, out_w), _rot_box(screen_box, out_w)

    return RenderedDevice(overlay, body_box, screen_box,
                          int(round(screen_r / SS)), int(round(body_r / SS)))


def paste_rgba(canvas: Image.Image, layer: Image.Image, x: int, y: int) -> None:
    """alpha_composite that tolerates negative offsets and overflow."""
    cx0, cy0 = max(0, x), max(0, y)
    cx1, cy1 = min(canvas.width, x + layer.width), min(canvas.height, y + layer.height)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    crop = layer.crop((cx0 - x, cy0 - y, cx1 - x, cy1 - y))
    canvas.alpha_composite(crop, dest=(cx0, cy0))


def fit_cover(img: Image.Image, w: int, h: int, anchor: str = "top") -> Image.Image:
    scale = max(w / img.width, h / img.height)
    nw, nh = max(w, round(img.width * scale)), max(h, round(img.height * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    x0 = (nw - w) // 2
    y0 = 0 if anchor == "top" else (nh - h) // 2
    return img.crop((x0, y0, x0 + w, y0 + h))


def drop_shadow(canvas: Image.Image, box: tuple, radius: int, short: int, strength: float = 0.38) -> None:
    """Soft shadow under a rounded box (computed at 1/4 scale for speed)."""
    k = 4
    blur = max(2, int(short * 0.035 / k))
    off = int(short * 0.018)
    w, h = canvas.width // k + 1, canvas.height // k + 1
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        [box[0] / k, (box[1] + off) / k, box[2] / k, (box[3] + off) / k], radius=radius / k, fill=int(255 * strength))
    m = m.filter(ImageFilter.GaussianBlur(blur)).resize(canvas.size, Image.BILINEAR)
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow.putalpha(m)
    canvas.alpha_composite(shadow)


def place_device(canvas: Image.Image, spec: FrameSpec, skin: Skin, orientation: str, short: int,
                 x: int, y: int, screenshot: Image.Image | None, shadow: bool = False) -> tuple:
    """Draw a device whose BODY top-left corner is at (x, y). Returns the body box on the canvas."""
    rd = render_overlay(spec, skin, short, orientation)
    ox, oy = x - rd.body_box[0], y - rd.body_box[1]
    body = tuple(v + o for v, o in zip(rd.body_box, (ox, oy, ox, oy)))
    scr = tuple(v + o for v, o in zip(rd.screen_box, (ox, oy, ox, oy)))

    if shadow:
        drop_shadow(canvas, body if not skin.frameless else scr,
                    rd.body_radius if not skin.frameless else rd.screen_radius, short)

    # Screen content — slightly larger than the hole when framed so no background leaks at AA edges
    grow = 0 if skin.frameless else 2
    sx0, sy0, sx1, sy1 = scr[0] - grow, scr[1] - grow, scr[2] + grow, scr[3] + grow
    sw, sh = sx1 - sx0, sy1 - sy0
    layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 255))
    if screenshot is not None:
        content = fit_cover(screenshot.convert("RGBA"), sw, sh, "top" if orientation == "portrait" else "center")
        layer.alpha_composite(content)
    layer.putalpha(rounded_mask((sw, sh), (0, 0, sw, sh), rd.screen_radius + grow))
    paste_rgba(canvas, layer, sx0, sy0)

    paste_rgba(canvas, rd.overlay, ox, oy)
    return body


def load_custom_frame(path: str) -> tuple:
    """Load a user-supplied frame PNG with a transparent screen; return (image, screen_box, screen_mask)."""
    frame = Image.open(path).convert("RGBA")
    alpha = frame.getchannel("A").point(lambda a: 255 if a < 128 else 0)
    probe = alpha.copy()
    cx, cy = frame.width // 2, frame.height // 2
    if probe.getpixel((cx, cy)) != 255:
        raise SystemExit(f"{path}: the centre of the frame is not transparent — cannot detect the screen area")
    ImageDraw.floodfill(probe, (cx, cy), 128)
    mask = probe.point(lambda a: 255 if a == 128 else 0).filter(ImageFilter.MaxFilter(5))
    return frame, mask.getbbox(), mask
