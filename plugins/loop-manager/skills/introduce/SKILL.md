---
name: introduce
description: Introduces the loop-manager plugin and routes the person to the right skill. Use when someone asks what loop-manager does, how to run an issue through agents to a pull request, how the "done?" hook decides a builder is finished, how this differs from /goal or /loop, or how to set a repo up for the development loop.
---

# Introduce Loop Manager

You are the `loop-manager` plugin. Explain what you do, then point the person at the skill.

## What this plugin does

It runs a **development loop**: one issue goes in, a pull request a person reviews comes out.
Each step is a separate agent that sees only what it needs:

1. A **critic** turns the issue into `goal.md`: what done looks like, extra files the builder may
   not touch, how many rounds it gets, and the shortcuts a builder could take to fake it.
2. A **builder** works in the loop's own working copy and commits.
3. A **"done?" hook** (`SubagentStop`) runs the repo's check every time the builder stops. Not
   met: it sends the builder back with the failing output. Met, out of rounds, or the builder
   says `IMPOSSIBLE:`: it lets it stop. These are `/goal`'s three answers, decided by a command.
4. Three **reviewers** (security, spec, simplicity) read the commits in parallel. Their findings
   go back to the builder **once**.
5. A **person** reviews the pull request. Nothing merges by itself.
6. An **optimizer** proposes one piece of guidance, and where it should live. A tip
   (`.devloop/lessons.md`) is the weakest: it can be read and ignored. Above it are the critic's
   goal rules, a tenet in the repo's `CLAUDE.md`, a step in a skill, and, strongest, the check
   itself. It picks the lowest rung that would have prevented this run's miss. A person approves
   each: a tip on the spot, the others as a commit in the pull request, and the check by changing
   it themselves.

The check is never an agent's to write. A person commits `devloop.json` (the command, and the
files the builder may not change), and the hook enforces it.

## Skills

| Skill | Use it for |
|---|---|
| `development-loop` | Running one issue (`/loop-manager:development-loop <issue>`), or the queue under `/loop` (`/loop /loop-manager:development-loop`) |

To try it with nothing at stake, the skill ships a sample repo (`skills/development-loop/sample/`).
