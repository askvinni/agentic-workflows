# Agentic Workflows

Local environment setup using [kenn.io](https://kenn.io) tooling and [engram](https://github.com/askvinni/engram) for human-assisted and fully-autonomous agentic software work.

## Overview

Five tools form the stack:

| Tool | Purpose | Who uses it |
|---|---|---|
| [kata](#kata) | Local-first issue ledger | Agents + human |
| [roborev](#roborev) | Continuous AI code review | Agents + human |
| [kwt](#kwt) | Git worktree manager | Agents + human |
| [engram](#engram) | Persistent memory management | Agents + human |
| [ghosthub](#ghosthub) | Native terminal multiplexer | Human only |

---

## kata

**[katatracker.com](https://www.katatracker.com) · [GitHub](https://github.com/kenn-io/kata)**

kata is a local-first issue tracker designed for the machine where code gets written. It runs a local SQLite-backed daemon that answers queries in ~4 ms — about 60× faster than a GitHub API round-trip — making it practical for agents to hit on every loop iteration.

### Why it exists

SaaS trackers (Linear, Jira, GitHub Issues) coordinate teams and organizations. kata coordinates the development machine itself: agents can fan out work, claim issues atomically, and stream events at loop speed without going to the network.

### Installation

```sh
brew install kata
```

### Key capabilities

- **CLI + TUI + Web UI + MCP server** — every surface supported
- **Atomic claims** — `kata claim` is atomic; two agents cannot double-claim
- **Evidence-based closes** — commits, test results, and prose are required; lazy closes are blocked
- **Relationships** — parent/child, blocks/blocked-by, related
- **Federation** — optional remote daemon or multi-machine hub for team sharing
- **Event stream** — `kata events --tail` for live updates between agents

### Basic human workflow

```sh
kata init                         # bind current directory to a project
kata tui                          # interactive issue browser
kata ui                           # open web UI
kata create "my task" --body "..."
kata list
kata show abc4
kata close abc4 --done --message "Done" --commit <sha>
```

### Agent contract

Agents should run `kata quickstart` for the authoritative usage contract. See [AGENTS.md](./AGENTS.md#kata--issue-ledger) for the condensed version.

---

## roborev

**[GitHub](https://github.com/kenn-io/roborev)**

roborev automatically reviews every commit via a git post-commit hook, running the review in the background using an AI agent (Claude Code, Copilot, Gemini, Cursor, and others). Findings surface in a TUI and browser UI before they compound into larger problems.

### Installation

```sh
curl -fsSL https://roborev.dev/install.sh | bash
# or: brew install kenn-io/tap/roborev
```

### Setup per repo

```sh
cd my-repo
roborev init                  # installs post-commit hook
roborev agent-hook install    # optional: hooks for the coding agent harness
roborev skills install        # optional: installs /roborev-fix skill for Claude Code
```

### Daily usage

```sh
roborev status                # daemon health and queue
roborev tui                   # interactive terminal UI
roborev ui                    # open browser UI

roborev show                  # review for HEAD
roborev show abc123           # review for specific commit
roborev list                  # all jobs on current branch
```

### Review types

| Flag | Focus |
|---|---|
| (default) | General correctness, complexity, dead code, duplication |
| `--type security` | Security-focused |
| `--type design` | Architecture and design |
| `--type lookahead` | Time-series look-ahead bias |

### Fixing findings

```sh
roborev fix               # single-pass: agent fixes open findings, commits
roborev refine            # automated loop: fix → commit → re-review → repeat until pass
```

`refine` is fully autonomous but requires a clean working tree and a feature branch.

---

## kwt

**[kwt.sh](https://kwt.sh) · [GitHub](https://github.com/kenn-io/ghosthub)**

kwt manages git worktrees as isolated branch checkouts, each with its own tmux workspace. It prevents multiple branches from sharing a working directory and provides safe, generation-tracked change inspection.

### Installation

```sh
go install go.kenn.io/kwt/cmd/kwt@latest
# Requires: Go 1.27+, Git 2.20+, tmux 2.1+
# Also bundled inside Ghosthub.app
```

> **Note:** `kwt` is not currently in PATH on this machine. Install it or use the version inside `/Applications/Ghosthub.app/Contents/MacOS/KwtRemote`.

### Core concept

Running `kwt` inside any git repo registers it automatically. The dashboard shows all registered projects and their linked worktrees.

```sh
kwt                          # open dashboard (registers current repo on first run)
kwt add -b feature/foo       # create a new worktree for a branch
kwt changes feature/foo      # inspect what changed (required before kwt open)
kwt open feature/foo         # launch tmux workspace for the worktree
kwt exec feature/foo -- make test   # run a command inside the worktree
kwt status                   # view all worktrees across all projects
kwt remove feature/foo       # safely remove (blocked if uncommitted changes)
kwt doctor                   # diagnose and repair worktree issues
kwt prune                    # remove stale or merged worktrees
```

### Safety model

New worktrees from existing branches start **inert** — workspace launch and setup scripts do not run automatically. You (or an agent) must explicitly call `kwt open` after reviewing `kwt changes`. This prevents accidental execution of untrusted branch code.

### Pull request workflow

```sh
kwt pr import <pr-url>    # isolated checkout for a PR; preserves contributor's push target
kwt pr attach <ref>       # explicitly open the PR worktree after review
```

### Agent integration

kwt outputs JSON (`--json`) for programmatic use. Agents can create worktrees, execute commands in them, inspect file changes with generation tracking, and remove them safely. See [AGENTS.md](./AGENTS.md#kwt--git-worktree-manager).

---

## ghosthub

**[GitHub](https://github.com/kenn-io/ghosthub)**

Ghosthub is a native macOS terminal application that presents all your tmux, Herdr, and Zellij sessions — local and remote — in a single unified interface. It does not force a common abstraction; each multiplexer keeps its own panes, layouts, key bindings, and processes.

### Installation

```sh
brew install kenn-io/tap/ghosthub
# or download the DMG from GitHub releases
```

### Requirements

- Apple Silicon Mac, macOS 26 (Tahoe) or newer
- tmux 3.2+, Herdr 0.8.0+, or Zellij 0.44+ (whichever you use)
- SSH key-based auth for remote hosts

### Key features

- **Unified session browser** — Command Palette searches sessions and actions across all machines
- **Git worktree management** — bundled kwt creates branches, imports PRs, manages worktrees without leaving the app
- **SSH resilience** — keepalive and automatic reconnection for remote sessions
- **Native rendering** — independent macOS windows and tabs via embedded libghostty

### Relationship to agents

Agents do not interact with Ghosthub directly. Worktrees created by kwt (whether from an agent or the CLI) appear automatically in Ghosthub's session list. Remote kata daemons reachable over SSH are addressable via `KATA_SERVER=http://<host>:<port>`.

---

## engram

**[GitHub](https://github.com/askvinni/engram)**

engram is a memory management system for AI-assisted development. It captures institutional knowledge — architectural decisions, discovered gotchas, recurring patterns — from completed work and surfaces it automatically in future Claude sessions. Without it, agents start every session blank and repeat the same mistakes.

### Why it exists

SaaS context tools pass a summary into each session. engram instead writes durable, structured memory files into the repo itself, versioned alongside the code, with routing conditions so agents self-select only the files relevant to what they're working on.

### Installation

```sh
cargo install --git https://github.com/askvinni/engram
# Requires: Rust (stable), gh CLI authenticated, Claude Code
```

### Setup per repo

```sh
cd my-repo
engram init    # creates .engram/, ensures GitHub labels, installs Claude Code skills
```

Re-run `engram init` after upgrading to sync skills.

### Core workflow

```sh
# 1. Start work: create a plan issue (why, approach, acceptance criteria)
engram plan new "Replace auth middleware"

# 2. Work normally on a branch; open a PR with "closes #N" in the body

# 3. After merging: synthesize learnings into memory files and close the issue
engram plan land <issue-number>

# Memory files auto-inject into CLAUDE.md for all future sessions
```

### Key commands

```sh
engram plan new <title>       # create a GitHub issue as a plan
engram plan land <N>          # synthesize learnings after merge, close issue + branch
engram plan learn <N>         # generate memory files without closing the issue
engram plan learn --all       # batch-process all closed issues
engram plan list              # show open plan issues
engram plan status            # show linked issue/PR for the current branch
engram compact                # audit and remove low-quality or stale memory files
engram objective new/plan/view  # track multi-PR work under a shared goal
engram doctor                 # verify dependencies and config
```

### Memory categories

| Category | What gets stored |
|---|---|
| `patterns/` | Recurring solutions and idioms discovered during implementation |
| `tripwires/` | Bugs, gotchas, and approaches that failed — with reasons |
| `architecture/` | Structural decisions and their rationale |
| `testing/` | Test strategies, fixtures, and codebase constraints |

Each memory file includes `read_when` routing conditions so agents load only what's relevant.

### Claude Code skills

- `/engram-plan <title>` — guided plan drafting with source file context
- `/engram-learn` — memory review and workflow guidance
- `/engram-memory` — navigate and evaluate memory files

### Agent contract

See [AGENTS.md](./AGENTS.md#engram--memory-management) for the condensed agent contract.

---

## Tackling a big issue end to end

This walkthrough covers a substantial piece of work — say, refactoring authentication across several services. Each step is labeled **[Human]** or **[Agent]** to make ownership explicit. Steps marked **[Auto]** happen without anyone asking.

### 1. One-time repo setup `[Human]`

Do this once per repo before any agent touches it.

```sh
# From the agentic-workflows directory — sets up tools, Claude Code hooks, and the current repo
uv run setup.py

# Or separately:
uv run setup.py --global-only   # tools + hooks only (first time on a new machine)
uv run setup.py --repo-only     # initialise a specific repo (run from that repo's root)
```

`setup.py` is idempotent — re-running it is safe at any time. It installs kata, roborev, kwt, and engram if missing; configures global Claude Code Stop hooks; and when run from a git repo, runs `kata init`, `roborev init`, `engram init`, and wires up agent hooks for that repo.

After repo setup, every commit triggers a background AI review automatically — you don't have to think about it again. The agent will be shown any open review findings before it finishes a session.

### 2. Break the work into issues `[Human]`

You own the decomposition. The agent will work from what you put here, so specificity matters — vague issues produce vague work.

```sh
kata tui    # interactive TUI for creating and linking issues
```

Or from the CLI:

```sh
# Top-level issue
kata create "Refactor auth across all services" \
  --body "Session tokens don't meet compliance requirements. Replace middleware in api, worker, and gateway." \
  --priority 0

# Sub-tasks linked to the parent; dependencies encoded with --blocked-by
kata create "Replace auth middleware in api service" --parent <parent-ref>
kata create "Replace auth middleware in worker service" --parent <parent-ref> --blocked-by <api-ref>
kata create "Replace auth middleware in gateway service" --parent <parent-ref> --blocked-by <api-ref>
kata create "Update integration tests for new auth flow" --parent <parent-ref> --blocked-by <api-ref>
```

The `--blocked-by` flags are load-bearing: they prevent the agent from picking up downstream tasks before the prerequisite is proven. You can view the full tree in `kata tui` or `kata ui`.

### 3. Create an isolated worktree `[Human]`

Rather than working on a shared branch, give this effort its own checkout so parallel agent sessions can't collide.

```sh
kwt add -b refactor/auth-middleware
kwt open refactor/auth-middleware    # launches a dedicated tmux session
```

Ghosthub shows the new session in its sidebar immediately. For parallel agents, each gets its own branch and worktree — kwt enforces that no two sessions share a directory.

### 4. Agent picks up and works `[Agent]`

Inside Claude Code (or any agent configured against this environment), the agent follows the contract in `AGENTS.md`:

```sh
# Agent finds the highest-priority unclaimed issue
kata next --unowned --agent

# Agent claims it atomically (fails if another agent got there first)
kata claim <ref>
```

The agent writes code, runs tests, and commits. It does not close the issue until the work is verified. Each commit triggers a roborev review automatically.

```sh
# Agent closes with substantive evidence when done
kata close <ref> --done \
  --message "Replaced SessionMiddleware with JWTMiddleware in api/middleware/auth.go. Unit and integration tests pass." \
  --commit <sha>
```

If the agent gets stuck or leaves work incomplete, it labels and comments rather than closing:

```sh
kata label add <ref> needs-review
kata comment <ref> --body "Attempted X, blocked by Y. Next step: Z."
```

### 5. Roborev reviews every commit `[Auto]`

The post-commit hook fires on every commit the agent makes. Reviews run in the background — no human or agent needs to trigger them.

When the agent's session ends, the `Stop` hook (installed by `roborev agent-hook install`) surfaces any open findings before the session closes. The agent either addresses them immediately or they remain queued for the next session.

You can watch the queue from Ghosthub or a terminal at any time:

```sh
roborev tui    # live view of review jobs and findings
roborev ui     # browser UI
```

### 6. Decide how to handle findings `[Human decision → Agent execution]`

This is the key human judgment point. When findings surface, you choose the mode:

**Hands-off — let the agent loop autonomously:**
```sh
roborev refine    # review → fix → commit → re-review → repeat until pass (max 10 iterations)
                  # runs in an isolated worktree; your branch is untouched during the loop
```

**Single pass — agent fixes once, you review the result:**
```sh
roborev fix       # agent addresses all open findings and commits; no re-review
```

**Manual — you review first, then decide:**
```sh
roborev show             # read the findings for HEAD
roborev show --job 42    # specific job
# then fix yourself or hand back to the agent
```

The default in this environment is to let `refine` handle it. Only intervene if findings require a design decision the agent can't resolve from the codebase alone.

### 7. Downstream tasks unlock automatically `[Auto → Agent]`

When the agent closes `<api-ref>`, kata removes its `blocked-by` edge on the dependent tasks. They become ready without any human action.

The agent (or you, to kick off a new session) checks:

```sh
kata ready --unowned --agent    # lists tasks with no remaining open blockers
```

Each ready task can go to a separate agent on its own worktree — the pattern scales to as many parallel agents as you want.

### 8. Human reviews before parent closes `[Human]`

Before closing the top-level issue, check the branch review:

```sh
roborev review --branch    # reviews the full commit range on this branch vs main
roborev show               # read the result
```

Once satisfied, close the parent. kata will refuse the close if any child issue is still open — a hard guardrail:

```sh
kata close <parent-ref> --done \
  --message "Auth middleware replaced in api, worker, and gateway. Integration tests passing. Branch review clean." \
  --commit <final-sha>
```

### 9. Clean up `[Human]`

After the branch is merged:

```sh
kwt prune                         # removes worktrees for merged/deleted branches
# or a specific one:
kwt remove refactor/auth-middleware
```

---

## Enforcing behavior with hooks

The tools work together, but hooks make the critical behaviors automatic rather than voluntary.

### What's already in place

| Hook | Type | What it enforces |
|---|---|---|
| git post-commit | git hook (roborev) | Every commit is reviewed; no agent action required |
| Pre/PostToolUse | Claude Code (beamy logger) | All tool calls are logged to `~/.beamy/claude_tool_calls.jsonl` |

### What `roborev agent-hook install` adds

Running this command writes a **Stop hook** into `~/.claude/settings.json`. When the agent is about to end its session, the hook calls `roborev agent-hook run`, which:

- Checks for open review findings on the current branch
- Surfaces them as agent-visible output before the session closes
- Optionally blocks the stop until findings are addressed (configurable)

This is the most important single hook to install — it closes the loop between "agent commits code" and "agent is responsible for the quality of that code."

```sh
roborev agent-hook install    # detects Claude Code and writes the Stop hook automatically
```

### Additional hooks worth adding

Two more Stop hooks round out coverage. These can be added to the existing `hooks.Stop` array in `~/.claude/settings.json`:

**1. Warn on claimed-but-unclosed kata issues**

Prevents the agent from ending a session while holding claimed issues without status:

```json
{
  "type": "command",
  "command": "bash -c 'kata list --owner \"$KATA_AUTHOR\" --status open --agent 2>/dev/null | grep -q . && echo \"[kata] You have open claimed issues. Close them or unassign before stopping.\"'"
}
```

**2. Require a passing branch review before merge-readiness**

A reminder hook (non-blocking) that fires if there are open roborev findings on the current branch:

```json
{
  "type": "command",
  "command": "bash -c 'roborev list --status open --branch HEAD 2>/dev/null | grep -q . && echo \"[roborev] Open review findings remain on this branch.\"'"
}
```

### What hooks cannot enforce

Hooks catch boundaries (session start/end, tool use) but cannot inspect agent reasoning mid-session. The behaviors that remain voluntary — because they require judgment — are covered by `AGENTS.md` instead:

- Searching before creating a kata issue (judgment: is this truly new work?)
- Choosing the right close form (`--done` vs `--duplicate-of` vs `--wontfix`)
- Deciding when a finding warrants a design conversation vs an automated fix
- Scoping issues to the right project

---

## How the tools fit together

```
Human intent
    │
    ▼
kata (issue ledger)
    │   human creates issues + hierarchy; agents claim, comment, close with evidence
    ▼
kwt (worktree isolation)
    │   one checkout per branch; parallel agents never share a directory
    ▼
[code changes + commits]
    │
    ▼
roborev (continuous review)
    │   post-commit hook triggers AI review in background
    │   roborev fix / refine feeds findings back to agents
    ▼
kata close (evidence-based)
    │   commits, test results, and review passage required as evidence
    ▼
engram plan land (memory synthesis)
    │   learnings extracted into .engram/memory/ and injected into CLAUDE.md
    │   future sessions load relevant patterns, tripwires, and architecture notes
    ▼
ghosthub (human visibility)
        human watches all sessions, worktrees, and remote machines in one place
```

---

## Further reading

- kata agent guide: `kata quickstart`
- roborev agent guide: `roborev quickstart` (in a repo)
- kwt docs: [kwt.sh/docs](https://kwt.sh/docs) (all pages available as `.md` at same path)
- engram docs: [github.com/askvinni/engram](https://github.com/askvinni/engram)
- Agent contracts for this environment: [AGENTS.md](./AGENTS.md)
