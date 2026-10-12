---
name: kata-worktree-dispatch
description: Dispatch kata issues to isolated kwt worktrees, each with a draft PR and a background Claude session in auto mode. Handles a single issue, several independent issues, or a parent's children as a stacked chain of PRs. Use when the user asks to "dispatch kata issues", "dispatch <ref>", "spawn worktrees for kata issues", or "work on kata sub-issues in parallel".
---

# kata-worktree-dispatch

All the mechanics live in the `kdispatch` CLI (`bin/kdispatch` in the agentic-workflows
repo, linked onto PATH by its `setup.py`). For each issue it claims the issue, creates a
branch with an empty wip commit, pushes it, opens a draft PR, attaches a kwt worktree,
starts the tmux workspace **detached**, and launches `claude --permission-mode auto`
there with the issue as the prompt. Your job is only to pick the arguments, confirm
with the user, run it once, and relay the result.

## Usage

```
/kata-worktree-dispatch <ref> [<ref> ...] [--stack] [--only a,b] [--count N]
```

| Invocation | What `kdispatch` does |
|---|---|
| `kdispatch <ref>` (issue has no children) | dispatches that one issue, based on the default branch |
| `kdispatch <ref>` (issue has children) | dispatches its open, unowned children as a stack: each branch and PR based on the previous one, linked with `gh stack link` |
| `kdispatch a b c` | dispatches each issue independently, all based on the default branch |
| `kdispatch --stack a b c` | stacks them in the order given |

Other flags: `--only a,b` / `--count N` to narrow a parent's children, `--no-stack` to
dispatch children independently, `--no-launch` to set everything up without starting
Claude, `-C <repo>` to run against another repo.
Run without a terminal (as you do), `kdispatch` never prompts: always pass refs, narrow
with `--only`, and confirm with `--yes`.

Branch names and PR titles come from the repo's `kdispatch.branch` / `kdispatch.prTitle`
git config templates. If `--dry-run` reports missing issue metadata (e.g. a Jira key), ask
the user for the value and set it with the `kata meta set` command it prints. Don't invent it.

## Instructions

1. Run from the repository the issues belong to. Preview the plan, which changes nothing:

   ```bash
   kdispatch <args> --dry-run
   ```

2. Show the user the planned issues, branches and bases. If a parent has more than one
   child, ask which to dispatch with `AskUserQuestion` (`multiSelect: true`, one option
   per child, ref + title) and pass the selection as `--only`. If the user selects
   nothing, stop.

3. Dispatch:

   ```bash
   kdispatch <args> --yes
   ```

4. Relay the summary: per issue the branch, base, draft PR URL, tmux session and
   whether Claude launched; plus any skipped refs and why. If the exit code is
   non-zero, report the error lines verbatim. Re-running the same command is safe once
   the cause is fixed: everything that already exists is reused.

## Rules

- Never dispatch without the user's confirmation of the plan.
- Never attach to or switch to a dispatched session (`kwt open` without
  `--start-session`, `kwt tmux attach`, `tmux attach`/`switch-client`). The user opens
  sessions from Ghosthub.
- Don't redo `kdispatch`'s steps by hand (`kwt add`, `gh pr create`, `tmux send-keys`,
  …). If it fails, report the failure. If it's a bug in `kdispatch`, fix the script.
