---
name: introduce
description: Introduces the session-manager plugin and routes the person to the right skill. Use when someone asks what this plugin does, how one Claude Code session can run several others, how to get one status summary across many sessions, or how to send every session's approval requests to one place.
---

# Introduce Session Manager

You are the `session-manager` plugin. When this skill is invoked, explain what you do, then route
the person to the right skill.

## What This Plugin Does

When several Claude Code sessions work on one goal (an incident, a launch, a release), the person
ends up switching tabs to learn what each is doing, answering the same kind of approval in every
tab, and finding out late that two sessions fixed the same thing. This plugin makes one session
the manager of the others:

- finds the sessions on the goal and confirms the list with the person;
- collects each one's task list and sets priorities across all of them;
- keeps two sessions off the same task, and suggests new sessions and handoffs;
- takes every approval request, asks the person once, and passes the answers back;
- checks in on a timer (every 10 minutes by default) and gives one short summary: what moved,
  what's stuck, what needs a decision.

It uses Claude Code's ListAgents and SendMessage tools, which reach the other sessions on the same
machine.

## Skills

| Skill | What it does |
|---|---|
| `introduce` | This skill. |
| `manage-sessions` | Run this session as the manager of the others on one goal. |

## How to Introduce Yourself

1. Explain the plugin in the few lines above.
2. Use AskUserQuestion:
   - **Manage the sessions on a goal now** → `/session-manager:manage-sessions`
   - **Just get a status from every session once** → `/session-manager:manage-sessions`, steps 1, 2
     and one check-in, without the timer
   - **Tell me more first** → walk through the steps in `manage-sessions`

## Requirements

- Claude Code with the ListAgents and SendMessage tools (cross-session messaging).
- The other sessions running on the same machine.
