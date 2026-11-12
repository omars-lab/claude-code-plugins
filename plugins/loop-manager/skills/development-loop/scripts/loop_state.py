#!/usr/bin/env python3
"""Keeps the state of development-loop runs, so a run can stop and pick up where it left off.

Each run lives in `<repo>/.devloop/<run id>/`:

    state.json   repo, worktree, branch, base commit, phase, the builder's agent id
    issue.md     what came in
    goal.md      the critic's goal (written by the critic agent)
    log          one line per event: UTC time, pid, ev=<event> key=value
    check.txt    the last failing check output (written by the hook)
    findings-*.md, guidance-proposed.md

The phases, in order: goal, build, review, fix, human, lessons, done (or stopped).

Commands (all print key=value lines a skill can read):

    loop_state.py next   --repo R              the run to resume, else the next queue line, else ev=queue_empty
    loop_state.py new    --repo R --issue TEXT start a run: folder, worktree on a new branch, state
    loop_state.py set    RUN key=value ...     change state fields (phase=review builder_id=abc)
    loop_state.py log    RUN <event> key=value append one event line
    loop_state.py show   RUN                   print the state
    loop_state.py finish RUN --phase done|stopped [--why TEXT]  close the run, free the worktree
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

PHASES = ["goal", "build", "review", "fix", "human", "lessons", "done", "stopped"]
OPEN = PHASES[:6]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def git(cwd: str, *args: str, check: bool = True) -> str:
    p = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)
    if check and p.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout.strip()


def log(run: str, ev: str, **kv) -> None:
    parts = [now(), f"pid={os.getpid()}", f"ev={ev}"]
    for k, v in kv.items():
        v = str(v)
        parts.append(f'{k}="{v}"' if (" " in v or not v) else f"{k}={v}")
    with open(os.path.join(run, "log"), "a") as f:
        f.write(" ".join(parts) + "\n")


def load(run: str) -> dict:
    with open(os.path.join(run, "state.json")) as f:
        return json.load(f)


def save(run: str, state: dict) -> None:
    tmp = os.path.join(run, "state.json.tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, os.path.join(run, "state.json"))


def runs_dir(repo: str) -> str:
    return os.path.join(repo, ".devloop")


def open_runs(repo: str) -> list[str]:
    d = runs_dir(repo)
    if not os.path.isdir(d):
        return []
    out = []
    for name in sorted(os.listdir(d)):
        p = os.path.join(d, name)
        if os.path.exists(os.path.join(p, "state.json")) and load(p).get("phase") in OPEN:
            out.append(p)
    return out


def emit(**kv) -> None:
    for k, v in kv.items():
        print(f"{k}={v}")


def cmd_next(repo: str) -> int:
    runs = open_runs(repo)
    if runs:
        s = load(runs[0])
        emit(ev="resume", run=runs[0], phase=s["phase"], worktree=s["worktree"], builder_id=s.get("builder_id", ""))
        return 0
    queue = os.path.join(runs_dir(repo), "queue.md")
    if os.path.exists(queue):
        for line in open(queue).read().splitlines():
            m = re.match(r"^\s*-\s*\[ \]\s*(.+)$", line)
            if m:
                emit(ev="queued", issue=m.group(1).strip())
                return 0
    emit(ev="queue_empty")
    return 0


def worktree_path(repo: str, cfg: dict) -> str:
    """One working copy per repo, reused run after run: `<repo>-devloop` beside the repo."""
    return os.path.abspath(cfg.get("worktree") or (repo.rstrip("/") + "-devloop"))


def cmd_new(repo: str, issue: str) -> int:
    repo = os.path.abspath(repo)
    cfg_path = os.path.join(repo, "devloop.json")
    if not os.path.exists(cfg_path):
        sys.exit(f"no devloop.json in {repo}: a person writes it first (see the skill's step 0)")
    if open_runs(repo):
        sys.exit("a run is still open; resume it (loop_state.py next) or finish it first")
    cfg = json.load(open(cfg_path))
    base = git(repo, "rev-parse", cfg.get("base", "HEAD"))
    run_id = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    run = os.path.join(runs_dir(repo), run_id)
    os.makedirs(run)
    branch = f"devloop/{run_id}"
    wt = worktree_path(repo, cfg)
    if os.path.isdir(wt):
        if git(wt, "status", "--porcelain"):
            sys.exit(f"the loop's working copy {wt} has uncommitted changes; clean it first")
        git(wt, "switch", "-q", "-c", branch, base)
    else:
        git(repo, "worktree", "add", "-q", "-b", branch, wt, base)
    with open(os.path.join(run, "issue.md"), "w") as f:
        f.write(issue.strip() + "\n")
    save(run, {"run": run_id, "repo": repo, "worktree": wt, "branch": branch, "base": base,
               "phase": "goal", "started": now()})
    log(run, "run_started", branch=branch, base=base[:12])
    lessons = os.path.join(runs_dir(repo), "lessons.md")
    if not os.path.exists(lessons):
        open(lessons, "w").write("# Lessons from earlier runs\n\nEach run's critic and builder read this first.\n")
    emit(ev="run_started", run=run, worktree=wt, branch=branch, base=base)
    return 0


def cmd_set(run: str, pairs: list[str]) -> int:
    s = load(run)
    for p in pairs:
        k, _, v = p.partition("=")
        if k == "phase" and v not in PHASES:
            sys.exit(f"unknown phase {v}; one of {', '.join(PHASES)}")
        s[k] = v
    save(run, s)
    if any(p.startswith("phase=") for p in pairs):
        log(run, "phase", to=s["phase"])
    emit(**{k: s[k] for k in (p.partition("=")[0] for p in pairs)})
    return 0


def cmd_finish(run: str, phase: str, why: str) -> int:
    s = load(run)
    s["phase"], s["finished"] = phase, now()
    save(run, s)
    log(run, "run_finished", phase=phase, why=why)
    # Free the shared working copy for the next run: back to a detached base, branch kept.
    if not git(s["worktree"], "status", "--porcelain", check=False):
        git(s["worktree"], "switch", "-q", "--detach", s["base"], check=False)
    queue = os.path.join(runs_dir(s["repo"]), "queue.md")
    issue = open(os.path.join(run, "issue.md")).read().strip()
    if os.path.exists(queue):
        text = open(queue).read()
        line = f"- [ ] {issue.splitlines()[0]}"
        if line in text:
            mark = "x" if phase == "done" else "-"
            open(queue, "w").write(text.replace(line, f"- [{mark}] {issue.splitlines()[0]} (run {s['run']})", 1))
    emit(ev="run_finished", phase=phase, branch=s["branch"])
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, rest = argv[1], argv[2:]

    def opt(name: str, default: str = "") -> str:
        return rest[rest.index(name) + 1] if name in rest else default

    if cmd == "next":
        return cmd_next(os.path.abspath(opt("--repo", ".")))
    if cmd == "new":
        return cmd_new(opt("--repo", "."), opt("--issue"))
    if cmd == "set":
        return cmd_set(os.path.abspath(rest[0]), rest[1:])
    if cmd == "log":
        log(os.path.abspath(rest[0]), rest[1], **dict(p.partition("=")[::2] for p in rest[2:]))
        return 0
    if cmd == "show":
        print(json.dumps(load(os.path.abspath(rest[0])), indent=1))
        return 0
    if cmd == "finish":
        return cmd_finish(os.path.abspath(rest[0]), opt("--phase", "done"), opt("--why", ""))
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
