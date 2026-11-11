#!/usr/bin/env bash
# Installer for the aso-appstore-screenshots agent skill (macOS / Linux).
# Installs into Claude Code and/or GitHub Copilot skill folders, creates an isolated
# Python environment with Pillow, runs a self-test and (optionally) wires up the
# Gemini MCP server used for AI enhancement.
set -euo pipefail

SKILL_NAME="aso-appstore-screenshots"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ASO_VENV:-${XDG_DATA_HOME:-$HOME/.local/share}/$SKILL_NAME/venv}"
export PYTHONDONTWRITEBYTECODE=1

usage() {
  cat <<EOF
Usage: ./install.sh [targets] [options]

Targets (default: --claude --copilot):
  --claude            Claude Code      user: ~/.claude/skills      project: <dir>/.claude/skills
  --copilot           GitHub Copilot   user: ~/.copilot/skills     project: <dir>/.github/skills
                      (Copilot CLI, VS Code agent mode, Copilot app)
  --agents            Open standard    user: ~/.agents/skills      project: <dir>/.agents/skills
                      (Codex and other Agent Skills-compatible agents)
  --all               All of the above

Options:
  --project DIR       Install into a project/repository instead of your home folder
  --link              Symlink to this folder instead of copying (for skill development)
  --setup-mcp         Configure the Gemini MCP server (Nano Banana Pro) for the selected agents.
                      Reads GEMINI_API_KEY from the environment or prompts for it (hidden input).
  --no-venv           Don't create .venv; use the system python3 (must already have Pillow)
  --skip-test         Skip the post-install self-test
  --force             Overwrite an existing folder that doesn't look like this skill
  --uninstall         Remove the skill from the selected targets
  -h, --help          Show this help

Examples:
  ./install.sh                                   # Claude Code + Copilot, user scope
  ./install.sh --copilot --project ~/code/my-app # commit .github/skills/... with your app
  GEMINI_API_KEY=... ./install.sh --all --setup-mcp
EOF
}

TARGETS=()
PROJECT=""
LINK=0; SETUP_MCP=0; NO_VENV=0; SKIP_TEST=0; FORCE=0; UNINSTALL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --claude)  TARGETS+=("claude") ;;
    --copilot) TARGETS+=("copilot") ;;
    --agents)  TARGETS+=("agents") ;;
    --all)     TARGETS=("claude" "copilot" "agents") ;;
    --project) PROJECT="${2:?--project needs a directory}"; shift ;;
    --link)    LINK=1 ;;
    --setup-mcp) SETUP_MCP=1 ;;
    --no-venv) NO_VENV=1 ;;
    --skip-test) SKIP_TEST=1 ;;
    --force)   FORCE=1 ;;
    --uninstall) UNINSTALL=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
  shift
done
[[ ${#TARGETS[@]} -eq 0 ]] && TARGETS=("claude" "copilot")

c_green=$'\033[32m'; c_yellow=$'\033[33m'; c_red=$'\033[31m'; c_dim=$'\033[2m'; c_off=$'\033[0m'
ok()   { echo "${c_green}✓${c_off} $*"; }
warn() { echo "${c_yellow}⚠${c_off} $*"; }
err()  { echo "${c_red}✗${c_off} $*" >&2; }

dest_for() {
  local t="$1" base
  if [[ -n "$PROJECT" ]]; then
    base="$(cd "$PROJECT" && pwd)"
    case "$t" in
      claude)  echo "$base/.claude/skills/$SKILL_NAME" ;;
      copilot) echo "$base/.github/skills/$SKILL_NAME" ;;
      agents)  echo "$base/.agents/skills/$SKILL_NAME" ;;
    esac
  else
    case "$t" in
      claude)  echo "$HOME/.claude/skills/$SKILL_NAME" ;;
      copilot) echo "$HOME/.copilot/skills/$SKILL_NAME" ;;
      agents)  echo "$HOME/.agents/skills/$SKILL_NAME" ;;
    esac
  fi
}

