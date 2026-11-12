#!/usr/bin/env python3
"""Turns one development-loop run (or several) into numbers.

    loop_report.py <run folder> [<run folder> ...] [--json]

For each run it reads the run's `log` and prints: the outcome, minutes from start to finish,
how many times the check said "not yet" while building and while fixing findings, the final
verdict, findings per reviewer, and tokens per agent and model.

Tokens come from the agents' own transcripts. Every agent the skill starts has the line
`devloop-run: <run folder>` in its first message, so the report finds them in the folder of
the builder's transcript (the hook logs that path on each check). A run whose transcripts are
gone still reports everything else, and says `tokens=unknown`.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

LINE = re.compile(r'(\w+)=("([^"]*)"|\S+)')


def parse(line: str) -> dict:
    parts = line.split(" ", 1)
    kv = {m.group(1): (m.group(3) if m.group(3) is not None else m.group(2)) for m in LINE.finditer(parts[1] if len(parts) > 1 else "")}
    kv["t"] = parts[0]
    return kv


def ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def agent_usage(run: str, transcripts: set[str]) -> dict:
    """tokens by agent type and model, from every transcript naming this run."""
    dirs = {os.path.dirname(t) for t in transcripts if t}
    usage: dict = defaultdict(Counter)
    seen = 0
    for d in dirs:
        for path in glob.glob(os.path.join(d, "agent-*.jsonl")):
            try:
                lines = open(path).read().splitlines()
            except OSError:
                continue
            if not lines or f"devloop-run: {run}" not in lines[0] and not any(f"devloop-run: {run}" in l for l in lines[:3]):
                continue
            seen += 1
            meta = os.path.join(d, os.path.basename(path).replace(".jsonl", ".meta.json"))
            kind = "agent"
            if os.path.exists(meta):
                try:
                    kind = json.load(open(meta)).get("agentType", kind)
                except ValueError:
                    pass
            # One reply with several parts (text, tool calls) is written as several lines that
            # share a message id and repeat its usage; count each id once, at its last line.
            last: dict = {}
            for i, l in enumerate(lines):
                try:
                    rec = json.loads(l)
                except ValueError:
                    continue
                msg = rec.get("message") or {}
                if rec.get("type") == "assistant" and msg.get("usage"):
                    last[msg.get("id") or f"line-{i}"] = msg
            for msg in last.values():
                u = msg["usage"]
                key = f"{kind} ({msg.get('model', '?')})"
                usage[key]["input"] += u.get("input_tokens", 0)
                usage[key]["cache_write"] += u.get("cache_creation_input_tokens", 0)
                usage[key]["cache_read"] += u.get("cache_read_input_tokens", 0)
                usage[key]["output"] += u.get("output_tokens", 0)
    return {"agents_found": seen, "by_agent": {k: dict(v) for k, v in usage.items()}}


def report(run: str) -> dict:
    run = os.path.abspath(run)
    events = [parse(l) for l in open(os.path.join(run, "log")).read().splitlines() if l.strip()]
    state = json.load(open(os.path.join(run, "state.json")))
    checks = [e for e in events if e.get("ev") == "check"]
    not_yet = Counter(e.get("phase", "build") for e in checks if e.get("verdict") == "not_yet")
    why = Counter(e.get("why") for e in checks if e.get("verdict") == "not_yet")
    verify = [e for e in events if e.get("ev") == "verify"]
    findings = {e.get("kind"): int(e.get("findings", 0)) for e in events if e.get("ev") == "review"}
    start = next((e["t"] for e in events if e.get("ev") == "run_started"), events[0]["t"] if events else None)
    end = next((e["t"] for e in reversed(events) if e.get("ev") == "run_finished"), events[-1]["t"] if events else None)
    out = {
        "run": state.get("run"),
        "phase": state.get("phase"),
        "minutes": round((ts(end) - ts(start)).total_seconds() / 60, 1) if start and end else None,
        "not_yet_build": not_yet.get("build", 0),
        "not_yet_fix": not_yet.get("fix", 0),
        "not_yet_reasons": dict(why),
        "last_check": checks[-1].get("verdict") if checks else None,
        "verified": verify[-1].get("verdict") if verify else None,
        "findings": findings,
        "pr": next((e.get("url") for e in events if e.get("ev") == "pr_opened"), None),
        # guidance_proposed rung=<tip|goal|tenet|skill|check|none>; runs before 0.2 logged lesson_proposed
        "guidance": next((e.get("rung", "?") for e in events if e.get("ev") == "guidance_proposed"),
                         "tip" if any(e.get("ev") == "lesson_proposed" for e in events) else None),
    }
    out["usage"] = agent_usage(run, {e.get("transcript", "") for e in checks})
    return out


def main(argv: list[str]) -> int:
    runs = [a for a in argv[1:] if not a.startswith("--")]
    if not runs:
        print(__doc__)
        return 2
    results = [report(r) for r in runs]
    if "--json" in argv:
        print(json.dumps(results, indent=1))
        return 0
    for r in results:
        print(f"run={r['run']} phase={r['phase']} minutes={r['minutes']} verified={r['verified']} last_check={r['last_check']}")
        print(f"  not_yet build={r['not_yet_build']} fix={r['not_yet_fix']} reasons={r['not_yet_reasons']}")
        print(f"  findings {' '.join(f'{k}={v}' for k, v in r['findings'].items()) or 'none'}  pr={r['pr']}  guidance={r['guidance']}")
        u = r["usage"]
        if not u["agents_found"]:
            print("  tokens=unknown (no agent transcripts found)")
        for k, v in u["by_agent"].items():
            print(f"  tokens {k}: " + " ".join(f"{a}={b}" for a, b in v.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
