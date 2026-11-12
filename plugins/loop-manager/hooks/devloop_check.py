#!/usr/bin/env python3
"""The "done?" check for the development loop.

Two ways in:

* As a SubagentStop hook (no arguments, JSON on stdin). When the agent stopping is
  `loop-manager:builder`, it finds the run named in the builder's first message
  (`devloop-run: <absolute run folder>`), runs the repo's check in the builder's working
  copy, and either lets the builder stop or sends it back with what failed.
* As a command: `devloop_check.py verify <run folder>` runs the same check once and prints
  the verdict. The skill runs this after the builder returns, so a hook that crashed or timed
  out can never pass a run by saying nothing.

The verdicts are the three `/goal` has (met, not yet, impossible), plus `cap` when the
builder ran out of rounds. Unlike `/goal`, the verdict comes from running a command, not
from a model reading the conversation.

What the check runs is never written by an agent: it is the `check` line of `devloop.json`,
a file a person commits at the repo root. The builder may not change that file, the paths it
lists under `protect`, or the extra paths the critic listed in `goal.md`.

Run `devloop_check.py --selftest` for the tests.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
import time

BUILDER = "loop-manager:builder"
RUN_LINE = re.compile(r"devloop-run:\s*(\S+)")
IMPOSSIBLE = re.compile(r"^\s*IMPOSSIBLE:\s*(.+)$", re.M)
TAIL = 40  # lines of failing output sent back to the builder


# ---------- small helpers ----------

def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log(run: str, ev: str, **kv) -> None:
    """One line per event: UTC time, pid, ev=<event>, key=value (no spaces in values)."""
    parts = [now(), f"pid={os.getpid()}", f"ev={ev}"]
    for k, v in kv.items():
        v = str(v)
        parts.append(f'{k}="{v}"' if (" " in v or not v) else f"{k}={v}")
    try:
        with open(os.path.join(run, "log"), "a") as f:
            f.write(" ".join(parts) + "\n")
    except OSError:
        pass


def git(cwd: str, *args: str) -> str:
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True).stdout


def read_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def config(state: dict) -> dict:
    """devloop.json as committed at the run's starting commit, never the copy on disk.

    The builder has a shell, so any file on disk could be edited; the base commit can't be."""
    text = git(state["repo"], "show", f"{state['base']}:devloop.json")
    if not text:
        raise RuntimeError("devloop.json is not committed at the run's base commit")
    return json.loads(text)


def protected_paths(cfg: dict, run: str) -> list[str]:
    """devloop.json itself, its `protect` list, and any extra paths in goal.md's Protected list."""
    pats = ["devloop.json", *cfg.get("protect", [])]
    goal = os.path.join(run, "goal.md")
    if os.path.exists(goal):
        section = re.search(r"^## Protected\s*\n(.*?)(?=^## |\Z)", open(goal).read(), re.M | re.S)
        if section:
            pats += re.findall(r"^\s*[-*]\s*`?([^`\s]+)`?", section.group(1), re.M)
    return pats


def matches(path: str, pats: list[str]) -> bool:
    for p in pats:
        if p.endswith("/") and path.startswith(p):
            return True
        if path == p or fnmatch.fnmatch(path, p):
            return True
    return False


def round_cap(run: str, cfg: dict) -> int:
    """The smaller of the person's `max_rounds` and the critic's `Rounds:` line."""
    cap = int(cfg.get("max_rounds", 6))
    goal = os.path.join(run, "goal.md")
    if os.path.exists(goal):
        m = re.search(r"^Rounds:\s*(\d+)", open(goal).read(), re.M)
        if m:
            cap = min(cap, int(m.group(1)))
    return cap


def rounds_used(run: str, phase: str) -> int:
    try:
        lines = open(os.path.join(run, "log")).read().splitlines()
    except OSError:
        return 0
    return sum(1 for l in lines if " ev=check " in l and " verdict=not_yet" in l and f" phase={phase}" in l)


# ---------- the check ----------

