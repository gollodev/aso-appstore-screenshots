#!/usr/bin/env python3
"""
Device catalog — single source of truth for store slots, exact export sizes,
programmatic frame geometry and frame skins.

Run directly to list presets:
    python3 devices.py                 # table of all presets
    python3 devices.py --info ipad-13  # details for one preset
    python3 devices.py --json          # machine-readable catalog
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional

# ── Frame geometry ──────────────────────────────────────────────────
# All ratios are relative to the device's SHORT side (body width in portrait).


@dataclass(frozen=True)
class Button:
    edge: str        # "left" | "right" | "top" (portrait orientation)
    start: float     # offset along the edge, ratio of short side, from top (or left for "top")
    length: float    # length along the edge, ratio of short side


@dataclass(frozen=True)
class FrameSpec:
    id: str
    label: str
    screen_aspect: float          # screen long side / short side
    bezel: float                  # bezel thickness
    body_radius: float            # outer corner radius
    screen_radius: float          # screen corner radius
    camera: str                   # "island" | "notch" | "punch" | "dot" | "none"
    camera_size: tuple            # (w, h) ratios; for punch/dot use (d, d)
    camera_offset: float          # distance from screen top edge (island/punch) or bezel centre (dot)
    camera_landscape: str         # where the camera ends up in landscape: "left" (phone-style) | "top" (tablet-style)
    rim: float                    # metallic rim thickness as a fraction of the bezel
    buttons: tuple = field(default_factory=tuple)
    crease: bool = False          # foldable inner display hinge line


FRAMES: dict[str, FrameSpec] = {
    "iphone": FrameSpec(
        id="iphone", label="iPhone (Dynamic Island)",
        screen_aspect=2868 / 1320, bezel=0.0180, body_radius=0.145, screen_radius=0.125,
        camera="island", camera_size=(0.310, 0.090), camera_offset=0.028,
        camera_landscape="left", rim=0.55,
        buttons=(Button("left", 0.42, 0.075), Button("left", 0.60, 0.150),
                 Button("left", 0.80, 0.150), Button("right", 0.66, 0.230)),
    ),
    "iphone-notch": FrameSpec(
        id="iphone-notch", label="iPhone (Face ID notch)",
        screen_aspect=2778 / 1284, bezel=0.0170, body_radius=0.150, screen_radius=0.125,
        camera="notch", camera_size=(0.440, 0.065), camera_offset=0.0,
        camera_landscape="left", rim=0.55,
        buttons=(Button("left", 0.36, 0.070), Button("left", 0.55, 0.140),
                 Button("left", 0.74, 0.140), Button("right", 0.60, 0.220)),
    ),
    "iphone-duo-outer": FrameSpec(
        id="iphone-duo-outer", label="Foldable phone (outer display)",
        screen_aspect=2034 / 1398, bezel=0.0200, body_radius=0.120, screen_radius=0.100,
        camera="island", camera_size=(0.200, 0.058), camera_offset=0.022,
        camera_landscape="left", rim=0.55,
        buttons=(Button("left", 0.28, 0.120), Button("left", 0.44, 0.120),
                 Button("right", 0.36, 0.160)),
    ),
    "iphone-duo-inner": FrameSpec(
        id="iphone-duo-inner", label="Foldable phone (inner display)",
        screen_aspect=2853 / 2007, bezel=0.0180, body_radius=0.075, screen_radius=0.055,
        camera="punch", camera_size=(0.032, 0.032), camera_offset=0.022,
        camera_landscape="left", rim=0.55, crease=True,
        buttons=(Button("right", 0.25, 0.110), Button("top", 0.70, 0.100)),
    ),
    "ipad": FrameSpec(
        id="ipad", label="iPad (uniform bezel)",
        screen_aspect=2752 / 2064, bezel=0.042, body_radius=0.062, screen_radius=0.038,
        camera="dot", camera_size=(0.012, 0.012), camera_offset=0.5,
        camera_landscape="top", rim=0.28,
        buttons=(Button("top", 0.78, 0.080), Button("right", 0.08, 0.070),
                 Button("right", 0.165, 0.070)),
    ),
    "android-phone": FrameSpec(
        id="android-phone", label="Android phone (punch-hole)",
        screen_aspect=20 / 9, bezel=0.0200, body_radius=0.110, screen_radius=0.090,
        camera="punch", camera_size=(0.040, 0.040), camera_offset=0.030,
        camera_landscape="left", rim=0.50,
        buttons=(Button("right", 0.42, 0.220), Button("right", 0.70, 0.110)),
    ),
    "android-tablet-7": FrameSpec(
        id="android-tablet-7", label="Android 7-inch tablet",
        screen_aspect=5 / 3, bezel=0.068, body_radius=0.085, screen_radius=0.018,
        camera="dot", camera_size=(0.022, 0.022), camera_offset=0.5,
        camera_landscape="top", rim=0.22,
        buttons=(Button("right", 0.18, 0.120), Button("right", 0.36, 0.180)),
    ),
    "android-tablet-10": FrameSpec(
        id="android-tablet-10", label="Android 10-inch tablet",
        screen_aspect=16 / 10, bezel=0.040, body_radius=0.045, screen_radius=0.014,
        camera="dot", camera_size=(0.014, 0.014), camera_offset=0.5,
        camera_landscape="top", rim=0.30,
        buttons=(Button("top", 0.12, 0.060), Button("top", 0.22, 0.120)),
    ),
}


# ── Skins ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Skin:
    id: str
    label: str
    rim_light: tuple      # highlight colour of the metallic rim (top-left)
    rim_dark: tuple       # shade colour of the metallic rim (bottom-right)
    bezel: tuple          # inner bezel colour
    button: tuple         # side button colour
    frameless: bool = False


SKINS: dict[str, Skin] = {
    "black":    Skin("black", "Black (default)", (78, 78, 82), (22, 22, 24), (8, 8, 10), (34, 34, 36)),
    "silver":   Skin("silver", "Silver / white", (244, 245, 247), (176, 179, 184), (10, 10, 12), (200, 202, 206)),
    "titanium": Skin("titanium", "Natural titanium / graphite", (186, 180, 170), (96, 92, 86), (10, 10, 12), (140, 135, 127)),
    "blue":     Skin("blue", "Deep blue", (96, 118, 150), (28, 40, 62), (8, 8, 12), (58, 76, 104)),
    "gold":     Skin("gold", "Gold", (246, 222, 178), (168, 132, 82), (10, 10, 12), (214, 184, 136)),
    "none":     Skin("none", "No frame (frameless rounded screen)", (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), frameless=True),
}

DEFAULT_SKIN = "black"


# ── Store presets ───────────────────────────────────────────────────


@dataclass(frozen=True)
class Device:
    id: str
    label: str
    platform: str                 # "ios" | "android"
    store: str                    # "App Store Connect" | "Google Play Console"
    slot: str                     # exact slot name in the store console
    sizes: tuple                  # accepted PORTRAIT sizes (w, h); first = default export
    frame: Optional[str]          # FrameSpec id, or None (no device, e.g. feature graphic)
    landscape: bool = True
    required: str = ""            # human-readable requirement note
    max_count: int = 10
    note: str = ""

    def size(self, orientation: str = "portrait", index: int = 0) -> tuple:
        w, h = self.sizes[index]
        if orientation == "landscape":
            if not self.landscape:
                raise ValueError(f"{self.id} does not support landscape")
            return (h, w) if h > w else (w, h)
        return (w, h)

    def all_sizes(self) -> list:
        out = []
        for w, h in self.sizes:
            out.append(("portrait" if h >= w else "landscape", (w, h)))
            if self.landscape and w != h:
                out.append(("landscape" if h >= w else "portrait", (h, w)))
        return out


DEVICES: dict[str, Device] = {d.id: d for d in [
    # ── Apple — iPhone ──
    Device("iphone-6.9", 'iPhone 6.9" (Dynamic Island, large)', "ios", "App Store Connect",
           "iPhone with Dynamic Island (large display) — 6.9\"",
           ((1320, 2868), (1290, 2796), (1260, 2736)), "iphone",
           required="Recommended primary iPhone size; App Store scales it down to smaller iPhones."),
    Device("iphone-6.5", 'iPhone 6.5" (Face ID, large)', "ios", "App Store Connect",
           "iPhone with Face ID (large display) — 6.5\"",
           ((1284, 2778), (1242, 2688)), "iphone-notch",
           required="Required only if you don't provide 6.9\" screenshots."),
    Device("iphone-6.3", 'iPhone 6.3" (Dynamic Island, medium)', "ios", "App Store Connect",
           "iPhone with Dynamic Island (medium display) — 6.1\"/6.3\"",
           ((1206, 2622), (1179, 2556)), "iphone",
           required="Apple lists this as the required iPhone slot when larger sizes are absent."),
    Device("iphone-duo-outer", "iPhone Duo (outer display)", "ios", "App Store Connect",
           "iPhone Duo — outer display", ((1398, 2034),), "iphone-duo-outer",
           required="Required for apps built with the iOS 27.1 SDK or later (from April 2027)."),
    Device("iphone-duo-inner", "iPhone Duo (inner display)", "ios", "App Store Connect",
           "iPhone Duo — inner display", ((2007, 2853),), "iphone-duo-inner",
           required="Required for apps built with the iOS 27.1 SDK or later (from April 2027)."),
    # ── Apple — iPad ──
    Device("ipad-13", 'iPad 13"', "ios", "App Store Connect", 'iPad 13" display',
           ((2064, 2752), (2048, 2732)), "ipad",
           required="Required if the app runs on iPad."),
    Device("ipad-11", 'iPad 11"', "ios", "App Store Connect", 'iPad 11" display',
           ((1668, 2388), (1640, 2360), (1668, 2420), (1488, 2266), (1512, 2316)), "ipad",
           required="Optional — App Store scales 13\" screenshots when missing."),
    # ── Google Play ──
    Device("android-phone", "Android phone", "android", "Google Play Console", "Phone screenshots",
           ((1080, 1920), (1440, 2560)), "android-phone", max_count=8,
           required="At least 2 screenshots; 4+ at ≥1080px 9:16 to be eligible for promotional placements."),
    Device("android-tablet-7", 'Android 7" tablet', "android", "Google Play Console", "7-inch tablet screenshots",
           ((1440, 2560), (1080, 1920)), "android-tablet-7", max_count=8,
           required="Optional; 4+ screenshots recommended for large-screen visibility."),
    Device("android-tablet-10", 'Android 10" tablet', "android", "Google Play Console", "10-inch tablet screenshots",
           ((2160, 3840), (1440, 2560)), "android-tablet-10", max_count=8,
           required="Optional; 4+ screenshots recommended for large-screen visibility."),
    Device("play-feature-graphic", "Google Play feature graphic", "android", "Google Play Console", "Feature graphic",
           ((1024, 500),), None, landscape=False, max_count=1,
           required="Required to publish a Play store listing.",
           note="Use scripts/feature_graphic.py, not compose.py."),
]}

DEVICE_ALIASES = {
    "iphone": "iphone-6.9", "iphone-6.7": "iphone-6.9", "iphone-6.1": "iphone-6.3",
    "ipad": "ipad-13", "ipad-12.9": "ipad-13",
    "android": "android-phone", "phone": "android-phone",
    "tablet-7": "android-tablet-7", "tablet-10": "android-tablet-10",
    "android-7": "android-tablet-7", "android-10": "android-tablet-10",
    "feature-graphic": "play-feature-graphic",
}

# Google Play rules for screenshots
PLAY_MIN_SIDE = 320
PLAY_MAX_SIDE = 3840
PLAY_MAX_BYTES = 8 * 1024 * 1024
PLAY_BANNED_WORDS = ["best", "#1", "no. 1", "number one", "top", "new", "discount", "sale",
                     "million downloads", "free", "download now", "install now", "play now",
                     "try now", "award", "ranked", "editor's choice"]

# Aspect ratios supported by Nano Banana (Gemini image models)
AI_ASPECT_RATIOS = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]


def get_device(device_id: str) -> Device:
    key = DEVICE_ALIASES.get(device_id, device_id)
    if key not in DEVICES:
        raise SystemExit(f"Unknown device '{device_id}'. Choose one of: {', '.join(DEVICES)}")
    return DEVICES[key]


def get_frame(frame_id: str) -> FrameSpec:
    return FRAMES[frame_id]


def get_skin(skin_id: str) -> Skin:
    if skin_id not in SKINS:
        raise SystemExit(f"Unknown skin '{skin_id}'. Choose one of: {', '.join(SKINS)}")
    return SKINS[skin_id]


def resolve_size(device: Device, orientation: str, size: Optional[str]) -> tuple:
    """Resolve "--size" (index, or "WxH") against the device's accepted sizes."""
    if not size:
        return device.size(orientation, 0)
    if "x" in size.lower():
        w, h = (int(v) for v in size.lower().split("x"))
        accepted = [s for _, s in device.all_sizes()]
        if (w, h) not in accepted:
            raise SystemExit(f"{w}x{h} is not an accepted size for {device.id}. Accepted: "
                             + ", ".join(f"{a}x{b}" for a, b in accepted))
        return (w, h)
    return device.size(orientation, int(size))


