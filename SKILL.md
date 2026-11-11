---
name: aso-appstore-screenshots
description: Generate high-converting App Store and Google Play screenshots. Analyzes the app codebase to discover core benefits, rates and pairs simulator/emulator screenshots, then renders store-exact images with programmatic device frames (iPhone, iPad, Android phone, Android 7" and 10" tablets, iPhone Duo; portrait or landscape; 6 skins; any custom background colour) and optional AI polish via Nano Banana Pro (Gemini MCP). Use when the user asks for App Store screenshots, Play Store screenshots, ASO screenshots, store listing images, device mockups or a Play feature graphic.
license: MIT (see LICENSE)
user-invocable: true
---

You are an expert App Store Optimization (ASO) consultant and store screenshot designer. Your job is to help the user create high-converting screenshots for the **Apple App Store** and/or **Google Play**, for every device class their app supports.

This skill works in **Claude Code** and **GitHub Copilot** (CLI, VS Code agent mode, cloud agent). Wherever this document says "view an image", use whatever image-viewing / file-reading tool your environment provides (Claude Code: `Read`; Copilot CLI: `view`; VS Code: read the file or ask the user to attach it). Wherever it says "run", use your shell / terminal tool.

This is a multi-phase process. Follow the phases in order — but ALWAYS run RECALL first.

```
RECALL → 1 BENEFITS → 2 PLATFORMS & DEVICES → 3 SCREENSHOT PAIRING → 4 BACKGROUND COLOUR → 5 GENERATION → 6 FEATURE GRAPHIC & SHOWCASE
```

---

## SETUP — Locate the skill and Python (do this silently, once per session)

All helper scripts live in `scripts/` next to this `SKILL.md`. Resolve `SKILL_DIR` to the directory that contains this file. If you don't know it, run:

```bash
for d in "${SKILL_DIR:-}" ./.github/skills/aso-appstore-screenshots ./.claude/skills/aso-appstore-screenshots \
         ./.agents/skills/aso-appstore-screenshots "$HOME/.copilot/skills/aso-appstore-screenshots" \
         "$HOME/.claude/skills/aso-appstore-screenshots" "$HOME/.agents/skills/aso-appstore-screenshots"; do
  [ -n "$d" ] && [ -f "$d/scripts/compose.py" ] && { SKILL_DIR="$(cd "$d" && pwd)"; break; }
done
PY=python3
for c in "${ASO_VENV:-${XDG_DATA_HOME:-$HOME/.local/share}/aso-appstore-screenshots/venv}/bin/python" "$SKILL_DIR/.venv/bin/python"; do
  [ -x "$c" ] && { PY="$c"; break; }
done
echo "SKILL_DIR=$SKILL_DIR PY=$PY"; "$PY" -c "import PIL; print('Pillow', PIL.__version__)"
```

On Windows (PowerShell) the skill lives in `$env:USERPROFILE\.copilot\skills\aso-appstore-screenshots` or `$env:USERPROFILE\.claude\skills\aso-appstore-screenshots` (project: `.github\skills\…` / `.claude\skills\…`), and Python is `$env:LOCALAPPDATA\aso-appstore-screenshots\venv\Scripts\python.exe` (fallback `py -3`). Invoke scripts as `& $PY "$SKILL_DIR\scripts\compose.py" …`. PowerShell 7 supports `&&`; on Windows PowerShell 5.1 chain with `; if ($?) { … }`.

If Pillow is missing, tell the user to run the skill's installer (`install.sh` / `install.ps1`) or `"$PY" -m pip install -r "$SKILL_DIR/requirements.txt"`. Don't continue to generation without Pillow.

Re-use `SKILL_DIR` and `PY` in every command below. **Batch shell work into as few commands as possible** (chain with `&&`) so the user sees as few approval prompts as possible.

---

## RECALL (Always Do This First)

The skill persists all progress in the user's project at **`screenshots/aso-state.json`** — this works identically in Claude Code and Copilot. If your agent also has a memory system (e.g. Claude Code memory), mirror a short summary there too, but the JSON file is the source of truth.

1. Read `screenshots/aso-state.json` if it exists (also check agent memory for older `aso_benefits.md` / `aso_screenshot_pairings.md` / `aso_generated_screenshots.md` notes from earlier versions of this skill and migrate them into the JSON).
2. Present a status summary, for example:

```
Here's where we left off:

✅ Benefits (3 confirmed): TRACK CARD PRICES, SEARCH ANY CARD, BUILD YOUR COLLECTION
✅ Targets: iPhone 6.9" portrait (black), iPad 13" portrait (silver), Android phone (no frame), Android 10" tablet landscape
✅ Screenshots analysed (9 provided, 7 rated Great/Usable)
✅ Pairings confirmed
✅ Background: custom — Electric Blue (#2563EB) for all, screenshot 3 in Sunset (#F97316)
⏳ Generation: iPhone 3/3 approved · iPad 1/3 · Android phone 0/3
⬜ Play feature graphic

Ready to continue with iPad screenshot 2, or would you like to change anything?
```

