---
name: development-loop
description: Runs one issue through a development loop of agents, from issue to a pull request a person reviews. A critic writes a checkable goal, a builder works until a hook running the repo's own check (devloop.json) says done, three reviewers (security, spec, simplicity) read the commit once and their findings go back to the builder, a pull request is opened but never merged, and an optimizer proposes one piece of guidance for the next run, at the lowest rung that would have prevented the miss (a tip, the critic's goal rules, a CLAUDE.md tenet, a skill step, or the check itself). Use for "/development-loop <issue>", "run the loop on this issue", "work the queue", or as the prompt of /loop to work .devloop/queue.md one item per pass. Do NOT use for a one-session task with no check to run (plain /goal is enough), or in a repo with no person-written devloop.json.
---

# Development loop

One issue in, one pull request out, with every step done by an agent that sees only what it
needs, and "done" decided by running a command, not by anyone's opinion.

```
issue -> critic -> goal.md -> builder <-> "done?" hook (runs the check) -> 3 reviewers
      -> findings back to the builder, once -> pull request (a person merges)
      -> optimizer -> guidance: tip | goal rule | tenet | skill step | check
```

How it relates to the two built-in commands it borrows from:

- **`/goal`** keeps the main session working until a small model judges a condition met. This
  skill keeps the same three answers (met, not yet, impossible) and the turn cap, but the answer
  comes from running the repo's check in the builder's working copy, on the builder agent's
  stop, by a `SubagentStop` hook. The check is a command a person wrote; no agent can soften it.
- **`/loop`** with no interval reruns a prompt and paces itself. `/loop /loop-manager:development-loop`
  works `.devloop/queue.md`, one issue a pass, and stops when the queue is empty.

## Before the first run (a person does this once per repo)

