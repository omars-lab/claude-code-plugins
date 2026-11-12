# loop-manager

Runs an issue through a loop of Claude Code agents to a pull request: critic, builder with a
"done?" hook that runs your own check, three reviewers, a person, and a lesson for next time.

Start with the `introduce` skill (`skills/introduce/SKILL.md`). The loop itself is
`skills/development-loop/SKILL.md`; the hook is `hooks/devloop_check.py`
(`python3 hooks/devloop_check.py --selftest` tests it).
