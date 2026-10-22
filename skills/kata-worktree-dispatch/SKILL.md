---
name: kata-worktree-dispatch
description: Dispatch engram plan and objective issues to isolated kwt worktrees with `engram dispatch`, each with a claimed kata mirror, a draft PR and a background Claude session in auto mode. Handles one plan, several plans, an objective's unblocked nodes, or an objective's dependency chains as stacked PRs. Use when the user asks to "dispatch plans", "dispatch #42", "dispatch an objective", "dispatch kata issues", "spawn worktrees for these plans", or "work on objective nodes in parallel".
---

# kata-worktree-dispatch

All the mechanics live in `engram dispatch`, run from the repository the issues belong
to. For each plan it claims the kata mirror (creating it if needed), creates a branch
with an empty wip commit, pushes it, opens a draft PR, attaches a kwt worktree, starts
the tmux workspace **detached**, and launches `claude --permission-mode auto` there with
the plan as the prompt. Your job is only to pick the arguments, confirm with the user,
run it, and relay the result.

It takes GitHub issue numbers of `engram-plan` and `engram-objective` issues. Plain kata
issues and other GitHub issues are refused. To dispatch one, make it an engram plan
first (`/engram-plan`).

## Usage

```
/kata-worktree-dispatch <issue> [<issue> ...] [--stack] [--no-launch]
```

| Invocation | What `engram dispatch` does |
|---|---|
| `engram dispatch 42` (a plan) | dispatches that plan, based on the default branch. Refused while its objective node waits on unfinished nodes |
| `engram dispatch 42 43` | dispatches each plan independently, all based on the default branch |
| `engram dispatch 41` (an objective) | dispatches its unblocked nodes, creating plan issues for nodes that have none; lists blocked nodes |
| `engram dispatch --stack 41` | every unfinished node of one objective, dependencies first, each branch based on its dependency's branch, chains linked with `gh stack link` |

Other flags: `--no-launch` sets everything up without starting Claude. Run
`engram dispatch --help` for the full list.

Run without a terminal (as you do), `engram dispatch` never prompts and fails without
`--yes`. So:

- Always pass issue numbers. To narrow an objective, pass the chosen nodes' plan issue
  numbers instead of the objective (from `engram objective view <N>`).
- Preview with `--dry-run`, then dispatch with `--yes`.

Branch names and PR titles come from the `[dispatch]` `branch` / `pr_title` templates in
`.engram/config.toml`. If `--dry-run` reports missing kata metadata (e.g. a Jira key), ask
the user for the value and set it with the `kata meta set` command it prints. Never
invent a value.

## Instructions

1. Check the tools if unsure: `engram doctor` prints `✓ dispatch available` or what is
   missing. Then preview the plan, which changes nothing:

   ```bash
   engram dispatch <issues> --dry-run
   ```

2. Show the user the planned plans with their branches, bases and PRs, any blocked or
   skipped nodes, and any errors. If an objective yields more than one candidate and the
   user may not want all of them, ask which ones with `AskUserQuestion`
   (`multiSelect: true`, one option per plan). Then pass those plan issue numbers instead
   of the objective. If the user selects nothing, stop.

3. Dispatch:

   ```bash
   engram dispatch <issues> --yes
   ```

4. Relay the result: for each plan, the kata ref, branch and base, draft PR URL, worktree,
   tmux session and whether Claude launched, plus any skipped nodes and why. If the exit
   code is non-zero, report the error lines verbatim. Re-running the same command is safe
   once the cause is fixed, because everything that already exists is reused.

## Rules

- Never dispatch without the user's confirmation of the plan.
- Never attach to or switch to a dispatched session (`kwt open` without
  `--start-session`, `kwt tmux attach`, `tmux attach`/`switch-client`). The user opens
  sessions from Ghosthub.
- Don't redo `engram dispatch`'s steps by hand (`kwt add`, `gh pr create`,
  `tmux send-keys`, …). If it fails, report the failure. If it's a bug in engram, report
  it, or fix it in the engram repo (https://github.com/askvinni/engram).