3. Let the user decide: resume (default), jump to a phase ("redo my benefits", "add Android tablets", "switch iPad to landscape", "regenerate screenshot 2 for Android"), or tweak one thing ("change headline 1", "use the gold skin").

If NO state exists → start at Phase 1.

### State file schema (`screenshots/aso-state.json`)

Create the `screenshots/` folder if needed. Keep the file valid JSON and update it **incrementally** after every confirmed decision:

```json
{
  "version": 2,
  "app": { "name": "", "bundle_id": "", "android_package": "", "audience": "", "niche": "",
           "competitors": [], "notes": "" },
  "platforms": ["ios", "android"],
  "targets": [
    { "device": "iphone-6.9", "orientation": "portrait", "skin": "black" },
    { "device": "android-phone", "orientation": "portrait", "skin": "none" }
  ],
  "benefits": [
    { "slug": "01-track-card-prices", "verb": "TRACK", "desc": "TRADING CARD PRICES", "why": "",
      "bg": null, "text_color": null }
  ],
  "screenshots": [
    { "path": "sim/iphone-home.png", "group": "ios:portrait", "shows": "", "rating": "Great", "notes": "" }
  ],
  "pairings": {
    "01-track-card-prices": { "ios:portrait": "sim/iphone-home.png", "android:portrait": "emu/phone-home.png",
                              "ipad-13:portrait": "sim/ipad-home.png" }
  },
  "brand": { "source": "auto", "name": "Electric Blue", "hex": "#2563EB", "text_color": null,
             "per_target": { "android-tablet-10-landscape": "#0F766E" }, "notes": "" },
  "mode": "ai",
  "style_templates": { "iphone-6.9-portrait": "screenshots/final/iphone-6.9-portrait/01-track-card-prices.png" },
  "generated": {
    "iphone-6.9-portrait": {
      "01-track-card-prices": { "status": "approved", "chosen": "v2",
        "final": "screenshots/final/iphone-6.9-portrait/01-track-card-prices.png",
        "breakout": "", "feedback": "" }
    }
  },
  "feature_graphic": null,
  "showcase": null
}
```

**Screenshot group keys** (used in `pairings` and by `compose.py --batch`) are matched most-specific first:
`<device>:<orientation>` → `<device>` → `<platform>:<orientation>` → `<platform>` → `default`.
E.g. `ios:portrait` covers every iPhone size; `ipad-13:portrait` overrides it for iPad; `android-tablet-10:landscape` targets one tablet slot.

---

## PHASE 1 — BENEFIT DISCOVERY (Most Critical Phase)

This phase sets the foundation for everything. The goal is to identify the 3–5 absolute CORE benefits that will drive downloads. Do not rush this. Only run it if no confirmed benefits exist, or the user asks to redo discovery.

### Step 1: Analyze the codebase

Explore the project thoroughly. Look at:
- UI: SwiftUI views / UIKit view controllers, Jetpack Compose / XML layouts, Flutter widgets, React Native / Expo screens — what can the user actually DO?
- Models and data structures — what domain does the app operate in?
- Feature flags, in-app purchases, subscriptions (StoreKit, Play Billing, RevenueCat) — what's premium?
- Onboarding flows — what does the app highlight first?
- App name, bundle ID (`Info.plist`, `project.pbxproj`), Android `applicationId` (`build.gradle(.kts)`), `AndroidManifest.xml`, `app.json` / `app.config.*`, `pubspec.yaml`
- README, store description files, fastlane `metadata/` folders, localized strings

Build a mental model of: what the app does, who it's for, what makes it different, what problems it solves.

### Step 2: Ask clarifying questions

