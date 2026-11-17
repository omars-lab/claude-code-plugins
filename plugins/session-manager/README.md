# Session Manager

Make one Claude Code session the manager of the other sessions working on the same goal.

## Getting Started

```bash
# Add the marketplace once, then install
/plugin marketplace add omars-lab/claude-code-plugins
/plugin install session-manager@omars-lab

# Learn what this plugin can do
/session-manager:introduce
```

## Skills (2)

| Category | Skill | What it does |
|---|---|---|
| **Intro** | `introduce` | Explain plugin capabilities |
| **Manage** | `manage-sessions` | Find the sessions on a goal, set their priorities, route approvals, check in on a timer |

The skill is a single `SKILL.md` with no scripts, so it also works copied on its own into
`~/.claude/skills/manage-sessions/SKILL.md`.

## Requirements

- Claude Code with ListAgents and SendMessage (cross-session messaging)

---

**Part of**: [omars-lab Claude Code plugins](../../README.md)
