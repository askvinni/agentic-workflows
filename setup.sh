#!/usr/bin/env bash
# setup.sh — configure kenn.io agentic workflow tooling
#
# Global setup (tools + Claude Code hooks): run from anywhere
# Repo setup (kata/roborev init):           run from a git repo root
#
# Usage:
#   ./setup.sh                  global + repo init (if cwd is a git repo)
#   ./setup.sh --global-only    tools and hooks only; skip repo init
#   ./setup.sh --repo-only      repo init only; skip tool installation

set -euo pipefail

# ── colour helpers ────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  BOLD='\033[1m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
  RED='\033[0;31m'; BLUE='\033[0;34m'; DIM='\033[2m'; NC='\033[0m'
else
  BOLD=''; GREEN=''; YELLOW=''; RED=''; BLUE=''; DIM=''; NC=''
fi

step()  { echo -e "\n${BOLD}${BLUE}▶ $*${NC}"; }
ok()    { echo -e "  ${GREEN}✓${NC} $*"; }
skip()  { echo -e "  ${DIM}– $*${NC}"; }
warn()  { echo -e "  ${YELLOW}⚠${NC}  $*"; }
die()   { echo -e "\n${RED}error:${NC} $*" >&2; exit 1; }

# ── argument parsing ──────────────────────────────────────────────────────────
DO_GLOBAL=true
DO_REPO=true

for arg in "$@"; do
  case $arg in
    --global-only) DO_REPO=false ;;
    --repo-only)   DO_GLOBAL=false ;;
    --help|-h)
      sed -n '3,9p' "$0" | sed 's/^# \{0,2\}//'
      exit 0
      ;;
    *) die "unknown argument: $arg (try --help)" ;;
  esac
done

# ── helpers ───────────────────────────────────────────────────────────────────
in_git_repo() { git rev-parse --git-dir &>/dev/null; }

cmd_exists() { command -v "$1" &>/dev/null; }