is_our_skill() { [[ -f "$1/SKILL.md" ]] && grep -q "^name: $SKILL_NAME" "$1/SKILL.md"; }

# ── Uninstall ────────────────────────────────────────────────────────
if [[ $UNINSTALL -eq 1 ]]; then
  for t in "${TARGETS[@]}"; do
    d="$(dest_for "$t")"
    if [[ -L "$d" ]]; then rm "$d"; ok "removed link $d"
    elif [[ -d "$d" ]]; then
      if is_our_skill "$d" || [[ $FORCE -eq 1 ]]; then rm -rf "$d"; ok "removed $d"
      else err "$d doesn't look like $SKILL_NAME — use --force"; fi
    else echo "${c_dim}- nothing at $d${c_off}"; fi
  done
  if [[ -z "$PROJECT" && -d "$VENV_DIR" ]]; then
    remaining=0
    for base in .claude .copilot .agents; do [[ -e "$HOME/$base/skills/$SKILL_NAME" ]] && remaining=1; done
    if [[ $remaining -eq 0 ]]; then rm -rf "$(dirname "$VENV_DIR")"; ok "removed Python env $(dirname "$VENV_DIR")"
    else echo "${c_dim}- kept shared Python env $VENV_DIR (other installs still use it)${c_off}"; fi
  fi
  exit 0
fi

# ── Python ───────────────────────────────────────────────────────────
PYTHON=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    PYTHON="$(command -v "$cand")"; break
  fi
done
if [[ -z "$PYTHON" ]]; then
  err "Python 3.9+ is required. Install it (macOS: 'brew install python' or python.org; Debian/Ubuntu: 'sudo apt install python3 python3-venv') and re-run."
  exit 1
fi
ok "Python: $PYTHON ($("$PYTHON" --version 2>&1))"

# One shared virtualenv outside the skill folders: agents index every file in a skill
# directory, so a .venv inside it would add thousands of files to each install.
setup_python_env() {  # prints the python path to use
  if [[ $NO_VENV -eq 0 ]]; then
    if [[ ! -x "$VENV_DIR/bin/python" ]]; then
      mkdir -p "$(dirname "$VENV_DIR")"
      if ! "$PYTHON" -m venv "$VENV_DIR" >/dev/null 2>&1; then
        rm -rf "$VENV_DIR"
        warn "could not create a virtualenv (Debian/Ubuntu: sudo apt install python3-venv) — using system Python" >&2
        NO_VENV=1
      fi
    fi
    if [[ $NO_VENV -eq 0 ]]; then
      "$VENV_DIR/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade pip >/dev/null 2>&1 || true
      "$VENV_DIR/bin/python" -m pip install --quiet --disable-pip-version-check -r "$SRC_DIR/requirements.txt" >&2
      echo "$VENV_DIR/bin/python"; return
    fi
  fi
  if ! "$PYTHON" -c 'import PIL' 2>/dev/null; then
    "$PYTHON" -m pip install --user --quiet -r "$SRC_DIR/requirements.txt" >&2 2>/dev/null || {
      err "Pillow is missing and pip couldn't install it. Run: $PYTHON -m pip install Pillow" ; exit 1; }
  fi
  echo "$PYTHON"
}

copy_skill() {  # $1 = destination
  local d="$1"
  mkdir -p "$(dirname "$d")"
  if [[ -e "$d" || -L "$d" ]]; then
    if [[ -L "$d" ]]; then rm "$d"
    elif is_our_skill "$d" || [[ $FORCE -eq 1 ]]; then
      rm -rf "$d"
    else
      err "$d exists and isn't $SKILL_NAME — re-run with --force to overwrite"; exit 1
    fi
  fi
  if [[ $LINK -eq 1 ]]; then
    ln -s "$SRC_DIR" "$d"
    return
  fi
  mkdir -p "$d"
  local items=(SKILL.md README.md LICENSE requirements.txt scripts assets examples)
  for it in "${items[@]}"; do
    [[ -e "$SRC_DIR/$it" ]] && cp -R "$SRC_DIR/$it" "$d/"
  done
  find "$d" \( -name "__pycache__" -o -name ".DS_Store" \) -prune -exec rm -rf {} + 2>/dev/null || true
  return 0
}