def evaluate(run: str) -> dict:
    """Run the check for one run folder. Returns {verdict, why, output}."""
    state = read_json(os.path.join(run, "state.json"))
    repo, wt, base = state["repo"], state["worktree"], state["base"]
    cfg = config(state)

    # 1. Protected files: compare the builder's copy with the run's starting commit.
    #    --no-renames, so a protected file moved away shows as deleted, not as a new name.
    changed = set(git(wt, "diff", "--no-renames", "--name-only", base).splitlines())
    changed |= set(git(wt, "ls-files", "--others", "--exclude-standard").splitlines())
    touched = sorted(p for p in changed if matches(p, protected_paths(cfg, run)))
    if touched:
        return {"verdict": "not_yet", "why": "protected_changed",
                "output": "You changed files you may not change: " + ", ".join(touched)
                + f". Put them back as they were at {base[:8]} (git checkout {base[:8]} -- <file>) and meet the goal without them."}

    # 2. The person's check, in the builder's copy.
    try:
        proc = subprocess.run(cfg["check"], shell=True, cwd=wt, capture_output=True, text=True,
                              timeout=int(cfg.get("check_timeout", 300)))
        out = (proc.stdout + proc.stderr).splitlines()
        if proc.returncode != 0:
            return {"verdict": "not_yet", "why": "check_failed",
                    "output": f"`{cfg['check']}` exited {proc.returncode}. Last lines:\n" + "\n".join(out[-TAIL:])}
    except subprocess.TimeoutExpired:
        return {"verdict": "not_yet", "why": "check_timeout",
                "output": f"`{cfg['check']}` ran longer than {cfg.get('check_timeout', 300)}s."}

    # 3. Committed, and nothing left over.
    if git(wt, "status", "--porcelain").strip():
        return {"verdict": "not_yet", "why": "uncommitted",
                "output": "The check passes, but there are uncommitted changes. Commit your work (or remove stray files)."}
    if not git(wt, "rev-list", f"{base}..HEAD").strip():
        return {"verdict": "not_yet", "why": "no_commit",
                "output": "The check passes, but you have not committed anything since the run started."}
    return {"verdict": "met", "why": "check_passed", "output": ""}


# ---------- hook entry ----------

def first_user_text(transcript: str) -> str:
    try:
        with open(transcript) as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("type") != "user":
                    continue
                content = rec.get("message", {}).get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    return " ".join(c.get("text", "") for c in content if isinstance(c, dict))
    except (OSError, ValueError):
        pass
    return ""


def hook(payload: dict) -> int:
    if payload.get("agent_type") != BUILDER:
        return 0
    m = RUN_LINE.search(first_user_text(payload.get("agent_transcript_path", "")))
    if not m or not os.path.exists(os.path.join(m.group(1), "state.json")):
        # Never trap an agent we can't place. The skill's own `verify` still decides the run.
        sys.stderr.write("devloop: builder stopped but no run folder was named; not checking\n")
        return 0
    run = m.group(1)
    state = read_json(os.path.join(run, "state.json"))
    phase = state.get("phase", "build")
    ids = dict(agent=payload.get("agent_id", ""), transcript=payload.get("agent_transcript_path", ""), phase=phase)

    said = IMPOSSIBLE.search(payload.get("last_assistant_message") or "")
    if said:
        log(run, "check", verdict="impossible", why=said.group(1).strip()[:120].replace("\n", " "), **ids)
        return 0

    try:
        result = evaluate(run)
    except Exception as e:  # fail closed for the run: no `met` line is written
        log(run, "check_error", error=type(e).__name__, **ids)
        sys.stderr.write(f"devloop: check could not run ({e}); the skill will verify\n")
        return 0

    if result["verdict"] == "met":
        log(run, "check", verdict="met", **ids)
        return 0

    cfg = config(state)
    used, cap = rounds_used(run, phase), round_cap(run, cfg)
    if used >= cap:
        log(run, "check", verdict="cap", why=result["why"], rounds=used, **ids)
        return 0
    log(run, "check", verdict="not_yet", why=result["why"], round=used + 1, cap=cap, **ids)
    with open(os.path.join(run, "check.txt"), "w") as f:
        f.write(result["output"] + "\n")
    print(json.dumps({"decision": "block",
                      "reason": f"Not done yet (round {used + 1} of {cap}). {result['output']}\n"
                                "Keep working toward goal.md. If the goal cannot be met, say so on a line "
                                "starting `IMPOSSIBLE:` with the reason."}))
    return 0


def verify(run: str) -> int:
    result = evaluate(run)
    log(run, "verify", verdict=result["verdict"], why=result["why"])
    print(f"verdict={result['verdict']} why={result['why']}")
    if result["output"]:
        print(result["output"])
    return 0 if result["verdict"] == "met" else 1


# ---------- selftest ----------

