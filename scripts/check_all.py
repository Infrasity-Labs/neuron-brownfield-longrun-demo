#!/usr/bin/env python3
"""Run every offline checker in one go. This is what the fast workflow runs after the unit tests.

  1. personal data      scripts/scan_personal.py        no home path, working folder name or personal vault name in tracked files
  2. rule values        scripts/scan_rule_values.py     no rule value in a prompt, a fixed question or an agent file
  3. README             scripts/check_readme.py         every README number agrees with the recorded files
  4. starting state     scripts/reset.py --check        vault/ holds the start-state notes (private folder ignored)
  5. notes manifest     scenarios/notes.json            every note in vault/ and scenarios/ is labeled code or synthetic

The pilot's own isolation and rule-value failures are findings about the pilot, not checks, and are not run here:
  python3 scripts/check_transcripts.py demo-state/transcripts/*.jsonl
  python3 scripts/scan_rule_values.py --asks demo-state/asks.jsonl
"""
from __future__ import annotations

import json
import os
import sys
from typing import Callable, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_readme  # noqa: E402
import reset  # noqa: E402
import scan_personal  # noqa: E402
import scan_rule_values  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def personal() -> List[str]:
    matches, _binary = scan_personal.scan(REPO)
    return ["%s:%d %s" % (rel, hit[0], hit[1]) for rel, hits in sorted(matches.items()) for hit in hits[:3]]


def rule_values() -> List[str]:
    return ["%s:%d [%s] %s" % (h["where"], h["line"], h["rule"], h["match"]) for h in scan_rule_values.scan(REPO)]


def readme() -> List[str]:
    return check_readme.check(REPO)


def starting_state() -> List[str]:
    return [p for p in reset.drift(REPO) if not p.startswith("vault-private/")]


def notes_manifest() -> List[str]:
    with open(os.path.join(REPO, "scenarios", "notes.json")) as handle:
        listed = {n["file"] for n in json.load(handle)["notes"]}
    problems = []
    on_disk = set()
    for folder in ("vault", "scenarios/step04/after", "scenarios/step07/after", "scenarios/private-notes", "scenarios/decoy-notes"):
        for name in os.listdir(os.path.join(REPO, folder)):
            if name.endswith(".md"):
                on_disk.add("%s/%s" % (folder, name))
    for missing in sorted(on_disk - listed):
        problems.append("%s is not labeled in scenarios/notes.json" % missing)
    for stale in sorted(listed - on_disk):
        problems.append("scenarios/notes.json lists %s which does not exist" % stale)
    return problems


CHECKS: List[Tuple[str, Callable[[], List[str]]]] = [
    ("personal data", personal),
    ("rule values in prompts", rule_values),
    ("README against recorded files", readme),
    ("starting state of the notes", starting_state),
    ("notes labeled code or synthetic", notes_manifest),
]


def main() -> int:
    failed = 0
    for name, check in CHECKS:
        problems = check()
        print("%-34s %s" % (name, "ok" if not problems else "%d problem(s)" % len(problems)))
        for problem in problems[:10]:
            print("    " + problem)
        failed += 1 if problems else 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
