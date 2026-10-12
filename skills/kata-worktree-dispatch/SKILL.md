---
name: kata-worktree-dispatch
description: Claim one or more child kata issues, create an isolated kwt worktree per issue, and spawn an interactive Claude session in auto mode inside each tmux workspace. Use when the user asks to "dispatch kata issues", "spawn worktrees for kata issues", or "work on kata sub-issues in parallel".
---

# kata-worktree-dispatch

Claim child kata issues under a parent ref, create a kwt worktree per issue, and launch a Claude session in auto mode inside the tmux workspace so the user can monitor and interact via Ghosthub.

The dispatching workflow (not the spawned sessions) is responsible for making the
dispatched branches a real git stack — each branch based on the previous one — and
for opening a draft PR per branch before handoff. It builds that stack with the
`gh-stack` extension (`gh stack init`/`add`/`submit`), which creates each branch on
top of the last and links their PRs on GitHub in one step. Spawned sessions never
create PRs or manage stacking themselves; they only push commits to the branch
they're given and mark their existing draft PR ready for review when done. This is
deliberate: a spawned session (or a bare `gh stack submit` with no local chain
behind it) cannot retroactively stack branches that were never based on each other
in git — that's what caused unmergeable PRs in past dispatches. The fix is building
the chain with `gh stack` up front, before any branch diverges independently.

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

### 4. Prepare the stack checkout

The confirmed children are dispatched **one git branch on top of the previous one**,
in the same order they were listed under the parent (step 1/2). This order is what
determines the stack — objective children are numbered in dependency order (e.g.
`2.4`, `2.5`, `2.6`), so listing order is a reliable stacking order.

All branch building (step 5) happens in a single checkout — the primary worktree,
or any existing worktree that isn't one of the per-child worktrees created in step
8 — since `gh stack` tracks the current stack by what's checked out there. Building
the stack checks each new branch out in that checkout, and git refuses to attach a
second worktree to a branch that is checked out anywhere. So the per-child
worktrees are only created in step 8, **after** step 7 has switched this checkout
back to where it started.

In that checkout, confirm the working tree is clean (stop and tell the user if it
isn't — don't stash their work) and record where it is so step 7 can return to it:

```bash
git status --porcelain            # must print nothing
ORIG_REF=$(git symbolic-ref --short -q HEAD || git rev-parse HEAD)
```

Track a running `PREV_BRANCH` variable across iterations of step 5, starting empty
(meaning "base off the repo's default branch").

Check once whether `gh-stack` is installed — it's the preferred way to build the
chain. If it's not available, fall back to the plain-git method noted inline in
steps 5d and 6:

```bash
gh extension list 2>/dev/null | grep -q stack && echo "gh-stack available"
```

### 5. Build the branch stack, one child at a time

Repeat this block for each confirmed child, in stacking order. Never parallelize it
— each iteration depends on the branch created by the previous one.

#### 5a. Claim the issue

```bash
kata claim <ref>
```

If the claim fails (already owned by another agent), skip this ref entirely (do not
advance `PREV_BRANCH`) and move to the next.

#### 5b. Read the full issue body

If not already fetched in step 2, re-fetch:

```bash
kata show <ref> --agent
```

#### 5c. Derive the branch name

- Take the issue title, lowercase it, strip all characters except letters/digits/spaces/hyphens, replace spaces with `-`, and truncate to 40 characters.
- Format: `<ref>-<slug>` — e.g. `751h-kata-detection`

#### 5d. Add the branch to the stack, on top of the previous one

With `gh-stack` available, use it to build the chain — it bases each new branch on
whatever is currently at the top of the stack, so the ancestry is real:

```bash
if [ -z "$PREV_BRANCH" ]; then
  gh stack init <branch>       # first child: bases on the repo's default branch
else
  gh stack add <branch>        # every later child: bases on the current top of the stack
fi
git commit --allow-empty -m "wip: <ref> <issue-title>"
```

The empty commit exists only so the branch has something to diverge from its base
on and a PR can be opened before real work starts; it is harmless and gets carried
along under the spawned session's real commits.

Without `gh-stack`, base the new branch on the previous one by hand — `kwt add -b`
cannot target an arbitrary base branch, so create the branch with plain git:

```bash
if [ -z "$PREV_BRANCH" ]; then
  git fetch origin
  git branch <branch> origin/<default-branch>
else
  git branch <branch> "$PREV_BRANCH"   # local tip, including its wip commit
fi
git checkout <branch>
git commit --allow-empty -m "wip: <ref> <issue-title>"
```

Record the branch, its base (`PREV_BRANCH`, or the default branch for the first
child) and its ref, then set `PREV_BRANCH=<branch>` before moving to the next child.

### 6. Push the stack and open draft PRs

With `gh-stack`, one command pushes and opens/updates the whole stack as linked,
based PRs:

```bash
gh stack submit --auto
```

New PRs are created as drafts by default under `--auto`; existing PRs just get
their base branch updated. Pull the resulting PR URLs for the handoff prompts in 8d:

```bash
gh pr list --json number,url,headRefName --jq '.[] | "\(.headRefName) \(.url)"'
```

Without `gh-stack`, push and open each branch's draft PR in stacking order, from the
same checkout:

```bash
git push -u origin <branch>
PR_URL=$(gh pr create --draft --head <branch> --base "<BASE>" \
  --title "<issue-title>" \
  --body "Work in progress for kata issue <ref>. Stacked on \`<BASE>\`.")
```

Record each `PR_URL` alongside its branch and base.

### 7. Release the stack checkout

