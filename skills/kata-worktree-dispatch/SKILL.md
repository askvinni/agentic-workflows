---
name: kata-worktree-dispatch
description: Claim one or more child kata issues, create an isolated kwt worktree per issue, and spawn an interactive Claude session in auto mode inside each tmux workspace. Use when the user asks to "dispatch kata issues", "spawn worktrees for kata issues", or "work on kata sub-issues in parallel".
---

# kata-worktree-dispatch

Claim child kata issues under a parent ref, create a kwt worktree per issue, and launch a Claude session in auto mode inside the tmux workspace so the user can monitor and interact via Ghosthub.

## Usage

```
/kata-worktree-dispatch <parent-ref> [--count N]
```

- `parent-ref`: kata issue ref whose children to dispatch (e.g. `zjat`)
- `--count N`: maximum number of unclaimed children to dispatch. Omit to let the user choose interactively.

## Instructions

Work through the steps below sequentially.

### 1. Inspect the parent issue

```bash
kata show <parent-ref> --agent
```

Parse the `Links:` section for `type=child` entries. Collect those refs in order.

### 2. Filter to unclaimed children

For each child ref, check whether it is already claimed:

```bash
kata show <ref> --agent
```

Skip any child that already has an owner. Collect only unowned children, preserving the original order.

If all children are already claimed, inform the user and stop.

### 3. Confirm with the user before dispatching

Present the unclaimed children as a checklist and ask the user which ones to dispatch. Use `AskUserQuestion` with `multiSelect: true`. Each option should show the ref and the issue title. Pre-select all by default (i.e., include all as options — the user unchecks what to skip).

Wait for the user's selection before proceeding. If `--count N` was given, apply it as an upper limit after the user's selection (take the first N checked items).

If the user selects nothing, inform them and stop.

### 4. For each confirmed child to dispatch

Repeat this block for each issue the user confirmed.

#### 4a. Claim the issue

```bash
kata claim <ref>
```

If the claim fails (already owned by another agent), skip this ref and move to the next.

#### 4b. Read the full issue body

If not already fetched in step 2, re-fetch:

```bash
kata show <ref> --agent
```

#### 4c. Derive the branch name

- Take the issue title, lowercase it, strip all characters except letters/digits/spaces/hyphens, replace spaces with `-`, and truncate to 40 characters.
- Prefix with the kata project name (derived from the parent issue's project, or from the repo name at `git rev-parse --show-toplevel` as fallback).
- Format: `<project>/<ref>-<slug>` — e.g. `engram/751h-kata-detection`

#### 4d. Create the worktree

Use `--no-launch` so `kwt add` creates the worktree without launching or attaching a tmux workspace:

```bash
kwt add -b <branch> --no-launch
```

#### 4e. Get the worktree path

```bash
kwt get <branch>
```

Store this as `WORKTREE_PATH`.

#### 4f. Start the tmux workspace without attaching

Use the **full worktree path** and `--start-session` to avoid attaching the current shell and to preserve project grouping in Ghosthub:

```bash
kwt open <WORKTREE_PATH> --start-session
```

#### 4g. Find the tmux session name

```bash
tmux ls 2>&1 | grep <ref>
```

Extract the session name (everything before the colon on the matching line). If multiple lines match, pick the one whose name also contains the branch slug.

#### 4h. Launch Claude in auto mode with inline issue context

Capture the issue body and build a prompt that instructs the agent to implement the work, open a pull request when done, and use `gh stack` if available. Pass it directly as the initial prompt — do not write any file to the worktree:

```bash
ISSUE=$(kata show <ref> --agent)

# Check whether gh-stack is available in the worktree
GH_STACK_NOTE=""
if kwt exec <branch> -- sh -c 'gh extension list 2>/dev/null | grep -q stack'; then
  GH_STACK_NOTE="gh stack is available. Once all PRs for this objective are ready, use \`gh stack submit\` to open them as a linked stack so the reviewer can merge them in order."
fi

PROMPT="Work on kata issue <ref>:

${ISSUE}

---
When the implementation is complete and tests pass, open a pull request for this branch targeting main. Use a clear title and include a summary of what was changed and why.
${GH_STACK_NOTE}"

tmux send-keys -t <session-name> "claude --permission-mode auto $(printf '%q' "$PROMPT")" Enter
```

`printf '%q'` shell-escapes the body so special characters do not break the command sent to the tmux pane.

### 5. Report

After all dispatches, print a summary:

- For each dispatched issue: ref, branch name, tmux session name
- Any skipped refs and why (user deselected, already owned, claim failed)

## Key rules

- Always confirm with the user via `AskUserQuestion` (multiSelect) before claiming or creating any worktree — never dispatch silently.
- Always pass `--no-launch` to `kwt add` — without it, `kwt add -b` automatically launches and attaches a tmux workspace, hijacking the current shell.
- Always use `--start-session` with the **full path** from `kwt get`, never the branch name pattern — using the path preserves project grouping in Ghosthub and prevents `kwt open` from attaching the current shell.
- Find the tmux session name from `tmux ls` after `kwt open`; do not guess or construct it — the session name includes an opaque hash suffix.
- Pass the kata issue body as the inline initial prompt via `printf '%q'`; do not write any file to the worktree — nothing from this dispatch should be committed.
- Always instruct the agent to open a PR when done. Include the `gh stack` note only when the extension is confirmed present.
- Always launch Claude with `--permission-mode auto` so the session runs unattended by default.
- Claim before creating the worktree — if the claim fails, skip all subsequent steps for that ref.
