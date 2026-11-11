# AGENTS.md — working on the `aso-appstore-screenshots` skill

This repository **is** an Agent Skill (open `SKILL.md` standard) used by Claude Code and GitHub Copilot. These notes
are for agents/contributors changing the skill itself — not for running it (that's `SKILL.md`).

## Architecture

- `SKILL.md` — the workflow prompt (Recall → Benefits → Platforms & Devices → Pairing → Brand colour → Generation →
  Feature graphic & Showcase). Must stay **agent-neutral**: no Claude-only or Copilot-only tool names without an
  equivalent for the other agent. State lives in the user's project at `screenshots/aso-state.json`.
- `scripts/devices.py` — **single source of truth** for store slots, accepted sizes, frame geometry (`FrameSpec`),
  skins and Google Play rules. Every other script reads from it; never hard-code sizes elsewhere.
- `scripts/frames.py` — programmatic, deterministic frame renderer. Draws in portrait at 2× supersampling, then
  downsamples and (for landscape) rotates 90° CCW losslessly. Overlay = body + bezel + camera with a transparent
  screen; the screenshot is composited underneath.
- `scripts/compose.py` — layout engine (portrait "top" layout, landscape "side" layout), single and `--batch` modes.
- `scripts/colors.py` — the only place colours are parsed (hex, `rgb()`, `hsl()`, CSS names) and contrast is
  checked. Every script that takes a colour must use `parse_color()`; never parse hex by hand.
- `scripts/fit.py`, `scripts/validate.py`, `scripts/feature_graphic.py`, `scripts/showcase.py`,
  `scripts/generate_frames.py`, `scripts/fonts.py` — see README §10.
- `install.sh` / `install.ps1` — copy the skill to `~/.claude/skills`, `~/.copilot/skills`, `~/.agents/skills` (or
  project `.claude/` `.github/` `.agents/`), create the shared venv **outside** the skill folders
  (`~/.local/share/aso-appstore-screenshots/venv`, `%LOCALAPPDATA%\…` on Windows), optional MCP wiring, self-test.

## Invariants (don't break these)

1. Every output image is **RGB, no alpha, at an exact accepted store size** from `devices.py`.
2. Frames contain **no logos or trademarked artwork**.
3. Scripts depend only on **Pillow** and the standard library; Python ≥ 3.9 (use `from __future__ import annotations`).
4. Scripts must work on macOS, Linux and Windows — no `sips`, no hard-coded font paths (use `fonts.py`).
5. Nothing large or generated goes inside the skill folder at install time (no `.venv`, no caches) — agents index
   every file in a skill directory.
6. `install.ps1` is saved as **UTF-8 with BOM** (Windows PowerShell 5.1 misreads BOM-less UTF-8).
7. Keep the README's device tables, `SKILL.md`'s target table and `devices.py` in sync.
8. Backgrounds are solid colours. Colour precedence in batch mode is item → target → top level; keep README §4.3
   and `SKILL.md` Phase 4 in sync with `compose.py`.

## Commands

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt        # dev environment
.venv/bin/python scripts/devices.py                                       # list presets
.venv/bin/python scripts/generate_frames.py                               # rebuild assets/frames/gallery-*.jpg
.venv/bin/python scripts/compose.py --device android-tablet-7 --orientation landscape --skin silver \
  --bg "#0F766E" --verb SEARCH --desc "ANY CARD" --screenshot examples/sample-android-tablet-landscape.png --output /tmp/t.png
.venv/bin/python scripts/validate.py /tmp/t.png
bash -n install.sh                                                        # shell syntax
HOME=$(mktemp -d) ./install.sh --all                                      # installer test without touching your real HOME
```

## Adding a device preset

1. Add a `FrameSpec` (if the device class is new) and a `Device` entry in `scripts/devices.py` with the store's
   exact accepted sizes (default first).
2. Render it in both orientations and every skin: `scripts/generate_frames.py`, then look at the galleries.
3. Run `compose.py` + `validate.py` on it.
4. Update the tables in `README.md` (§3, §4, §11) and `SKILL.md` (Phase 2 table, device-description table,
   upload map).