Switch the checkout back to where it started, so none of the stack branches is
checked out there any more:

```bash
git checkout "$ORIG_REF"
```

Skipping this makes step 8's `kwt add` fail for the top branch with "already checked
out".

### 8. Attach a worktree and launch a session per child

For each dispatched child (the branches recorded in step 5). These can run in any
order now that every branch and PR exists.

#### 8a. Attach a worktree to the branch

The branch already exists, so attach a worktree without `-b`:

```bash
kwt add <branch> --no-launch
WORKTREE_PATH=$(kwt get <branch>)
```

#### 8b. Start the tmux workspace without attaching

Use the **full worktree path**, `--start-session` (create the workspace detached)
and `--json` (report where it was created):

```bash
OPEN_JSON=$(kwt open "$WORKTREE_PATH" --start-session --json)
```

#### 8c. Read the tmux endpoint from kwt's output

kwt runs its workspaces on a **separate tmux server** (socket name `kwt`), not the
default one — so plain `tmux ls` / `tmux send-keys` / `tmux attach` never see them.
Take the session and socket straight from the JSON instead of searching for them:

```bash
SESSION=$(jq -r .session_name <<<"$OPEN_JSON")
SOCKET=$(jq -r .tmux_socket_name <<<"$OPEN_JSON")
```

If either is empty, stop and report the `kwt open` output to the user — do not fall
back to `kwt open <branch>`, `kwt tmux attach`, `tmux attach`/`switch-client`, or
`tmux new-session` without `-d`. Each of those attaches the current terminal to
the new workspace instead of leaving it in the background.

#### 8d. Launch Claude in auto mode with inline issue context

Capture the issue body and build a prompt that instructs the agent to implement the
work and mark the **already-open draft PR** ready for review — not to create a new
PR or touch the branch's base. Pass it directly as the initial prompt — do not write
any file to the worktree:

```bash
ISSUE=$(kata show <ref> --agent)

PROMPT="Work on kata issue <ref>:

${ISSUE}

---
A draft pull request has already been opened for this branch: ${PR_URL}
It is correctly stacked on \`${BASE}\` as part of a multi-PR dependency chain — do
not create a new PR, and do not change this branch's base or rebase it onto main.
When the implementation is complete and tests pass, push your commits to this
branch and run \`gh pr ready\` on the existing PR (adding a summary comment of what
changed and why) instead of opening a new one."

tmux -L "$SOCKET" send-keys -t "$SESSION" "claude --permission-mode auto $(printf '%q' "$PROMPT")" Enter
```

`printf '%q'` shell-escapes the body so special characters do not break the command sent to the tmux pane.

### 9. Report

After all dispatches, print a summary:

- For each dispatched issue: ref, branch name, base branch, draft PR URL, tmux session name
- The overall stack order, so the user can see the dependency chain at a glance
- Any skipped refs and why (user deselected, already owned, claim failed)

## Key rules

- Always confirm with the user via `AskUserQuestion` (multiSelect) before claiming or creating any worktree — never dispatch silently.
- The main workflow — never the spawned session — creates each branch, bases it on the previous branch in the stack, opens its draft PR, and records the base before handoff. A spawned session cannot fix a branch that was never based on the right commit; it can only make things it's given, correct.
- Prefer `gh stack init`/`add` to build the branch chain and `gh stack submit --auto` to open/link the draft PRs — that's what builds a real dependency chain (each branch based on the previous one) and keeps GitHub's stack view in sync, instead of assembling one after the fact. Fall back to plain git (base each branch on the previous one's local tip) plus `gh pr create --draft --base <prev-branch>` only when the `gh-stack` extension isn't installed.
- Whichever method is used, base every branch after the first on the previous branch, not on the default branch — a bare `gh stack submit`/`gh pr create` cannot retroactively fix branches that were already independently forked from main; the chain has to be real in git before either tool touches it.
- Process the branch-creation steps (5a-5d) for children strictly in stacking order, one at a time — never in parallel — since each depends on the previous branch's tip existing.
- Build the whole stack and open its PRs (steps 5-6) before creating any per-child worktree, then switch the stack checkout back to its original ref (step 7). A branch checked out in that checkout cannot also get a kwt worktree.
- Always pass `--no-launch` to `kwt add` — without it, `kwt add -b` automatically launches and attaches a tmux workspace, hijacking the current shell.
- Always use `kwt open <full path> --start-session --json`, never the branch name pattern — using the path preserves project grouping in Ghosthub, and `--start-session` is the only mode of `kwt open` that does not attach the current terminal.
- Take the session name and socket from that JSON (`session_name`, `tmux_socket_name`) and address the session with `tmux -L <socket>`. kwt sessions live on their own tmux server, so `tmux ls` on the default socket won't list them; don't guess or construct the name (it has an opaque hash suffix).
- Never attach to or switch to a dispatched session (`kwt open` without `--start-session`, `kwt tmux attach`, `tmux attach`, `tmux switch-client`, `tmux new-session` without `-d`). The user opens it from Ghosthub; if the endpoint can't be resolved, stop and report instead.
- Pass the kata issue body as the inline initial prompt via `printf '%q'`; do not write any file to the worktree — nothing from this dispatch should be committed.
- Never instruct a spawned session to open its own PR — one already exists in draft by the time the session is launched. Instruct it to push commits and mark that PR ready for review instead.
- Always launch Claude with `--permission-mode auto` so the session runs unattended by default.
- Claim before creating the branch — if the claim fails, skip all subsequent steps for that ref and do not advance `PREV_BRANCH`.
