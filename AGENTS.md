# Agentic Workflow Contracts

This file defines operating contracts for agents working in this environment.
Four kenn.io tools and engram are active: **kata** (issue ledger), **roborev** (code review),
**kwt** (git worktree manager), **engram** (memory management), and **ghosthub** (terminal multiplexer — human-only).

---

## kata — Issue Ledger

`kata` is the shared issue ledger for this machine. All task coordination between
agents and human goes through it. It is local-first (SQLite, ~4 ms per query)
with optional federation.

**Always run `kata quickstart` at session start to get the authoritative contract.**

### Core rules

- Use `--agent` on all reads and routine mutations (compact output, stable format).
- Use `--json` only when piping to `jq` or another structured consumer.
- Issue refs are short alphanumeric IDs (e.g. `abc4`). Numeric refs (`#12`) no longer work.
- **Search before creating.** Duplicate issues are noise.

```sh
kata search "login race" --agent
kata search --project foo "login race" --agent
```

- Create with an idempotency key so retries are safe:

```sh
kata create "fix login race" \
  --body "Observed double-submit in Safari callback." \
  --idempotency-key "login-race-2026-05-02" \
  --agent
```

- Claim before working; release when done or blocked:

```sh
kata next --unowned --agent          # pick highest-priority unclaimed issue
kata claim abc4                      # atomic claim; fails if already owned
kata unassign abc4                   # release if blocked
```

- Close only when work is verified. Include substantive prose and evidence:

```sh
kata close abc4 --done \
  --message "Fixed Safari callback double-submit; verified tests pass." \
  --commit <sha>
```

  Other close forms: `--duplicate-of`, `--superseded-by`, `--wontfix`, `--audit-no-change`.
  The daemon refuses closing a parent while children are still open.
  Do NOT close in a batch at the end; close each issue as soon as its work is verified.

- If work is incomplete, do NOT close. Label and comment instead:

```sh
kata label add abc4 needs-review
kata comment abc4 --body "What was attempted and what remains."
```

### Relationships (set on create or edit)

| Flag | Meaning |
|---|---|
| `--parent ref` | This issue is a sub-task of the target |
| `--blocks ref` | This must resolve before the target can proceed |
| `--blocked-by ref` | The target must resolve before this can proceed |
| `--related ref` | Useful context, no ordering |

### MCP integration

`kata mcp` exposes kata tools via Model Context Protocol. When the MCP server
is configured for this session, prefer native MCP calls over subprocess invocations
for lower overhead.

### Do not

- Create practice, tutorial, example, or scratchpad issues.
- Run `kata delete` or `kata purge` unless the user explicitly requests it with the exact ref.
- Work across projects unless explicitly scoped (`--project`).

---

## roborev — Continuous Code Review

`roborev` reviews every commit automatically via a post-commit git hook and surfaces
findings before they compound. The daemon is running; check `roborev status` to confirm.

**Run `roborev quickstart` in a repo for the repo-specific agent contract.**

### Setup (per repo)

```sh
roborev init              # installs post-commit hook + config
roborev agent-hook install  # installs optional hooks for this agent harness
roborev skills install    # installs Claude Code skills for /roborev-fix etc.
```

### Reading reviews

```sh
roborev show              # show review for HEAD
roborev show abc123       # review for a specific commit
roborev list              # list all review jobs on the current branch
roborev status            # daemon health and queue state
```

### Triggering reviews manually

```sh
roborev review                          # review HEAD
roborev review --dirty                  # review uncommitted changes
roborev review --dirty --wait           # review dirty tree and wait for result
roborev review --branch                 # review all commits on current branch vs main
roborev review --type security          # security-focused review
roborev review --type design            # design-focused review
roborev review --branch --type security # branch security review
```

### Fixing findings

`roborev fix` is a single-pass fix (applies changes, commits, no re-review).
`roborev refine` is the automated loop (review → fix → commit → re-review → repeat).

```sh
roborev fix                     # fix all open findings on current branch
roborev fix 123                 # fix a single job
roborev fix --batch-size 5      # pack up to 5 reviews per agent call
roborev refine                  # iterative loop until all reviews pass
roborev refine --max-iterations 5
roborev refine --min-severity high   # only address high/critical findings
```

`roborev refine` requires a clean working tree and a feature branch. It runs the
agent in an isolated worktree so your working tree is untouched.