def selftest() -> int:
    import shutil
    import tempfile
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _selftest import SelfTest

    t = SelfTest(os.path.abspath(__file__))
    tmp = tempfile.mkdtemp(prefix="devloop-selftest-")
    repo = os.path.join(tmp, "repo")
    os.makedirs(os.path.join(repo, "test"))

    def sh(*cmd, cwd=repo):
        subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)

    sh("git", "init", "-q")
    sh("git", "config", "user.email", "selftest@example.invalid")
    sh("git", "config", "user.name", "selftest")
    open(os.path.join(repo, "devloop.json"), "w").write(json.dumps(
        {"check": "test -f done.txt && grep -q ok done.txt", "protect": ["test/"], "max_rounds": 2}))
    open(os.path.join(repo, "test", "spec.txt"), "w").write("locked\n")
    sh("git", "add", ".")
    sh("git", "commit", "-qm", "start")
    base = git(repo, "rev-parse", "HEAD").strip()
    wt = os.path.join(tmp, "wt")
    sh("git", "worktree", "add", "-q", wt, "-b", "devloop/run-1", base)
    run = os.path.join(tmp, "runs", "1")
    os.makedirs(run)
    json.dump({"repo": repo, "worktree": wt, "base": base, "phase": "build"}, open(os.path.join(run, "state.json"), "w"))
    open(os.path.join(run, "goal.md"), "w").write("Rounds: 5\n\n## Protected\n- `extra.txt`\n")
    transcript = os.path.join(tmp, "agent.jsonl")
    open(transcript, "w").write(json.dumps({"type": "user", "message": {"content": f"Build it.\ndevloop-run: {run}\n"}}) + "\n")

    def stop(msg="done", agent=BUILDER):
        return t.run({"hook_event_name": "SubagentStop", "agent_type": agent, "agent_id": "a1",
                      "agent_transcript_path": transcript, "last_assistant_message": msg})

    def blocked(r):
        try:
            return json.loads(r[1]).get("decision") == "block"
        except ValueError:
            return False

    t.assert_quiet(stop(agent="loop-manager:critic"), "another agent stopping is ignored")

    r = stop()
    t.check(blocked(r) and "exited" in r[1], "check fails -> not yet, with the failing output", repr(r))

    open(os.path.join(wt, "test", "spec.txt"), "w").write("loosened\n")
    r = stop()
    t.check(blocked(r) and "test/spec.txt" in r[1], "protect list from devloop.json is enforced", repr(r))
    sh("git", "checkout", "--", "test/spec.txt", cwd=wt)

    r = stop()
    t.check(not blocked(r) and "verdict=cap" in open(os.path.join(run, "log")).read(),
            "after max_rounds (2, smaller than goal's 5) the builder may stop, logged as cap", repr(r))

    open(os.path.join(run, "log"), "w").write("")  # fresh rounds
    open(os.path.join(wt, "extra.txt"), "w").write("x\n")
    r = stop()
    t.check(blocked(r) and "extra.txt" in r[1], "critic's extra protected path is enforced", repr(r))
    os.remove(os.path.join(wt, "extra.txt"))

    open(os.path.join(wt, "devloop.json"), "w").write(json.dumps({"check": "true"}))
    r = stop()
    t.check(blocked(r) and "devloop.json" in r[1], "the check's own config file is protected", repr(r))
    sh("git", "checkout", "--", "devloop.json", cwd=wt)

    open(os.path.join(run, "log"), "w").write("")
    on_disk = open(os.path.join(repo, "devloop.json")).read()
    open(os.path.join(repo, "devloop.json"), "w").write(json.dumps({"check": "true", "protect": []}))
    r = stop()
    t.check(blocked(r) and "exited" in r[1], "editing the main checkout's devloop.json changes nothing: the base commit's is used", repr(r))
    open(os.path.join(repo, "devloop.json"), "w").write(on_disk)

    open(os.path.join(run, "log"), "w").write("")
    sh("git", "mv", "test/spec.txt", "spec-moved.txt", cwd=wt)
    sh("git", "commit", "-qm", "move", cwd=wt)
    r = stop()
    t.check(blocked(r) and "test/spec.txt" in r[1], "moving a protected file away counts as changing it", repr(r))
    sh("git", "reset", "-q", "--hard", base, cwd=wt)
    open(os.path.join(run, "log"), "w").write("")

    open(os.path.join(run, "log"), "w").write("")
    open(os.path.join(wt, "done.txt"), "w").write("ok\n")
    r = stop()
    t.check(blocked(r) and "uncommitted" in r[1], "passing but uncommitted -> not yet", repr(r))

    sh("git", "add", "done.txt", cwd=wt)
    sh("git", "commit", "-qm", "work", cwd=wt)
    r = stop()
    t.check(not blocked(r) and "verdict=met" in open(os.path.join(run, "log")).read(), "passing and committed -> met", repr(r))

    r = stop(msg="I tried.\nIMPOSSIBLE: the spec contradicts itself")
    t.check(not blocked(r) and "verdict=impossible" in open(os.path.join(run, "log")).read(), "IMPOSSIBLE line lets it stop", repr(r))

    open(transcript, "w").write(json.dumps({"type": "user", "message": {"content": "no run named"}}) + "\n")
    r = stop()
    t.check(r[0] == 0 and not blocked(r), "no run folder named -> never traps the agent", repr(r))

    rc = subprocess.run([sys.executable, os.path.abspath(__file__), "verify", run], capture_output=True, text=True)
    t.check(rc.returncode == 0 and "verdict=met" in rc.stdout, "verify command agrees with the hook", rc.stdout + rc.stderr)

    shutil.rmtree(tmp, ignore_errors=True)
    return t.report()


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if len(sys.argv) == 3 and sys.argv[1] == "verify":
        return verify(os.path.abspath(sys.argv[2]))
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    return hook(payload)


if __name__ == "__main__":
    sys.exit(main())