self_test() {  # $1 = skill dir, $2 = python
  local dir="$1" py="$2" tmp
  tmp="$(mktemp -d)"
  if "$py" "$dir/scripts/compose.py" --device iphone-6.9 --bg "#2563EB" --verb TEST --desc "INSTALL OK" \
        --screenshot "$dir/examples/sample-phone-portrait.png" --output "$tmp/iphone.png" >/dev/null &&
     "$py" "$dir/scripts/compose.py" --device android-tablet-10 --orientation landscape --skin none --bg "#111827" \
        --verb TEST --desc "TABLET" --screenshot "$dir/examples/sample-android-tablet-landscape.png" --output "$tmp/tab.png" >/dev/null 2>&1 &&
     "$py" "$dir/scripts/validate.py" "$tmp/iphone.png" "$tmp/tab.png" >/dev/null; then
    ok "self-test passed (rendered + validated iPhone and Android tablet scaffolds)"
  else
    err "self-test failed — run: $py $dir/scripts/compose.py --help"
  fi
  rm -rf "$tmp"
  echo "  ${c_dim}headline font: $("$py" "$dir/scripts/fonts.py" | head -1 | sed 's/.*→ //')${c_off}"
}

# ── Install ──────────────────────────────────────────────────────────
INSTALLED=()
for t in "${TARGETS[@]}"; do
  d="$(dest_for "$t")"
  copy_skill "$d"
  if [[ $LINK -eq 1 ]]; then ok "$t → $d ${c_dim}(symlink → $SRC_DIR)${c_off}"; else ok "$t → $d"; fi
  INSTALLED+=("$t|$d")
done
PY_BIN="$(setup_python_env)"
ok "Python env: $PY_BIN ${c_dim}(Pillow $("$PY_BIN" -c 'import PIL; print(PIL.__version__)'))${c_off}"

if [[ $SKIP_TEST -eq 0 ]]; then
  IFS='|' read -r _ d <<< "${INSTALLED[0]}"
  self_test "$d" "$PY_BIN"
fi

# ── Gemini MCP (optional) ────────────────────────────────────────────
write_mcp_json() {  # $1 = copilot-user | vscode-user | vscode-project, $2 = key (copilot-user only)
  "$PYTHON" - "$1" "${2:-}" "$PROJECT" <<'PYEOF'
import json, os, sys
mode, key, project = sys.argv[1], sys.argv[2], sys.argv[3]
home = os.path.expanduser("~")
if mode == "copilot-user":
    path = os.path.join(home, ".copilot", "mcp-config.json")
elif mode == "vscode-project":
    path = os.path.join(project, ".vscode", "mcp.json")
else:
    candidates = [os.path.join(home, "Library", "Application Support", "Code", "User"),
                  os.path.join(home, ".config", "Code", "User")]
    base = next((c for c in candidates if os.path.isdir(c)), None)
    if not base:
        print("SKIP")
        sys.exit(0)
    path = os.path.join(base, "mcp.json")
os.makedirs(os.path.dirname(path), exist_ok=True)
try:
    cfg = json.load(open(path)) if os.path.exists(path) else {}
except json.JSONDecodeError:
    print(f"SKIP-INVALID {path}")
    sys.exit(0)
if mode == "copilot-user":
    cfg.setdefault("mcpServers", {})["gemini"] = {
        "type": "local", "command": "npx", "args": ["-y", "@houtini/gemini-mcp"],
        "env": {"GEMINI_API_KEY": key}, "tools": ["*"]}
else:
    cfg.setdefault("inputs", [])
    if not any(i.get("id") == "gemini-api-key" for i in cfg["inputs"]):
        cfg["inputs"].append({"type": "promptString", "id": "gemini-api-key",
                              "description": "Google AI Studio API key for Gemini / Nano Banana Pro",
                              "password": True})
    cfg.setdefault("servers", {})["gemini"] = {
        "type": "stdio", "command": "npx", "args": ["-y", "@houtini/gemini-mcp"],
        "env": {"GEMINI_API_KEY": "${input:gemini-api-key}"}}
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
if mode == "copilot-user":
    os.chmod(path, 0o600)
print(path)
PYEOF
}