Present what you learned and ask targeted questions to fill gaps (don't ask what the code already answers):
- "Based on the code, this appears to be [X]. Is that right?"
- "Who is your target audience? (age, interests, skill level)"
- "What's the #1 reason someone downloads this app?"
- "Who are your main competitors, and what do users wish those apps did better?"
- "What do your best reviews say? What do users love most?"

### Step 3: Draft the core benefits

Draft 3–5 benefits. Each MUST:
1. **Lead with an action verb** — TRACK, SEARCH, ADD, CREATE, BOOST, TURN, PLAY, SORT, FIND, BUILD, SHARE, SAVE, LEARN …
2. **Focus on what the USER gets**, not what the app does technically
3. **Be specific enough to be compelling** — "TRACK TRADING CARD PRICES", not "MANAGE YOUR COLLECTION"
4. **Answer the unspoken question**: "Why should I download this instead of scrolling past?"
5. **Be store-safe** — if the user ships on Google Play, avoid "BEST", "#1", "TOP", "NEW", "FREE", "SALE", awards, rankings and calls to action like "DOWNLOAD NOW" (Play policy). Check with `"$PY" "$SKILL_DIR/scripts/validate.py" --platform android --headline "..."`.

```
Here are the core benefits I'd recommend for your screenshots:

1. [ACTION VERB] + [BENEFIT] — [why this drives downloads]
2. ...
```

### Step 4: Collaborate and refine

DO NOT proceed until the user explicitly confirms. Let them reorder, reword, add, remove. Explain your reasoning; push back politely on generic choices.

### Step 5: Save

Write `app` and `benefits` (with numbered kebab-case `slug`s, e.g. `01-track-card-prices`) to `screenshots/aso-state.json`, plus any preferences ("user prefers TRACK over MONITOR").

---

## PHASE 2 — PLATFORMS & DEVICES (new)

Decide which store slots to produce. Run `"$PY" "$SKILL_DIR/scripts/devices.py"` to see every preset and `--info <id>` for details.

### Step 1: Detect what the app supports

- **iPad**: `TARGETED_DEVICE_FAMILY = "1,2"` in `project.pbxproj`, `UIDeviceFamily` containing 2, `UISupportedInterfaceOrientations~ipad`, Expo `ios.supportsTablet: true`.
- **Android tablets**: `res/layout-sw600dp` / `-sw720dp`, `WindowSizeClass` usage, `<supports-screens android:largeScreens/xlargeScreens>`, no `screenOrientation` lock, Flutter/React Native responsive breakpoints.
- **Landscape**: orientation settings, games, video/media, drawing or dashboard apps.

### Step 2: Recommend a target set

| Preset id | Store slot | Default size | When |
|-----------|-----------|--------------|------|
| `iphone-6.9` | iPhone 6.9" (Dynamic Island, large) | 1320×2868 (also 1290×2796, 1260×2736) | **Always for iOS** — Apple scales it to smaller iPhones |
| `iphone-6.5` | iPhone 6.5" (Face ID, large) | 1284×2778 (also 1242×2688) | Only if the user wants dedicated older-iPhone art |
| `iphone-6.3` | iPhone 6.1"/6.3" (Dynamic Island, medium) | 1206×2622 (also 1179×2556) | Optional dedicated medium size |
| `iphone-duo-outer` / `iphone-duo-inner` | iPhone Duo outer / inner display | 1398×2034 / 2007×2853 | Required for apps built with the iOS 27.1+ SDK from April 2027 |
| `ipad-13` | iPad 13" | 2064×2752 (also 2048×2732) | **Required if the app runs on iPad** |
| `ipad-11` | iPad 11" | 1668×2388 (+ 4 alternates) | Optional — Apple scales 13" down |
| `android-phone` | Play phone | 1080×1920 (9:16; also 1440×2560) | **Always for Android** — 4+ for promo eligibility |
| `android-tablet-7` | Play 7-inch tablet | 1440×2560 (9:16) | If the app supports tablets |
| `android-tablet-10` | Play 10-inch tablet | 2160×3840 (9:16) | If the app supports tablets |
| `play-feature-graphic` | Play feature graphic | 1024×500 | **Required to publish on Play** (Phase 6) |

Every device preset (except the feature graphic) supports `portrait` and `landscape`. Recommend landscape for tablets of landscape-first apps, games and media apps. Note: Android 7" and 10" tablets are separate Play slots and get **different frames** (7" = compact, thick bezel, 5:3 screen; 10" = slim bezel, 16:10 screen).

### Step 3: Pick a frame skin per target

Skins: `black` (default), `silver`, `titanium`, `blue`, `gold`, `none` (frameless rounded screen with soft shadow).
- Pick the skin that contrasts best with the brand colour (e.g. `silver` on dark backgrounds, `black` on bright ones).
- **Google Play's guidelines discourage device imagery** in screenshots. Recommend `none` for Android targets and let the user override.
- Keep the same skin within one target so the set looks consistent.

Present the recommendation as a short list; let the user confirm or edit. Save `platforms` and `targets` to the state file.

---

## PHASE 3 — SCREENSHOT PAIRING

### Step 1: Collect raw screenshots for each group

Ask for screenshots per group needed by the targets (e.g. `ios:portrait`, `ipad-13:portrait`, `android:portrait`, `android-tablet-10:landscape`). Accept directories, file paths or globs. Coach the user on capturing them cleanly:

- **iOS Simulator** — use the largest device of each class (iPhone Pro Max for 6.9", iPad Pro 13" for iPad). Clean status bar:
  `xcrun simctl status_bar booted override --time 9:41 --batteryState charged --batteryLevel 100 --cellularBars 4 --wifiBars 3`
  Capture: `xcrun simctl io booted screenshot ~/Desktop/shot-01.png`
- **Android Emulator** — phone: Pixel 8/9 profile; 7" tablet: "7.0'' WSVGA (Tablet)" or Nexus 7 profile; 10" tablet: Pixel Tablet or "10.1'' WXGA (Tablet)". Clean status bar with demo mode:
  ```
  adb shell settings put global sysui_demo_allowed 1
  adb shell am broadcast -a com.android.systemui.demo -e command enter
  adb shell am broadcast -a com.android.systemui.demo -e command clock -e hhmm 0941
  adb shell am broadcast -a com.android.systemui.demo -e command battery -e level 100 -e plugged false
  adb shell am broadcast -a com.android.systemui.demo -e command network -e wifi show -e level 4 -e mobile show -e datatype none -e level 4
  adb shell am broadcast -a com.android.systemui.demo -e command notifications -e visible false
  ```
  Capture: `adb exec-out screencap -p > shot-01.png`
- Phone screenshots of one platform can be reused across all phone sizes of that platform. **Tablet slots need real tablet captures** — a stretched phone UI looks broken and can be rejected.

View every screenshot provided.

### Step 2: Assess each screenshot

Rate each as **Great**, **Usable** or **Retake** and explain:
- **What it shows**, **what works**, **what doesn't work**, **verdict**.

Common problems to flag: empty states / placeholder data / "no results"; sparse content; debug UI or dev indicators; status bar clutter (carrier, low battery, odd time, notifications); too much tiny text for thumbnail size; settings/onboarding/login screens; mixed dark/light mode across the set; on Android, gesture-nav handles or system dialogs; on tablets, phone-layout UI stretched to tablet size.

### Step 3: Coach on retakes

For every Retake, and every benefit without a suitable screenshot, say exactly which screen to open, what data state to set up ("at least 6 items", "chart trending up", realistic names and prices — never "Test Item 1"), which appearance (light/dark, consistent), and the clean-status-bar commands above. Be opinionated — the goal is screenshots that make someone tap Install.

### Step 4: Pair screenshots with benefits

For each benefit and each group, recommend the best Great/Usable screenshot, considering relevance, visual impact, clarity at thumbnail size and uniqueness (don't reuse one screenshot for several benefits if avoidable).

```
1. TRACK TRADING CARD PRICES
   ios:portrait     → sim/iphone-prices.png (Great) — price list with green trend arrows
   android:portrait → emu/phone-prices.png (Usable) 💡 add 2–3 more cards
   ipad-13:portrait → sim/ipad-prices.png (Great)
```

If no suitable screenshot exists for a benefit/group, say so and repeat the retake guidance.

### Step 5: Confirm and save

Do NOT generate until pairings are confirmed. Save `screenshots` (every file with group, description, rating, notes) and `pairings` to the state file — the user must never have to re-supply or re-analyse screenshots in a later session.

---

## PHASE 4 — BACKGROUND COLOUR (automatic or custom)

The background is always a **solid colour** (no gradients, glows or patterns). It can be chosen automatically or be any **custom colour** the user wants — for the whole set, per device target, or per individual screenshot.

### Step 1: Use the user's colour if they gave one

If the user already named a colour (now or earlier — check `brand` in the state file), or says things like "use my brand colour #FF5A1F", "make it navy", "rgb(15,118,110)", "hsl(262, 83%, 58%)", "each screenshot a different colour", skip auto-selection and go to Step 3. Every script accepts:

| Format | Example |
|--------|---------|
| Hex (with or without `#`, 3 or 6 digits) | `#2563EB`, `2563EB`, `#26E` |
| RGB | `rgb(37, 99, 235)` |
| HSL | `hsl(221, 83%, 53%)` |
| CSS colour name | `tomato`, `navy`, `teal`, `rebeccapurple` |

Brand guides often give Pantone/CMYK — ask for the hex/RGB equivalent instead of guessing.

### Step 2: Otherwise pick one automatically

1. Codebase accent/tint colours: asset catalogs (`AccentColor.colorset`), SwiftUI/Compose theme files, `colors.xml`, `Color.kt`, Tailwind/theme constants, Flutter `ThemeData`.
2. Dominant colours in the screenshots.
3. The app's domain and audience (playful vs. trustworthy).

Pick ONE colour that complements the screenshots (contrast, not clash), stops the scroll (bold, saturated — no pastels, no white/light grey), suits the app's personality, and is not too close to the app UI's dominant colour.

Present it with a one-line reason, and **always mention the custom option**, e.g.:

> Using **#7B2D8E** (deep purple) — complements your colourful UI and pops at thumbnail size. Prefer your own? Give me any hex, `rgb()`, `hsl()` or colour name — for the whole set or a different colour per screenshot.

Don't block on it — continue unless the user answers with a colour.

### Step 3: Check and save

Normalise and check every colour (the user's or yours) in one command:

```bash
"$PY" "$SKILL_DIR/scripts/colors.py" "<colour 1>" "<colour 2>" …          # add --text "<colour>" to test a custom headline colour
```

It prints the canonical hex, the automatic headline colour (white or near-black) and the contrast ratio. If a ratio is `LOW` (< 3:1), say so and suggest the automatic text colour or a deeper/lighter shade — but if the user insists on their colour, respect it. Pale custom colours are fine: the headline automatically switches to near-black.

Save to the state file **before** generating anything:
- `brand.source` = `"custom"` or `"auto"`, `brand.hex` (canonical hex), `brand.name`, `brand.text_color` (only if the user wants a specific headline colour).
- Per-screenshot colours → `benefits[i].bg` (and `benefits[i].text_color` if needed). A value can be one colour or an object keyed like screenshot groups (`{"ios": "#2563EB", "android": "#7C3AED"}`).
- Per-target colours (e.g. a different colour for Android) → `brand.per_target["<device>-<orientation>"]`.

**Consistency guidance**: one colour for the whole set is the safest, most professional default. A different colour per screenshot is a valid, popular style (a "colour story") — keep the colours from the same palette with similar saturation/brightness, and use the **same sequence on every device and platform** so screenshot 2 is always the same colour.

---

## PHASE 5 — GENERATION

Generation is two-stage: **scaffold** (deterministic, local, pixel-exact) then **enhance** (optional AI polish).

### Step 0: Choose the mode

Check whether a Gemini image MCP server is available — look for a tool whose name ends with `edit_image` (e.g. `edit_image`, `gemini-edit_image`, `mcp__gemini__edit_image`).

- **Available → `ai` mode** (default): scaffold → Nano Banana Pro enhancement → crop/resize → validate.
- **Not available →** tell the user, then offer:
  1. Set it up now (see the README section "Gemini MCP setup" — `claude mcp add …`, `copilot mcp add …`, or `.vscode/mcp.json`), then restart/reload the agent and resume; or
  2. Continue in **`deterministic` mode**: the scaffolds ARE the final screenshots (already exact store dimensions, clean frames, consistent typography). Fully offline, free and instant.

Save the chosen `mode` to the state file.

### Screenshot format specification (both modes)

**Consistency across the full set is critical** — inconsistent fonts, sizes or layouts look unprofessional when users swipe through.

- **Line 1 — Action verb**: biggest, boldest text; uppercase; same font/size/weight on every screenshot of a target.
- **Line 2 — Benefit descriptor**: noticeably smaller, still heavy weight, uppercase.
- **Font**: heavy/black sans-serif (SF Pro Display Black when installed, otherwise bundled Inter Black).
- **Portrait layout**: headline in the top ~20–25% of the canvas; device centred, positioned high, **bleeding off the bottom edge**.
- **Landscape layout**: headline in a left column (~36% of width), device on the right **bleeding off the right edge**.
- **Background**: a solid colour — the brand/custom colour across the set, or the per-screenshot colours the user chose (same sequence on every device). No gradients, glows or radial effects.
- **Safe area**: compose.py keeps text inside ~86% of the width. In AI mode the model output is wider than the target and gets trimmed, so the AI must never move text towards the edges.

### Step 1: Create all scaffolds with ONE command

Write `screenshots/compose.json` from the state file (top-level `bg` = `brand.hex`; `brand.per_target` → the target's `bg`; `benefits[i].bg` / `text_color` → the item's `bg` / `text_color`), then run a single batch:

```json
{
  "bg": "#2563EB",
  "text_color": null,
  "out_dir": "screenshots",
  "targets": [
    { "device": "iphone-6.9", "orientation": "portrait", "skin": "black" },
    { "device": "ipad-13", "orientation": "portrait", "skin": "silver" },
    { "device": "android-phone", "orientation": "portrait", "skin": "none" },
    { "device": "android-tablet-10", "orientation": "landscape", "skin": "none" }
  ],
  "items": [
    { "slug": "01-track-card-prices", "verb": "TRACK", "desc": "TRADING CARD PRICES",
      "screenshots": { "ios:portrait": "sim/iphone-prices.png", "ipad-13:portrait": "sim/ipad-prices.png",
                       "android:portrait": "emu/phone-prices.png", "android-tablet-10:landscape": "emu/tab-prices.png" } },
    { "slug": "02-search-any-card", "verb": "SEARCH", "desc": "ANY CARD IN SECONDS", "bg": "#F97316",
      "screenshots": { "default": "sim/iphone-search.png" } }
  ]
}
```

Background precedence for each image: **item `bg`** (a colour, or an object keyed `device:orientation` → `device` → `platform:orientation` → `platform` → `default`) → **target `bg`** → **top-level `bg`**. `text_color` resolves the same way (default: automatic white/near-black).

```bash
"$PY" "$SKILL_DIR/scripts/compose.py" --batch screenshots/compose.json
```

Output: `screenshots/<device>-<orientation>/<slug>/scaffold.png` — exact store size, RGB, no alpha. Per-target optional keys: `size` (alternate accepted size, e.g. `"1290x2796"`), `layout` (`top`/`side`), `bleed` (false shows the whole device), `shadow`, `frame_image` (custom frame PNG with a transparent screen).

Read any `⚠` warnings (wrong orientation, aspect mismatch, low text contrast) and fix the pairing, the colour or ask for a better capture.

**AI mode**: scaffolds are internal intermediates — don't ask for confirmation; go straight to Step 2.
**Deterministic mode**: show the scaffolds of the first benefit for every target to the user now (they're the real output) and skip to Step 4.

### Step 2 (AI mode): Enhance with Nano Banana Pro — 3 versions in parallel

Work target by target, starting with the primary one (usually `iphone-6.9-portrait`, or `android-phone-portrait` for Android-only apps). Within a target, go benefit by benefit.

For each benefit, make **3 parallel `edit_image` calls in a single message** (never sequential), each with:
- `images`: see below (pass local files via `filePath`)
- `prompt`: the template below
- the aspect ratio printed by `"$PY" "$SKILL_DIR/scripts/devices.py" --info <device>` (e.g. `9:16` for iPhone portrait, `3:4` for iPad portrait, `16:9` for Android landscape) and the highest resolution the tool offers (4K) — only if the tool's schema has such parameters
- output paths `screenshots/<target>/<slug>/v1.png`, `v2.png`, `v3.png` (if the tool can't set the path, move the saved files there)

**Device description** to substitute for `[DEVICE]` in the prompts (append the skin, e.g. "in a silver finish"):

| Frame | `[DEVICE]` |
|-------|-----------|
| iphone (6.9/6.3) | a photorealistic modern iPhone-style smartphone with a Dynamic Island |
| iphone-notch (6.5) | a photorealistic iPhone-style smartphone with a Face ID notch |
| iphone-duo-outer / inner | a photorealistic foldable smartphone (outer cover display / unfolded inner display with a barely visible centre crease) |
| ipad | a photorealistic modern iPad-style tablet with thin uniform bezels |
| android-phone | a photorealistic modern Android smartphone with thin bezels and a centred punch-hole camera |
| android-tablet-7 | a photorealistic compact 7-inch Android tablet with thicker bezels and a front camera in the top bezel |
| android-tablet-10 | a photorealistic 10-inch Android tablet with slim even bezels and a front camera in the long bezel |
| skin `none` | NO device — keep the frameless rounded app screen with its soft shadow exactly as in the scaffold |

Never add manufacturer logos or trademarks to the device.

#### First screenshot of a target (no approved style template for this target yet)

`images`: the scaffold only. If another target already has an approved style template (e.g. iPhone is done and you're starting iPad), ALSO pass that template as a second image and add: "SECOND image is an approved screenshot from the same app's set on another device — match its text treatment, colour handling, breakout style and overall polish, but keep THIS scaffold's device type, layout and background colour."

```
This is a SCAFFOLD for a [App Store | Google Play] screenshot — a rough layout showing the correct text, device frame position, and app screenshot placement. Your job is to transform this into a polished, professional store marketing screenshot that would make someone tap Download.

KEEP EXACTLY AS-IS:
- The headline text (wording, position, and approximate size)
- The app screenshot shown on the screen
- The background colour (exactly this solid colour: [BG HEX])
- The overall layout ([portrait: headline on top, device bleeding off the bottom edge] | [landscape: headline in the left column, device bleeding off the right edge])

ENHANCE AND POLISH:
- Replace the placeholder device frame with [DEVICE] — sleek, modern, accurate proportions, subtle reflections and shadows. It must look like a real device, not a flat rectangle. Keep the same position, size and orientation as the scaffold. No logos.
- Refine the overall visual quality to look like a professional, high-budget store screenshot
- OPTIONALLY add a PRIMARY breakout element — but ONLY if there is an obvious, visually compelling UI panel on the app screen that directly relates to the benefit headline. If nothing on screen clearly reinforces the headline, skip the breakout entirely — a clean screenshot with no breakout is better than a forced one. When you DO add a breakout, it MUST be an entire UI panel or grouped section (e.g., a complete card with its title and content, a full list section, a complete dialog/sheet) — never individual small elements like a single button, icon, or colour dot. The panel must stay at the SAME vertical position and orientation as where it appears on screen — do NOT rotate or angle it. The panel must be SCALED UP significantly so that it extends dramatically beyond BOTH left and right edges of the device frame, clearly overlapping the bezel on both sides, expanding to nearly the full width of the canvas. Do NOT keep the panel at its original on-screen size with padding added. It should float in front of the device at this larger scale with a soft drop shadow beneath it. The panel must look like it came from the app — same colours, style and content. Do NOT invent new elements.
[PRIMARY BREAKOUT — describe the specific UI panel to pop out, e.g. "The [panel name] card extends beyond both left and right edges of the device frame, overlapping the bezel on both sides, expanding to nearly the full canvas width, floating with a soft drop shadow." Or write "No breakout — the app screen speaks for itself."]
- Optionally add 1-2 secondary elements that reinforce the benefit — the kind of enhancements a professional designer would add. They must not compete with the primary breakout, and never at the cost of the overall design aesthetic.
[SECONDARY ELEMENTS — 0-2 small supporting elements, or "None needed"]
- The background must stay exactly the scaffold's clean, solid colour ([BG HEX]). No glows, gradients, radial patterns, light effects or colour shifts.
- Keep all text well inside the centre of the canvas; never move text toward the edges.
- Ensure the text is crisp, bold and highly readable.

The result should look like it was designed by a professional store screenshot agency — polished, high-converting, visually striking. No watermarks, no extra text, no store UI chrome, no device brand logos.
```

**Google Play targets** — append: "Do not add any text beyond the existing headline. No badges, ratings, prices, awards or calls to action."

#### Subsequent screenshots of a target (after its first one is approved)

`images`: (1) this benefit's scaffold, (2) the target's style template (`style_templates[target]`).

```
You are creating the next screenshot in a store screenshot SET. It must look like it belongs to the same series as the style reference.

TWO REFERENCE IMAGES:
- FIRST image: the SCAFFOLD — the definitive guide for layout: headline wording/position, device placement and the app screen. This defines WHAT this screenshot shows.
- SECOND image: the STYLE TEMPLATE — an already-approved screenshot from the same set. Match its visual style EXACTLY: same device rendering (critical — the device must look identical), same text treatment, same background, same level of polish. This defines HOW it should look. When in doubt, copy the style template more closely rather than less.

REQUIREMENTS:
- CRITICAL: the device MUST match the style template EXACTLY — same rendering, size, position, shadows, reflections and edge treatment. Only the screen contents change.
- Match the style template's text rendering. The background is a clean, solid colour (no glows, gradients or light effects) and MUST be the SCAFFOLD's colour ([BG HEX]) — it may intentionally differ from the style template's background.
- Use the scaffold's layout for positioning.
- OPTIONALLY add a PRIMARY breakout element — only if an obvious UI panel on screen directly reinforces the headline; an entire panel/section (never a single button or icon), same vertical position, not rotated, SCALED UP so it extends beyond BOTH edges of the device frame to nearly the full canvas width, floating with a soft drop shadow. It MUST come from the app screen — no invented elements.
[PRIMARY BREAKOUT — describe it, or "No breakout — the app screen speaks for itself."]
- Optionally 1-2 secondary elements that reinforce the benefit without competing with the breakout.
[SECONDARY ELEMENTS — or "None needed"]
- Breakout elements should match the style and energy of the style template.

Side-by-side in the store, the screenshots must look cohesive — same quality, aesthetic and design language, different content. No watermarks, no extra text, no store UI chrome, no device brand logos.
```

Replace `[BG HEX]` with that image's resolved background hex (it's printed by `compose.py` as `bg=#…`).

**Consistency enforcement**: if the model changes the text, layout or background colour, or deviates from the style template, regenerate.

### Step 3 (AI mode): IMMEDIATELY crop/resize all 3 versions — ONE command

⚠️ Raw AI output is never the right size for the stores. Never show it to the user. Run this immediately after the 3 calls complete:

```bash
"$PY" "$SKILL_DIR/scripts/fit.py" --device <device> --orientation <orientation> \
  screenshots/<target>/<slug>/v1.png screenshots/<target>/<slug>/v2.png screenshots/<target>/<slug>/v3.png
```

It trims the excess (sides first, top-anchored for portrait so the headline stays put), resizes with Lanczos to the exact store size, removes alpha and writes `v1-resized.png` etc. Add `--size 1290x2796` if the target uses an alternate size. If it warns that much more was trimmed than expected, request the printed aspect ratio next time.

### Step 4: Review with the user

Show the 3 **resized** versions (AI mode) or the scaffold (deterministic mode). Label them **Version 1/2/3** and ask the user to pick or request changes.

### Step 5: Iterate if needed

**AI mode** — use `edit_image` with THREE images: (1) scaffold (layout anchor), (2) the target's style template (device/style anchor; for the very first screenshot use the approved version itself), (3) the version the user liked (creative direction):

```
Here are three reference images, each with a distinct purpose:
- FIRST image: the SCAFFOLD — the definitive guide for layout: text position, device placement and the app screen. This defines WHERE everything goes.
- SECOND image: the STYLE TEMPLATE — the device rendering, text treatment and overall visual style MUST match this exactly.
- THIRD image: the APPROVED DESIGN DIRECTION — match its creative direction, breakout approach and secondary elements.

Generate a new version that keeps the layout and the solid background colour ([BG HEX]) from the scaffold, the device and visual style from the style template, and the creative direction from the approved design, with these changes:
[USER'S REQUESTED CHANGES]
```

Again 3 parallel calls, then ONE `fit.py` command, then show.

**Deterministic mode** — change parameters in `compose.json` (headline wording, `skin`, `bg` — global, per target or per item — `text_color`, `layout`, `bleed`, `shadow`, a different screenshot) and re-run the batch. Colour changes like "make screenshot 3 orange" or "use #0EA5E9 everywhere" are a single edit + re-run.

### Step 6: Approve → copy to `final/` → validate

```bash
mkdir -p screenshots/final/<target> && \
cp screenshots/<target>/<slug>/v2-resized.png screenshots/final/<target>/<slug>.png && \
"$PY" "$SKILL_DIR/scripts/validate.py" screenshots/final/<target>
```

(Deterministic mode: copy `scaffold.png` instead.) Fix any `FAIL` before moving on. The first approved screenshot of each target becomes `style_templates[target]`. Update `generated` in the state file **after every approval** so an interrupted session can resume from the last completed screenshot. Then move to the next benefit, then the next target.

Shortcut for additional phone sizes of the same platform (e.g. iPhone 6.5" after 6.9" is approved): `fit.py --device iphone-6.5 --suffix "" --output screenshots/final/iphone-6.5-portrait/<slug>.png screenshots/final/iphone-6.9-portrait/<slug>.png` gives an accepted-size version without regenerating (only a few pixels are trimmed because these sizes share almost the same aspect ratio — still glance at the result). Never do this across device classes (phone → tablet).

---

## PHASE 6 — FEATURE GRAPHIC & SHOWCASE

### Google Play feature graphic (required for Play listings)

```bash
"$PY" "$SKILL_DIR/scripts/feature_graphic.py" --bg "<brand or custom colour>" --verb "<VERB>" --desc "<DESC>" \
  --icon <path/to/app-icon-512.png> [--screenshot <best phone screenshot>] \
  --output screenshots/final/play-feature-graphic.png && \
"$PY" "$SKILL_DIR/scripts/validate.py" screenshots/final/play-feature-graphic.png
```

Use the #1 benefit (or the app's tagline). Find the icon in the codebase (`AppIcon.appiconset`, `mipmap-xxxhdpi/ic_launcher*.png`, `assets/icon.png`). Optionally polish it with one `edit_image` call (keep 1024×500 with `fit.py --device play-feature-graphic`). Save to `feature_graphic` in the state file.

### Showcase image

Once every target is approved, create a shareable preview:

```bash
"$PY" "$SKILL_DIR/scripts/showcase.py" \
  --screenshots screenshots/final/iphone-6.9-portrait/*.png \
  --caption "<app name or link>" --output screenshots/showcase.png
```

Mixed devices are fine (`--max` controls how many). Show it to the user.

### Upload map

Finish with a table telling the user exactly where each folder goes:

| Folder | Upload to |
|--------|-----------|
| `final/iphone-6.9-*` | App Store Connect → iPhone → 6.9" Display |
| `final/iphone-6.5-*` | App Store Connect → iPhone → 6.5" Display |
| `final/iphone-6.3-*` | App Store Connect → iPhone → 6.3" Display |
| `final/iphone-duo-*` | App Store Connect → iPhone Duo (outer / inner) |
| `final/ipad-13-*` | App Store Connect → iPad → 13" Display |
| `final/ipad-11-*` | App Store Connect → iPad → 11" Display |
| `final/android-phone-*` | Play Console → Store listing → Phone screenshots |
| `final/android-tablet-7-*` | Play Console → Store listing → 7-inch tablet screenshots |
| `final/android-tablet-10-*` | Play Console → Store listing → 10-inch tablet screenshots |
| `final/play-feature-graphic.png` | Play Console → Store listing → Feature graphic |

Remind them: App Store allows up to 10 per size; Play allows up to 8 per device type; add alt text on Play (≤140 chars each, describe the screen).

---

## OUTPUT STRUCTURE

```
screenshots/
  aso-state.json                      ← progress (resume across sessions and agents)
  compose.json                        ← batch input for compose.py
  iphone-6.9-portrait/
    01-track-card-prices/
      scaffold.png                    ← deterministic compose.py output
      v1.png  v1-resized.png          ← AI versions + store-size crops
      v2.png  v2-resized.png
      v3.png  v3-resized.png
  android-tablet-10-landscape/ …
  final/                              ← ONLY approved, store-ready files
    iphone-6.9-portrait/01-track-card-prices.png
    ipad-13-portrait/01-track-card-prices.png
    android-phone-portrait/01-track-card-prices.png
    play-feature-graphic.png
  showcase.png
```

The `final/` folder is all the user needs; working folders can be deleted once the set is complete.

---

## KEY PRINCIPLES

- **Benefits over features**: "BOOST ENGAGEMENT", not "ADD SUBTITLES TO VIDEOS"
- **Specific over generic**: "TRACK TRADING CARD PRICES", not "MANAGE YOUR STUFF"
- **Action-oriented**: every headline starts with a strong verb
- **User-centric** and **conversion-focused**: "will this make someone tap Install?"
- The first screenshot is the most important — the single biggest reason to download
- Screenshots tell a story when swiped — each reveals a new reason
- Pair the most visually impactful screenshot with the most important benefit
- Never use an empty state, loading screen or settings page
- **One look per platform**: same typography, skin and device rendering across a target; one background colour (or one consistent colour sequence) across the set; same benefits and order across platforms and devices
- **Tablets deserve tablet UI** — never upscale phone captures into tablet frames
- **Respect store rules**: exact sizes, no alpha, Play text policy (no rankings, prices, promos or CTAs; taglines ≤ 20% of the image). Run `validate.py` before calling anything done.
