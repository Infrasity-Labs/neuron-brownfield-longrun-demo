#!/usr/bin/env python3
"""Put the repository back to the starting state of the experiment.

  python3 scripts/reset.py            reset the notes and the Reviewer's private folder
  python3 scripts/reset.py --check    only report whether the working tree is at the starting state

What it does:
  1. For every scenarios/<step>/after/ file: restore scenarios/<step>/before/<name> into vault/, or delete
     vault/<name> when the step adds a new note (ops-runbook.md).
  2. Remove vault/specs/ (the pilot wrote specs there; new runs keep specs outside the watched folder).
  3. Empty vault-private/ and copy the synthetic private notes from scenarios/private-notes/ into it.
  4. Report any change under app/ (the runner never edits app/, it works in a copy, so a change here means a
     person edited it). It is reported and never reverted automatically.

Per-run state (workdirs, specs, app edits) lives in a temporary canonical tree that run_demo.py builds for each
run with scripts/build_workdir.py, so a new run never inherits the previous run's code.
"""
from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import subprocess
import sys
from typing import List, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _scenario_steps(scenarios: str) -> List[str]:
    return sorted(d for d in os.listdir(scenarios) if d.startswith("step") and os.path.isdir(os.path.join(scenarios, d, "after")))


def drift(repo: str = REPO) -> List[str]:
    """What differs from the starting state. Empty list means the notes are at the starting state."""
    vault = os.path.join(repo, "vault")
    scenarios = os.path.join(repo, "scenarios")
    problems = []
    for step in _scenario_steps(scenarios):
        after = os.path.join(scenarios, step, "after")
        before = os.path.join(scenarios, step, "before")
        for name in sorted(os.listdir(after)):
            live = os.path.join(vault, name)
            start = os.path.join(before, name)
            if os.path.isfile(start):
                if not os.path.isfile(live) or not filecmp.cmp(live, start, shallow=False):
                    problems.append("vault/%s differs from %s/before/%s" % (name, step, name))
            elif os.path.exists(live):
                problems.append("vault/%s exists but is added only at %s" % (name, step))
    if os.path.isdir(os.path.join(vault, "specs")):
        problems.append("vault/specs/ exists")
    private_src = os.path.join(scenarios, "private-notes")
    private = os.path.join(repo, "vault-private")
    wanted = sorted(os.listdir(private_src)) if os.path.isdir(private_src) else []
    have = sorted(n for n in os.listdir(private) if n.endswith(".md")) if os.path.isdir(private) else []
    if wanted != have:
        problems.append("vault-private/ holds %s, expected %s" % (have, wanted))
    return problems


def app_changes(repo: str = REPO) -> List[str]:
    out = subprocess.run(["git", "-C", repo, "status", "--porcelain", "--", "app"], capture_output=True, text=True)
    return [line for line in out.stdout.splitlines() if line.strip()] if out.returncode == 0 else []


def reset(repo: str = REPO) -> List[str]:
    vault = os.path.join(repo, "vault")
    scenarios = os.path.join(repo, "scenarios")
    actions = []
    for step in _scenario_steps(scenarios):
        after = os.path.join(scenarios, step, "after")
        before = os.path.join(scenarios, step, "before")
        for name in sorted(os.listdir(after)):
            live = os.path.join(vault, name)
            start = os.path.join(before, name)
            if os.path.isfile(start):
                shutil.copyfile(start, live)
                actions.append("restored vault/%s" % name)
            elif os.path.exists(live):
                os.remove(live)
                actions.append("removed vault/%s" % name)
    if os.path.isdir(os.path.join(vault, "specs")):
        shutil.rmtree(os.path.join(vault, "specs"))
        actions.append("removed vault/specs/")
    private = os.path.join(repo, "vault-private")
    os.makedirs(private, exist_ok=True)
    for name in os.listdir(private):
        path = os.path.join(private, name)
        if os.path.isfile(path) and name.endswith(".md"):
            os.remove(path)
    private_src = os.path.join(scenarios, "private-notes")
    for name in sorted(os.listdir(private_src)):
        shutil.copyfile(os.path.join(private_src, name), os.path.join(private, name))
        actions.append("seeded vault-private/%s" % name)
    return actions


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="report drift from the starting state, change nothing")
    args = parser.parse_args(argv)
    if args.check:
        problems = drift()
        for problem in problems:
            print("drift: " + problem)
        print("starting state: %s" % ("yes" if not problems else "NO (%d difference(s))" % len(problems)))
        return 1 if problems else 0
    for action in reset():
        print(action)
    for line in app_changes():
        print("app/ is not at the committed state, not reverted: " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