# Merge a new Stop hook entry into ~/.claude/settings.json only if the
# command string is not already present anywhere in the Stop array.
add_claude_stop_hook() {
  local command="$1"
  local settings="$HOME/.claude/settings.json"

  [[ -f "$settings" ]] || echo '{}' > "$settings"

  python3 - "$settings" "$command" <<'EOF'
import json, sys

path, command = sys.argv[1], sys.argv[2]

with open(path) as f:
    cfg = json.load(f)

hooks = cfg.setdefault("hooks", {})
stop  = hooks.setdefault("Stop", [])

# Check if this command is already registered
existing = {h.get("command","") for g in stop for h in g.get("hooks",[])}
if command in existing:
    print("already present")
    sys.exit(0)

stop.append({"matcher": "", "hooks": [{"type": "command", "command": command}]})

with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")

print("added")
EOF
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — global tool installation + Claude Code hooks
# ══════════════════════════════════════════════════════════════════════════════
if $DO_GLOBAL; then

  step "Checking required tools"

  # ── kata ──────────────────────────────────────────────────────────────────
  if cmd_exists kata; then
    skip "kata already installed ($(kata version 2>/dev/null | head -1))"
  else
    echo "  installing kata..."
    if cmd_exists brew; then
      brew install kata
    else
      curl -fsSL https://katatracker.com/install.sh | bash
    fi
    ok "kata installed"
  fi

  # ── roborev ───────────────────────────────────────────────────────────────
  if cmd_exists roborev; then
    skip "roborev already installed ($(roborev version 2>/dev/null | head -1))"
  else
    echo "  installing roborev..."
    if cmd_exists brew; then
      brew install kenn-io/tap/roborev
    else
      curl -fsSL https://roborev.dev/install.sh | bash
    fi
    ok "roborev installed"
  fi

  # ── kwt ───────────────────────────────────────────────────────────────────
  if cmd_exists kwt; then
    skip "kwt already installed"
  elif [[ -x "$HOME/go/bin/kwt" ]]; then
    export PATH="$HOME/go/bin:$PATH"
    skip "kwt already installed (~/go/bin)"
  elif cmd_exists go; then
    echo "  installing kwt via go install..."
    go install go.kenn.io/kwt/cmd/kwt@latest
    export PATH="$HOME/go/bin:$PATH"
    ok "kwt installed (add ~/go/bin to your PATH to use it)"
  else
    warn "kwt not installed — Go is required (brew install go) or use the version bundled in Ghosthub.app"
  fi

  # ── roborev daemon ────────────────────────────────────────────────────────
  step "Ensuring roborev daemon is running"
  if roborev status &>/dev/null; then
    skip "roborev daemon already running"
  else
    roborev daemon start &>/dev/null || true
    ok "roborev daemon started"
  fi

  # ── roborev global skills ─────────────────────────────────────────────────
  step "Installing roborev Claude Code skills"
  roborev skills install
  ok "skills installed (idempotent)"

  # ── Claude Code global hooks ──────────────────────────────────────────────
  step "Configuring Claude Code global Stop hooks"

  # roborev: surface open review findings before session ends
  echo "  adding roborev agent hook..."
  roborev agent-hook install
  ok "roborev Stop hook installed"

  # kata: warn if agent has claimed-but-unclosed issues at session end
  KATA_HOOK='bash -c '"'"'issues=$(kata list --owner "${KATA_AUTHOR:-$USER}" --status open --agent 2>/dev/null); [ -n "$issues" ] && printf "[kata] Open claimed issues — close or unassign before stopping:\n%s\n" "$issues"'"'"''

  echo "  adding kata claimed-issues hook..."
  result=$(add_claude_stop_hook "$KATA_HOOK")
  if [[ "$result" == "already present" ]]; then
    skip "kata Stop hook already present"
  else
    ok "kata Stop hook added to ~/.claude/settings.json"
  fi

fi # DO_GLOBAL


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — per-repo initialisation
# ══════════════════════════════════════════════════════════════════════════════
if $DO_REPO; then

  if ! in_git_repo; then
    if $DO_GLOBAL; then
      warn "current directory is not a git repo — skipping repo init (re-run from a repo root, or use --repo-only)"
    else
      die "not inside a git repository"
    fi
  else

    REPO_ROOT=$(git rev-parse --show-toplevel)
    REPO_NAME=$(basename "$REPO_ROOT")
    step "Initialising repo: $REPO_ROOT"

    # ── kata ──────────────────────────────────────────────────────────────
    if [[ -f "$REPO_ROOT/.kata.toml" ]]; then
      skip "kata already initialised (.kata.toml exists)"
    else
      echo "  running kata init..."
      # --with-hooks: installs kata work.attention hooks into .claude/
      # --with-agents: writes kata guidance into AGENTS.md / CLAUDE.md
      kata init --with-hooks --with-agents
      ok "kata initialised for project: $REPO_NAME"
    fi

    # ── roborev ───────────────────────────────────────────────────────────
    if [[ -f "$REPO_ROOT/.roborev.toml" ]] || [[ -f "$REPO_ROOT/.git/hooks/post-commit" ]]; then
      skip "roborev already initialised"
    else
      echo "  running roborev init..."
      roborev init --agent claude-code
      ok "roborev initialised (post-commit hook installed)"
    fi

    # ── roborev agent hook (repo scope) ───────────────────────────────────
    echo "  installing roborev agent-hook for this repo..."
    roborev agent-hook install
    ok "roborev agent-hook installed"

    echo ""
    echo -e "  ${BOLD}Repo ready.${NC} Every commit will now be reviewed automatically."
    echo -e "  ${DIM}Monitor: roborev tui   |   Issues: kata tui${NC}"

  fi

fi # DO_REPO


# ══════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${GREEN}Setup complete.${NC}"
echo ""
echo -e "  ${BOLD}Global${NC}"
echo -e "    kata:     $(kata version 2>/dev/null | head -1 || echo 'check installation')"
echo -e "    roborev:  $(roborev version 2>/dev/null | head -1 || echo 'check installation')"
echo -e "    kwt:      $(kwt version 2>/dev/null | head -1 || echo 'not in PATH — install separately or use Ghosthub bundle')"
echo ""
echo -e "  ${BOLD}Next steps${NC}"
echo -e "    1. From each repo you work in:  ${DIM}$(realpath "$0") --repo-only${NC}"
echo -e "    2. Check Claude Code hooks:     ${DIM}cat ~/.claude/settings.json | python3 -m json.tool${NC}"
echo -e "    3. Read the agent contract:     ${DIM}cat $(dirname "$(realpath "$0")")/AGENTS.md${NC}"
