# Claude Code plugins

Claude Code plugins I have shared. Each one is checked for secrets and private details before it
goes up here.

Add this marketplace once, in Claude Code. It is listed as `omars-lab`, the name you install
from:

```
/plugin marketplace add omars-lab/claude-code-plugins
```

| Plugin | What it does | Install |
|---|---|---|
| [loop-manager](plugins/loop-manager/) | A development loop where a command you wrote, not an agent, decides when the work is done | `/plugin install loop-manager@omars-lab` |
| [session-manager](plugins/session-manager/) | One Claude Code session manages the others on a goal: priorities, approvals in one place, a status every ten minutes | `/plugin install session-manager@omars-lab` |

## loop-manager

```
issue -> critic -> goal.md -> builder <-> "done?" hook (runs your check) -> 3 reviewers
      -> findings back to the builder, once -> pull request (you merge)
      -> optimizer -> one piece of guidance for the next run
```

- A **critic** turns the issue into a goal: done when, the files to leave alone, and the
  shortcuts to watch for. It can refuse to start, for example when your check already passes.
- A **builder** works in its own copy of the repo. Each time it stops, a `SubagentStop` hook runs
  the check named in your `devloop.json`. It gets one of three answers: met, not yet (back to work,
  with what failed), or stuck (stop and keep the branch). The builder can't edit your tests or the
  check.
- **Three reviewers** (security, spec, simplicity) read the commits once. Their findings go back
  to the builder one time.
- **You** read the pull request. The loop never merges.
- An **optimizer** proposes one piece of guidance at the lowest rung that would have caught the
  miss: a tip, a goal rule, a CLAUDE.md tenet, a skill step, or the check itself. It lands only on
  your yes.

To use it:

1. In your repo, commit a `devloop.json`:
   ```json
   { "check": "make verify", "protect": ["test/", "Makefile"], "max_rounds": 6, "pr": true }
   ```
2. Add `.devloop/` to `.gitignore`.
3. Run `/loop-manager:development-loop <the issue>`, or put issues in `.devloop/queue.md` and run
   `/loop /loop-manager:development-loop` to work through them one at a time.

To try it first, the plugin ships a tiny sample repo with an issue, locked tests and a
`devloop.json`: see `plugins/loop-manager/skills/development-loop/sample/README.md`.

The full steps are in `plugins/loop-manager/skills/development-loop/SKILL.md`. The hook's own
tests: `python3 plugins/loop-manager/hooks/devloop_check.py --selftest`.

## session-manager

When several Claude Code sessions work on one goal (an incident, a launch, a release), you end up
switching tabs to learn what each is doing and answering the same kind of approval in every tab.
This plugin makes one session the manager of the others:

- It finds the sessions on the goal and asks each for its folder, branch and task list.
- It ranks the tasks by how much they move the goal, and tells each session what to do next.
- It keeps two sessions off the same task and out of the same folder.
- Every approval comes to the manager, which asks you once and writes your answer down before
  passing it on.
- Every ten minutes it asks each session for a status and gives you one short summary: what
  moved, what's stuck, what needs you.

To use it, run `/session-manager:manage-sessions` in the session you want as the manager. It needs
the ListAgents and SendMessage tools, which reach the other sessions on the same machine. The
steps are in `plugins/session-manager/skills/manage-sessions/SKILL.md`.

## License

MIT