def ai_aspect_ratio(width: int, height: int) -> str:
    """Closest Nano Banana aspect ratio that is at least as wide as the target,
    so the post-processing crop trims the sides (preserving the headline at the top)."""
    target = width / height
    best, best_err = None, 1e9
    for r in AI_ASPECT_RATIOS:
        a, b = (int(x) for x in r.split(":"))
        ratio = a / b
        if ratio + 1e-6 < target:
            continue
        err = abs(math.log(ratio / target))
        if err < best_err:
            best, best_err = r, err
    return best or "21:9"


def _table() -> str:
    rows = [("id", "store slot", "portrait", "landscape", "frame")]
    for d in DEVICES.values():
        p = d.size("portrait")
        land = f"{p[1]}x{p[0]}" if d.landscape else "—"
        port = f"{p[0]}x{p[1]}"
        if d.id == "play-feature-graphic":
            port, land = "—", "1024x500"
        rows.append((d.id, d.slot, port, land, d.frame or "none"))
    widths = [max(len(r[i]) for r in rows) for i in range(5)]
    lines = ["  ".join(c.ljust(widths[i]) for i, c in enumerate(r)) for r in rows]
    lines.insert(1, "  ".join("-" * w for w in widths))
    lines.append("\nSkins: " + ", ".join(SKINS))
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description="List device presets and skins")
    p.add_argument("--info", help="Show full details for a device id")
    p.add_argument("--json", action="store_true", help="Dump catalog as JSON")
    args = p.parse_args(argv)

    if args.json:
        print(json.dumps({
            "devices": {k: asdict(v) for k, v in DEVICES.items()},
            "frames": {k: asdict(v) for k, v in FRAMES.items()},
            "skins": {k: asdict(v) for k, v in SKINS.items()},
        }, indent=2))
        return
    if args.info:
        d = get_device(args.info)
        print(f"{d.label}  [{d.id}]")
        print(f"  Store:     {d.store} → {d.slot}")
        print(f"  Required:  {d.required}")
        print(f"  Max count: {d.max_count}")
        print(f"  Frame:     {d.frame or 'none'}")
        for orient, (w, h) in d.all_sizes():
            print(f"  {orient:<9}  {w}x{h}   (AI aspect ratio: {ai_aspect_ratio(w, h)})")
        if d.note:
            print(f"  Note:      {d.note}")
        return
    print(_table())


if __name__ == "__main__":
    sys.exit(main())
