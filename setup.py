#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "rich>=13",
# ]
# ///
#
# Configures kenn.io agentic workflow tooling for this machine and/or a repo.
#
# Usage:
#   ./setup.py                  global + repo init (if cwd is a git repo)
#   ./setup.py --global-only    tools and Claude Code hooks only
#   ./setup.py --repo-only      repo init only (kata + roborev in cwd)

import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.syntax import Syntax

console = Console()

def step(msg: str) -> None:
    console.print(f"\n[bold blue]▶ {msg}[/]")

def ok(msg: str) -> None:
    console.print(f"  [green]✓[/] {msg}")

def skip(msg: str) -> None:
    console.print(f"  [dim]– {msg}[/]")

def warn(msg: str) -> None:
    console.print(f"  [yellow]⚠[/]  {msg}")

def die(msg: str) -> None:
    console.print(f"\n[red]error:[/] {msg}")
    sys.exit(1)


def run(args: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a command, streaming output unless capture=True."""
    if capture:
        return subprocess.run(args, capture_output=True, text=True, check=check)
    return subprocess.run(args, check=check)


def cmd_exists(name: str) -> str | None:
    """Return the full path if the command exists, else None."""
    # Also check ~/go/bin for go-installed tools not yet on PATH
    extra = [str(Path.home() / "go" / "bin")]
    path = os.environ.get("PATH", "")
    search = path + os.pathsep + os.pathsep.join(extra)
    return shutil.which(name, path=search)


def cmd_version(name: str, *args: str) -> str:
    """Return the first line of a version command, or empty string on failure."""
    binary = cmd_exists(name)
    if not binary:
        return ""
    try:
        result = subprocess.run([binary, *args], capture_output=True, text=True, timeout=5)
        return result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    except Exception:
        return ""


def in_git_repo() -> bool:
    r = subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True)
    return r.returncode == 0


def git_repo_root() -> Path:
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
    return Path(r.stdout.strip())


def add_claude_stop_hook(command: str) -> bool:
    """
    Merge a Stop hook into ~/.claude/settings.json.
    Returns True if added, False if the command was already present.
    """
    settings_path = Path.home() / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    cfg: dict = {}
    if settings_path.exists():
        with settings_path.open() as f:
            cfg = json.load(f)

    hooks = cfg.setdefault("hooks", {})
    stop: list = hooks.setdefault("Stop", [])

    existing_commands = {
        h.get("command", "")
        for group in stop
        for h in group.get("hooks", [])
    }
    if command in existing_commands:
        return False

    stop.append({"matcher": "", "hooks": [{"type": "command", "command": command}]})

    with settings_path.open("w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")

    return True


def sync_agent_contract() -> None:
    """
    Copy AGENTS.md to ~/.claude/agentic-workflows.md and ensure ~/.claude/CLAUDE.md
    imports it. On re-runs, diffs the source against the installed copy and updates
    only if changed.
    """
    source = Path(__file__).parent / "AGENTS.md"
    if not source.exists():
        warn(f"AGENTS.md not found alongside setup.py — skipping contract sync")
        return

    target = Path.home() / ".claude" / "agentic-workflows.md"
    claude_md = Path.home() / ".claude" / "CLAUDE.md"
    import_line = "@agentic-workflows.md"

    new_content = source.read_text()

    # ── sync the contract file ─────────────────────────────────────────────────
    if target.exists():
        old_content = target.read_text()
        if old_content == new_content:
            skip("agent contract already up to date (~/.claude/agentic-workflows.md)")
        else:
            diff_lines = list(difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile="installed",
                tofile="source",
            ))
            additions = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
            removals  = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
            target.write_text(new_content)
            ok(f"agent contract updated ([green]+{additions}[/] / [red]-{removals}[/] lines)")
            if len(diff_lines) <= 40:
                console.print(Syntax("".join(diff_lines), "diff", theme="ansi_dark", line_numbers=False))
            else:
                console.print(f"  [dim](diff too large to display inline — {len(diff_lines)} lines)[/]")
    else:
        target.write_text(new_content)
        ok(f"agent contract installed → ~/.claude/agentic-workflows.md")

    # ── ensure CLAUDE.md imports it ────────────────────────────────────────────
    if claude_md.exists():
        existing = claude_md.read_text()
        if import_line in existing:
            skip("~/.claude/CLAUDE.md already imports agentic-workflows.md")
        else:
            claude_md.write_text(import_line + "\n\n" + existing)
            ok("added @agentic-workflows.md import to ~/.claude/CLAUDE.md")
    else:
        claude_md.write_text(import_line + "\n")
        ok("created ~/.claude/CLAUDE.md with @agentic-workflows.md import")


# ── argument parsing ──────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(
    description="Set up kenn.io agentic workflow tooling.",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=(
        "Run without flags from a git repo root to do everything.\n"
        "Re-running is safe — all steps are idempotent."
    ),
)
parser.add_argument("--global-only", action="store_true", help="install tools and configure Claude Code hooks only")
parser.add_argument("--repo-only",   action="store_true", help="initialise current repo only (kata + roborev)")
args = parser.parse_args()

do_global = not args.repo_only
do_repo   = not args.global_only


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — global tool installation + Claude Code hooks
# ══════════════════════════════════════════════════════════════════════════════

if do_global:

    step("Checking required tools")

    # ── kata ──────────────────────────────────────────────────────────────────
    if cmd_exists("kata"):
        skip(f"kata already installed ({cmd_version('kata', 'version')})")
    else:
        console.print("  installing kata…")
        if cmd_exists("brew"):
            run(["brew", "install", "kata"])
        else:
            run(["bash", "-c", "curl -fsSL https://katatracker.com/install.sh | bash"])
        ok("kata installed")

    # ── roborev ───────────────────────────────────────────────────────────────
    if cmd_exists("roborev"):
        skip(f"roborev already installed ({cmd_version('roborev', 'version')})")
    else:
        console.print("  installing roborev…")
        if cmd_exists("brew"):
            run(["brew", "install", "kenn-io/tap/roborev"])
        else:
            run(["bash", "-c", "curl -fsSL https://roborev.dev/install.sh | bash"])
        ok("roborev installed")

    # ── kwt ───────────────────────────────────────────────────────────────────
    if cmd_exists("kwt"):
        skip(f"kwt already installed ({cmd_version('kwt', 'version')})")
    elif cmd_exists("go"):
        console.print("  installing kwt via go install…")
        run(["go", "install", "go.kenn.io/kwt/cmd/kwt@latest"])
        gobin = Path.home() / "go" / "bin"
        os.environ["PATH"] = str(gobin) + os.pathsep + os.environ.get("PATH", "")
        ok(f"kwt installed — add [dim]{gobin}[/] to your PATH")
    else:
        warn("kwt not installed — Go is required ([dim]brew install go[/]) or use the version bundled in Ghosthub.app")

    # ── roborev daemon ────────────────────────────────────────────────────────
    step("Ensuring roborev daemon is running")
    result = run(["roborev", "status"], check=False, capture=True)
    if result.returncode == 0:
        skip("roborev daemon already running")
    else:
        run(["roborev", "daemon", "start"], check=False, capture=True)
        ok("roborev daemon started")

    # ── roborev Claude Code skills ────────────────────────────────────────────
    step("Installing roborev Claude Code skills")
    run(["roborev", "skills", "install"])
    ok("skills installed (idempotent)")

    # ── Claude Code global Stop hooks ─────────────────────────────────────────
    step("Configuring Claude Code global Stop hooks")

    console.print("  adding roborev agent hook…")
    run(["roborev", "agent-hook", "install"])
    ok("roborev Stop hook installed")

    console.print("  adding kata claimed-issues hook…")
    kata_hook = (
        "bash -c 'issues=$(kata list --owner \"${KATA_AUTHOR:-$USER}\" --status open --agent 2>/dev/null); "
        "[ -n \"$issues\" ] && "
        "printf \"[kata] Open claimed issues — close or unassign before stopping:\\n%s\\n\" \"$issues\"'"
    )
    if add_claude_stop_hook(kata_hook):
        ok("kata Stop hook added to ~/.claude/settings.json")
    else:
        skip("kata Stop hook already present")

    # ── global agent contract ─────────────────────────────────────────────────
    step("Syncing agent contract to global Claude memory")
    sync_agent_contract()


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — per-repo initialisation
# ══════════════════════════════════════════════════════════════════════════════

if do_repo:

    if not in_git_repo():
        if do_global:
            warn("current directory is not a git repo — skipping repo init (re-run from a repo root, or use --repo-only)")
        else:
            die("not inside a git repository")
    else:
        repo_root = git_repo_root()
        repo_name = repo_root.name
        step(f"Initialising repo: {repo_root}")

        # ── kata ──────────────────────────────────────────────────────────────
        if (repo_root / ".kata.toml").exists():
            skip("kata already initialised (.kata.toml exists)")
        else:
            console.print("  running kata init…")
            # --with-hooks:  installs kata work.attention hooks into .claude/
            # --with-agents: writes kata guidance into AGENTS.md / CLAUDE.md
            run(["kata", "init", "--with-hooks", "--with-agents"])
            ok(f"kata initialised for project: {repo_name}")

        # ── roborev ───────────────────────────────────────────────────────────
        post_commit = repo_root / ".git" / "hooks" / "post-commit"
        roborev_cfg = repo_root / ".roborev.toml"
        if post_commit.exists() or roborev_cfg.exists():
            skip("roborev already initialised")
        else:
            console.print("  running roborev init…")
            run(["roborev", "init", "--agent", "claude-code"])
            ok("roborev initialised (post-commit hook installed)")

        # ── roborev agent hook ────────────────────────────────────────────────
        console.print("  installing roborev agent-hook…")
        run(["roborev", "agent-hook", "install"])
        ok("roborev agent-hook installed")

        console.print()
        console.print(f"  [bold]Repo ready.[/] Every commit will now be reviewed automatically.")
        console.print(f"  [dim]Monitor: roborev tui   |   Issues: kata tui[/]")


# ══════════════════════════════════════════════════════════════════════════════

console.print()
console.print("[bold green]Setup complete.[/]")
console.print()
console.print("  [bold]Global[/]")
console.print(f"    kata:     {cmd_version('kata', 'version') or '[yellow]check installation[/]'}")
console.print(f"    roborev:  {cmd_version('roborev', 'version') or '[yellow]check installation[/]'}")
console.print(f"    kwt:      {cmd_version('kwt', 'version') or '[yellow]not in PATH — install separately or use Ghosthub bundle[/]'}")
console.print()
console.print("  [bold]Next steps[/]")
script_path = Path(__file__).resolve()
console.print(f"    1. From each repo you work in:  [dim]uv run {script_path} --repo-only[/]")
console.print(f"    2. Check Claude Code hooks:     [dim]cat ~/.claude/settings.json | python3 -m json.tool[/]")
console.print(f"    3. Read the agent contract:     [dim]cat {script_path.parent / 'AGENTS.md'}[/]")