### Agent-hook behavior

When the agent hook is installed, roborev may surface reminders or prompts at session
boundaries. Respond to these normally; use `roborev snooze` to suppress reminders
temporarily if they are interrupting focused work.

### Do not

- Run `roborev refine` on the default branch without `--since` to bound the range.
- Use `--allow-unsafe-agents` unless you have verified the agent environment is safe.

---

## kwt — Git Worktree Manager

`kwt` creates one isolated checkout per branch, each with its own tmux workspace.
It prevents parallel work from sharing directories and provides generation-tracked
change inspection.

### Core workflow

```sh
# Register a repo (run once inside it; no init file required)
kwt                          # opens dashboard; registration is automatic

# Create a worktree for a new branch
kwt add -b feature/my-branch

# New worktrees start INERT — review changes before opening
kwt changes feature/my-branch   # inspect what changed
kwt open feature/my-branch      # launch the tmux workspace

# Execute commands inside a worktree without switching to it
kwt exec feature/my-branch -- go test ./...

# Get the filesystem path (useful for scripts)
kwt get feature/my-branch       # prints path; --json for structured output

# Inspect all worktrees across registered projects
kwt status
kwt status --json

# Remove a worktree (blocked if uncommitted changes unless --force)
kwt remove feature/my-branch

# Maintenance
kwt doctor                    # diagnose worktree issues (Git 2.31+)
kwt prune                     # remove stale/merged worktrees
```

### Pull-request workflow

```sh
kwt pr import <pr-url>        # creates a protected worktree for the PR
kwt pr attach <ref>            # explicitly open a PR worktree after review
```

PR worktrees are "protected" — they require explicit `kwt pr attach` rather than
`kwt open`, preserving the contributor's push destination.

### Agent conventions

- Always check `kwt changes <worktree>` before `kwt open` when the branch existed
  before the worktree was created (inert safety pattern).
- Prefer `kwt exec` over `cd` + command to keep work scoped to the worktree.
- Use `--json` output when consuming kwt data programmatically.
- Do not `kwt remove --force` without confirming the user wants uncommitted work discarded.

---

## engram — Memory Management

`engram` captures institutional knowledge from completed work and makes it available
to future agent sessions automatically. Memory files live in `.engram/memory/` inside
the repo and are injected into `CLAUDE.md` with routing conditions so agents load
only the files relevant to what they're working on.

### Core workflow

1. Before starting substantial work, create a plan issue: `engram plan new <title>`
2. Work on the branch, open a PR with `closes #N` in the body
3. After the PR merges, run `engram plan land <N>` to synthesize learnings

```sh
engram plan new "Fix session token storage"    # create a plan issue on GitHub
engram plan land <issue-number>                # synthesize memory files, close issue
engram plan learn <issue-number>               # generate memory without closing
engram plan learn --all                        # process all closed plan issues
engram plan list                               # show open plans
engram plan status                             # show issue/PR for current branch
engram compact                                 # prune stale or low-quality memory files
engram doctor                                  # verify dependencies and config
```

### Memory categories

| Directory | What it contains |
|---|---|
| `patterns/` | Recurring solutions and idioms discovered during implementation |
| `tripwires/` | Bugs, gotchas, and approaches that failed — with reasons |
| `architecture/` | Structural decisions and their rationale |
| `testing/` | Test strategies, fixtures, and codebase constraints |

Each file includes a `read_when` condition. Agents must honor these conditions and
load only memory files relevant to the current task.

### Do not

- Skip `engram plan new` for substantial, multi-commit pieces of work — the plan
  is what gives `engram plan land` enough context to extract good learnings.
- Run `engram plan land` before the PR is merged — landing is a post-merge step.
- Manually edit files under `.engram/memory/` — use `engram compact` to prune.

---

## ghosthub — Terminal Multiplexer (Human-only)

Ghosthub is a native macOS terminal app at `/Applications/Ghosthub.app`. It
unifies tmux, Herdr, and Zellij sessions across local and remote machines and
bundles kwt for worktree management.

**Agents do not interact with Ghosthub directly.** It is a human-facing GUI.

- kwt workspaces created by an agent appear automatically in Ghosthub's session list.
- SSH sessions managed by Ghosthub may host remote kata daemons reachable via
  `KATA_SERVER=http://<host>:<port>`.
- Requires macOS 26 (Tahoe), Apple Silicon.

