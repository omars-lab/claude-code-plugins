# Claude Code plugins

Claude Code plugins I have shared. Each one is checked for secrets and private details before it
goes up here.

Add this marketplace once, in Claude Code:

```
/plugin marketplace add omars-lab/claude-code-plugins
```

| Plugin | What it does | Install |
|---|---|---|
| [loop-manager](plugins/loop-manager/) | A development loop where a command you wrote, not an agent, decides when the work is done | `/plugin install loop-manager@claude-code-plugins` |

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

## License

MIT
