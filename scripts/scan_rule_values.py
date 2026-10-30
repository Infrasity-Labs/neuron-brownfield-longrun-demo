#!/usr/bin/env python3
"""Fail when a prompt, a fixed question or an agent file contains a rule value.

An agent must get a rule value (the edit window, the article cap, the field names, the error shape) from its
memory arm, never from its instructions. A value in an instruction produces that value whether or not memory
works. This script reads the patterns in scenarios/rule_values.json and scans:

  default             docs/prompts/**/*.md, agents/**/*.md, agents/*.md, and every question text in docs/questions.json
  --asks FILE         the `request.question` of every ask in a recorded asks.jsonl
  --specs DIR         every Markdown spec a Planner wrote (a value copied into a spec reaches the Builder
                      through the spec file: the one-hop leak)

Exit status 1 when any pattern matches. The notes themselves, and the notes pasted into the arm B prompt, are
the rule source and are not scanned.

  python3 scripts/scan_rule_values.py
  python3 scripts/scan_rule_values.py --asks demo-state/asks.jsonl     (the pilot asks fail, by design: see demo-state/README.md)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from typing import Dict, Iterator, List, Optional, Tuple

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULE_VALUES = os.path.join(REPO, "scenarios", "rule_values.json")


def load_patterns(path: str = RULE_VALUES) -> List[Tuple[str, "re.Pattern[str]"]]:
    with open(path) as handle:
        data = json.load(handle)
    patterns = []
    for item in data["patterns"]:
        flags = re.I if "i" in item.get("flags", "") else 0
        patterns.append((item["id"], re.compile(item["regex"], flags)))
    return patterns


def scan_text(text: str, patterns: List[Tuple[str, "re.Pattern[str]"]]) -> List[Tuple[int, str, str]]:
    """(line, pattern id, matched text) for every match."""
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        for rule_id, pattern in patterns:
            for match in pattern.finditer(line):
                hits.append((number, rule_id, match.group(0)))
    return hits


def default_files(repo: str = REPO) -> List[str]:
    files = glob.glob(os.path.join(repo, "docs", "prompts", "**", "*.md"), recursive=True)
    files += glob.glob(os.path.join(repo, "agents", "**", "*.md"), recursive=True)
    return sorted(files)


def question_texts(repo: str = REPO) -> Iterator[Tuple[str, str]]:
    with open(os.path.join(repo, "docs", "questions.json")) as handle:
        data = json.load(handle)
    for key, questions in data["steps"].items():
        for question in questions:
            yield "docs/questions.json:%s:%s" % (key, question["id"]), question["text"]


def asked_questions(asks_path: str) -> Iterator[Tuple[str, str]]:
    with open(asks_path) as handle:
        for number, line in enumerate(handle, 1):
            if line.strip():
                record = json.loads(line)
                yield "%s:%d" % (os.path.relpath(asks_path, REPO) if asks_path.startswith(REPO) else asks_path, number), \
                    (record.get("request") or {}).get("question") or ""


def scan(repo: str = REPO, asks: Optional[str] = None, specs: Optional[str] = None,
         patterns: Optional[List[Tuple[str, "re.Pattern[str]"]]] = None) -> List[dict]:
    patterns = patterns or load_patterns(os.path.join(repo, "scenarios", "rule_values.json"))
    found: List[dict] = []

    def add(where: str, text: str) -> None:
        for number, rule_id, matched in scan_text(text, patterns):
            found.append({"where": where, "line": number, "rule": rule_id, "match": matched})

    if asks:
        for where, text in asked_questions(asks):
            add(where, text)
        return found
    if specs:
        for path in sorted(glob.glob(os.path.join(specs, "*.md"))):
            with open(path) as handle:
                add(os.path.basename(path), handle.read())
        return found
    for path in default_files(repo):
        with open(path) as handle:
            add(os.path.relpath(path, repo), handle.read())
    for where, text in question_texts(repo):
        add(where, text)
    return found


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--asks", help="scan the questions in a recorded asks.jsonl instead of the prompts")
    parser.add_argument("--specs", help="scan the Planner's spec files in this folder instead of the prompts")
    args = parser.parse_args(argv)
    hits = scan(asks=args.asks, specs=args.specs)
    for hit in hits[:60]:
        print("%s:%d: [%s] %s" % (hit["where"], hit["line"], hit["rule"], hit["match"]))
    if len(hits) > 60:
        print("... %d more" % (len(hits) - 60))
    target = "recorded questions" if args.asks else "spec files" if args.specs else "prompts, agent files and fixed questions"
    print("rule-value scan of %s: %d hit(s)" % (target, len(hits)))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
