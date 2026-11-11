#!/usr/bin/env python3
"""
Store-compliance validator for App Store Connect and Google Play screenshots.

Checks: exact accepted dimensions, no alpha channel, file format, Google Play size/ratio
limits and file-size cap, per-slot screenshot counts, and Google Play tagline policy.

    python3 validate.py screenshots/final                      # every device folder, auto-detected
    python3 validate.py --device android-phone shot1.png shot2.png
    python3 validate.py --headline "BEST APP TO TRACK PRICES" --platform android
    python3 validate.py --json screenshots/final

Exit code 1 if any check FAILS (warnings don't fail).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image  # noqa: E402

import devices as D  # noqa: E402

IMAGE_EXT = {".png", ".jpg", ".jpeg"}


def matching_devices(w: int, h: int) -> list:
    return [d.id for d in D.DEVICES.values() if (w, h) in [s for _, s in d.all_sizes()]]


def lint_headline(text: str) -> list:
    issues = []
    low = text.lower()
    for word in D.PLAY_BANNED_WORDS:
        if re.search(r"(?<![\w#])" + re.escape(word) + r"(?!\w)", low):
            issues.append(f'Google Play discourages "{word}" in screenshot text (rankings, promos, CTAs)')
    return issues


def check_file(path: Path, device: str | None) -> dict:
    res = {"file": str(path), "fail": [], "warn": [], "ok": []}
    try:
        img = Image.open(path)
        img.load()
    except Exception as e:  # noqa: BLE001
        res["fail"].append(f"cannot open image: {e}")
        return res
    w, h = img.size
    res["size"] = f"{w}x{h}"
    fmt = (img.format or "").upper()
    if fmt not in ("PNG", "JPEG"):
        res["fail"].append(f"format {fmt or '?'} — stores accept PNG or JPEG only")
    has_alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)
    if has_alpha:
        res["fail"].append(f"image has an alpha channel ({img.mode}) — re-save as RGB (fit.py does this)")
    else:
        res["ok"].append("no alpha channel")

    matches = matching_devices(w, h)
    if device:
        dev = D.get_device(device)
        if dev.id in matches:
            res["ok"].append(f"{w}x{h} accepted for {dev.slot}")
        else:
            accepted = ", ".join(f"{a}x{b}" for _, (a, b) in dev.all_sizes())
            res["fail"].append(f"{w}x{h} is not accepted for {dev.id} (accepted: {accepted})")
        targets = [dev]
    else:
        if matches:
            res["ok"].append(f"{w}x{h} matches: {', '.join(matches)}")
        else:
            res["fail"].append(f"{w}x{h} does not match any App Store / Google Play preset")
        targets = [D.DEVICES[m] for m in matches]
    res["devices"] = [t.id for t in targets]

    if any(t.platform == "android" for t in targets):
        short, long = min(w, h), max(w, h)
        size = path.stat().st_size
        if targets and all(t.id == "play-feature-graphic" for t in targets):
            pass
        else:
            if short < D.PLAY_MIN_SIDE or long > D.PLAY_MAX_SIDE:
                res["fail"].append(f"Google Play needs sides between {D.PLAY_MIN_SIDE} and {D.PLAY_MAX_SIDE}px")
            if long > 2 * short:
                res["fail"].append("Google Play: the long side can't exceed 2× the short side")
            if short < 1080 or abs(long / short - 16 / 9) > 0.01:
                res["warn"].append("not eligible for Play promotional formats (needs ≥1080px at exactly 9:16 / 16:9)")
        if size > D.PLAY_MAX_BYTES:
            res["fail"].append(f"file is {size / 1e6:.1f} MB — Google Play's limit is 8 MB (save as JPEG)")
    return res


def expand(paths: list) -> list:
    out = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            out += sorted(f for f in pp.rglob("*") if f.suffix.lower() in IMAGE_EXT and "showcase" not in f.name)
        elif pp.exists():
            out.append(pp)
        else:
            out.append(pp)
    return out


def device_from_path(path: Path) -> str | None:
    for part in reversed(path.parts[:-1]):
        for dev in D.DEVICES:
            if part == dev or part.startswith(dev + "-portrait") or part.startswith(dev + "-landscape"):
                return dev
    return None


def main(argv=None):
    p = argparse.ArgumentParser(description="Validate store screenshots")
    p.add_argument("paths", nargs="*", help="Files or folders (folders are scanned recursively)")
    p.add_argument("--device", help="Expected device preset for all files")
    p.add_argument("--headline", action="append", default=[], help="Headline text to lint (repeatable)")
    p.add_argument("--platform", choices=["ios", "android", "both"], default="both",
                   help="Which store's text policy to apply to --headline")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    results = []
    groups: dict = {}
    for f in expand(a.paths):
        if not f.exists():
            results.append({"file": str(f), "fail": ["file not found"], "warn": [], "ok": []})
            continue
        dev = a.device or device_from_path(f)
        r = check_file(f, dev)
        results.append(r)
        if dev:
            groups.setdefault((D.get_device(dev).id, f.parent), []).append(f)

    counts = []
    for (dev_id, folder), files in groups.items():
        dev = D.DEVICES[dev_id]
        n = len(files)
        entry = {"folder": str(folder), "device": dev_id, "count": n, "fail": [], "warn": []}
        if n > dev.max_count:
            entry["fail"].append(f"{n} screenshots — {dev.store} allows at most {dev.max_count} for {dev.slot}")
        if dev.platform == "android" and dev.frame and n < 4:
            entry["warn"].append("Google Play recommends at least 4 screenshots per device type")
        counts.append(entry)

    text = []
    if a.platform in ("android", "both"):
        for hl in a.headline:
            for issue in lint_headline(hl):
                text.append({"headline": hl, "warn": issue})

    failed = any(r["fail"] for r in results) or any(c["fail"] for c in counts)
    if a.json:
        print(json.dumps({"files": results, "counts": counts, "text": text, "passed": not failed}, indent=2))
    else:
        for r in results:
            status = "FAIL" if r["fail"] else ("WARN" if r["warn"] else "PASS")
            print(f"[{status}] {r['file']}  {r.get('size', '')}")
            for m in r["fail"]:
                print(f"   ✗ {m}")
            for m in r["warn"]:
                print(f"   ⚠ {m}")
        for c in counts:
            for m in c["fail"]:
                print(f"[FAIL] {c['folder']}: {m}")
            for m in c["warn"]:
                print(f"[WARN] {c['folder']}: {m}")
        for t in text:
            print(f"[WARN] \"{t['headline']}\": {t['warn']}")
        print("\n" + ("✗ validation failed" if failed else "✓ all checks passed"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