1. **Write `devloop.json`** at the repo root and commit it:
   ```json
   {
     "check": "make verify",
     "protect": ["test/", "Makefile"],
     "max_rounds": 6,
     "check_timeout": 300,
     "pr": true
   }
   ```
   `check` is the command that says done. `protect` lists what the builder may not change: the
   tests, and **whatever defines the check** (the Makefile, `package.json`'s scripts), or the
   builder could pass by editing the check. `devloop.json` itself is always protected.
   `pr: false` prints the branch instead of opening a pull request.
2. **Ignore the run folders**: add `.devloop/` to `.gitignore`. Runs, the queue and the lessons
   stay on this machine.
3. The loop works in **one working copy beside the repo**, `<repo>-devloop`, made on the first
   run and reused after (a `"worktree"` path in devloop.json overrides it). Each run gets its own
   branch, `devloop/<run id>`, from the repo's current `HEAD`.

If `devloop.json` is missing or not committed, stop and say so. Never write it for the person: the
check is theirs.

**What the hook guards, and what it doesn't.** It reads `devloop.json` from the run's starting
commit, so editing the file on disk changes nothing. It compares the protected files in the
working copy with that commit, renames included. It does not guard the run folder: `state.json`,
`log` and `goal.md` sit on disk, and a builder with a shell could edit them. The builder is told
not to, the spec reviewer reads the code rather than the log, and a person reads the pull
request; that is the line of defence for the run folder, not the hook.

## Every agent gets the run line

Every agent prompt below starts with these lines, filled in with absolute paths:

```
devloop-run: <run folder>
Working copy: <worktree>
Base commit: <base>
```

The hook finds the run from the first line, and `loop_report.py` finds each agent's token use
from it. Never leave it out.

## Steps

`S` below is `python3 ${CLAUDE_PLUGIN_ROOT}/skills/development-loop/scripts/loop_state.py`,
`C` is `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/devloop_check.py`. Run each as one command from the repo root.

**1. Find the work.** `S next --repo .`

- `ev=resume`: a run is open. Go to the step for its `phase` and carry on from there. A wakeup
  under `/loop` always finishes the open run before it takes a new issue.
- `ev=queued`: start it with step 2, using that line as the issue.
- `ev=queue_empty`: if an issue was given as the argument, start it. Otherwise say the queue is
  empty, and under `/loop` call `ScheduleWakeup` with `stop: true`.

**Waiting for an agent.** The Agent tool may run an agent in the background. Every "start" below
means: start it, keep the agent id its launch result gives, and wait for its completion notice
before the next step. Never run `C verify` or read an agent's file before that notice.

**2. Goal (phase `goal`).** For a new issue, `S new --repo . --issue "<issue text>"` prints the run
folder, the working copy and the base. (Resuming a run already in `goal`: skip `S new`; take the
paths from `S show <run>`.) Start the `loop-manager:critic` agent with the run lines and "Write
goal.md for this run." When it finishes, read `goal.md`:

- `STATUS: blocked`: `S finish <run> --phase stopped --why "<the Why line>"`, tell the person why,
  and stop. A blocked goal is a result, not a failure.
- `STATUS: ready`: `S log <run> goal_written rounds=<n>`, `S set <run> phase=build`.

**3. Build (phase `build`).** Start `loop-manager:builder` with the run lines and "Meet the goal
in goal.md." Save its agent id at once: `S set <run> builder_id=<id>`. The hook checks it every
time it stops. When it finishes, decide with the command, never with the agent's own words:

`C verify <run>`

- `verdict=met`: `S set <run> phase=review`.
- Not met, and the log's last check says `verdict=impossible` or `verdict=cap`:
  `S finish <run> --phase stopped --why "<verdict and reason>"`, report, and stop. The branch is
  kept for a person to look at.
- Not met otherwise (the hook could not run, or the agent stopped early): send the builder
  `C verify`'s output with `SendMessage` to its id, once, then verify again. Still not met: stop
  as above with `--why unverified`.

Resuming in `build` with a `builder_id`: verify first; if not met, `SendMessage` the builder
"The session restarted. Carry on toward goal.md." and continue as above.

**4. Review (phase `review`).** Start the three reviewers **in one message, in parallel**:
`loop-manager:review-security`, `loop-manager:review-spec`, `loop-manager:review-simplicity`,
each with the run lines and "Review this run's commits." The spec reviewer must not be told
anything the builder said. Each reviewer returns its findings as its reply; it does not save a
file (Claude Code refuses a helper agent that writes a report file, so the second sample run's
reviewers were all blocked). When all three return, write each reply's findings block, as given,
to `<run>/findings-<kind>.md` with the Write tool, then `S log <run> review kind=<kind> findings=<n>`
(n = the number of `- **` lines in it). Then `S set <run> phase=fix`.

**5. Findings back, once (phase `fix`).** If every file says `- none`, skip to step 6. Otherwise
`SendMessage` the builder all three files' findings in one message: "Reviewers found these. Fix
each one you agree with; say why for any you don't. Commit, then stop." Then `S log <run> findings_sent n=<total>`
and `C verify <run>`. There is no second review round. Not met after the fix: say so in the pull
request; do not hide it.

**6. A person reviews (phase `human`).** `S set <run> phase=human`. With `pr: true` and a remote:
push the run branch and open a pull request whose body has the goal, the last `C verify` line,
and the three findings files with what the builder did about each. Add a **"Not checked by the
check"** list: every example input a finding named (a title, a flag, a value), with what the fix
should now give. The check runs only the person's tests, so nobody in the loop ran these after the
fix; the person tries them, or adds them to the check. (Sample runs 2 and 5 both ended with fixed
edge cases no one had run.) `S log <run> pr_opened url=<url>`.
With `pr: false`, print the branch and the same summary. **Never merge, approve or enable
auto-merge.** That is the person's step.

**7. Guidance (phase `lessons`).** `S set <run> phase=lessons`. Start `loop-manager:optimizer`
with the run lines. It writes `guidance-proposed.md` with a **rung**: where the guidance should
live, from weakest to strongest. A tip can be read and ignored; a check can't. The optimizer
picks the lowest rung that would have prevented this run's miss.

| Rung | Lands in | How it lands, on a person's yes |
|---|---|---|
| `tip` | `.devloop/lessons.md` (local, not committed) | Append it |
| `goal` | the critic agent's file | A commit on the run's branch, pushed to its pull request |
| `tenet` | the repo's `CLAUDE.md` | A commit on the run's branch, pushed to its pull request |
| `skill` | a step in a skill or agent file | A commit on the run's branch, pushed to its pull request |
| `check` | `devloop.json` | **Never written by the loop.** Added to the pull request's description as a proposal; the person changes the check themselves |

So everything above a tip is approved the same way the code is: a person merges the pull
request, or drops that commit. `S log <run> guidance_proposed rung=<rung>` (or `rung=none`). Then:

- **Someone is at the keyboard**: show the guidance, its rung and its "Why not lower" line, and
  ask with AskUserQuestion: land it as proposed / move it a rung down (a tip instead) / drop it,
  each with what it changes for the next run. Land it only on a yes.
- **Under `/loop`** (nobody to ask): append it, with its rung, to `.devloop/guidance-pending.md`,
  and for a rung above `tip` add it to the pull request's description as "proposed guidance".
  The next attended run asks about pending guidance first.

`S finish <run> --phase done`.

**8. Report.** `python3 ${CLAUDE_PLUGIN_ROOT}/skills/development-loop/scripts/loop_report.py <run>`
prints the run's numbers. Show them, with the pull request link. Under `/loop`, call
`ScheduleWakeup` with the same prompt and a short delay (60 to 120 seconds) when the queue has
more, or `stop: true` when it is empty.

## Task management

One task per step, so a run that stops halfway shows where:

```javascript
TaskCreate({ subject: "Goal: critic writes goal.md", activeForm: "Writing the goal" })
TaskCreate({ subject: "Build until the check passes", activeForm: "Building" })
TaskCreate({ subject: "Three reviewers read the commits", activeForm: "Reviewing" })
TaskCreate({ subject: "Findings back to the builder, once", activeForm: "Fixing findings" })
TaskCreate({ subject: "Open the pull request for a person", activeForm: "Opening the pull request" })
TaskCreate({ subject: "Propose one piece of guidance and its rung, then report", activeForm: "Writing the guidance" })
```

## The queue

`.devloop/queue.md`, one issue per line: `- [ ] <the issue, in a sentence or a link>`. A finished
run marks its line `[x]` (done) or `[-]` (stopped), with the run id. Add lines by hand.

## When not to use it

- One session, no check to run, no reviewers needed: `/goal <condition>` is enough.
- The check can't see the issue (a visual change, a wording change): write a check that can, or
  do it by hand. A loop with a check that always passes is a loop that ships whatever it wrote.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/loop_state.py` | Starts a run (folder, working copy on a new branch, state), changes its phase, logs events, finishes it and frees the working copy, and finds the run to resume or the next queue item | Every step above | `python3 ${CLAUDE_PLUGIN_ROOT}/skills/development-loop/scripts/loop_state.py next\|new\|set\|log\|show\|finish …` |
| `scripts/loop_report.py` | Turns runs into numbers: minutes, "not yet" counts and reasons, findings per reviewer, the pull request, tokens per agent and model | Step 8, and to compare several runs | `python3 ${CLAUDE_PLUGIN_ROOT}/skills/development-loop/scripts/loop_report.py <run> [<run> …] [--json]` |
| `../../hooks/devloop_check.py` | The "done?" check: as a `SubagentStop` hook it runs on the builder's stop and blocks with the failing output; `verify <run>` runs the same check once; `--selftest` tests it | Step 3 and 5 (`verify`); after changing it (`--selftest`) | `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/devloop_check.py verify <run>` |

## Try it on the sample

`sample/` beside this file is a tiny repo with an issue, locked tests and a `devloop.json`. Copy it
somewhere, `git init` and commit it, then run `/development-loop` there with the issue in
`sample/ISSUE.md`. See `sample/README.md`.