if [[ $SETUP_MCP -eq 1 ]]; then
  echo
  if ! command -v npx >/dev/null 2>&1; then
    warn "npx (Node.js 18+) not found — install Node.js from https://nodejs.org, then re-run with --setup-mcp"
  else
    KEY="${GEMINI_API_KEY:-}"
    if [[ -z "$KEY" ]] && [[ " ${TARGETS[*]} " == *" claude "* || " ${TARGETS[*]} " == *" copilot "* ]] && [[ -t 0 ]]; then
      read -r -s -p "Gemini API key (https://aistudio.google.com/apikey): " KEY; echo
    fi
    for t in "${TARGETS[@]}"; do
      case "$t" in
        claude)
          if command -v claude >/dev/null 2>&1 && [[ -n "$KEY" ]]; then
            scope="user"; [[ -n "$PROJECT" ]] && scope="local"
            claude mcp remove gemini -s "$scope" >/dev/null 2>&1 || true
            if (cd "${PROJECT:-$HOME}" && claude mcp add -e GEMINI_API_KEY="$KEY" -s "$scope" gemini -- npx -y @houtini/gemini-mcp >/dev/null); then
              ok "Claude Code: gemini MCP added ($scope scope) — check with: claude mcp get gemini"
            else warn "Claude Code: 'claude mcp add' failed — see README → Gemini MCP setup"; fi
          else
            warn "Claude Code: 'claude' CLI or API key not available — see README → Gemini MCP setup"
          fi ;;
        copilot)
          if [[ -n "$KEY" ]]; then
            ok "Copilot CLI: gemini MCP added to $(write_mcp_json copilot-user "$KEY") — check with /mcp"
          else
            warn "Copilot CLI: no API key given — skipped ~/.copilot/mcp-config.json"
          fi
          if [[ -n "$PROJECT" ]]; then
            ok "VS Code: gemini MCP added to $(write_mcp_json vscode-project) (VS Code asks for the key on first start)"
          else
            r="$(write_mcp_json vscode-user)"
            case "$r" in
              SKIP) echo "  ${c_dim}VS Code user folder not found — skipped VS Code mcp.json${c_off}" ;;
              SKIP-INVALID*) warn "VS Code: ${r#SKIP-INVALID } isn't valid JSON — add the server manually (README)" ;;
              *) ok "VS Code: gemini MCP added to $r (VS Code asks for the key on first start)" ;;
            esac
          fi ;;
        agents) : ;;
      esac
    done
  fi
fi

# ── Next steps ───────────────────────────────────────────────────────
echo
echo "Next steps"
for entry in "${INSTALLED[@]}"; do
  IFS='|' read -r t d <<< "$entry"
  case "$t" in
    claude)  echo "  • Claude Code: start 'claude' in your app's folder and run ${c_green}/$SKILL_NAME${c_off}" ;;
    copilot) echo "  • Copilot CLI: run '/skills reload' then '/skills info $SKILL_NAME'; use ${c_green}/$SKILL_NAME${c_off}"
             echo "  • VS Code (Copilot agent mode): type ${c_green}/$SKILL_NAME${c_off} in Chat, or Chat: Open Customizations → Skills" ;;
    agents)  echo "  • Other Agent Skills agents: the skill is in $d" ;;
  esac
done
[[ $SETUP_MCP -eq 0 ]] && echo "  • Optional AI polish: re-run with --setup-mcp (needs Node.js + a Gemini API key), or see README"
