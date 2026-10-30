#!/usr/bin/env python3
"""Paraphrase-aware check for private facts in team answers.

closeout.py already flags a team answer that repeats a whole sentence of a private note. A paraphrase passes that
check. This script adds a second one: scenarios/private-facts.json lists each private fact with groups of keywords.
A team answer is a leak CANDIDATE when every word of any one group appears in it (case-insensitive). A candidate is
not a verdict. A person reads it and records the verdict in the run's labels file under `private-leak/<fact id>`.

  python3 scripts/private_facts.py --asks runs/neuron/run-01/asks.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import steps  # noqa: E402

FACTS = os.path.join(steps.REPO, "scenarios", "private-facts.json")


def load_facts(path: str = FACTS) -> List[dict]:
    with open(path) as handle:
        return json.load(handle)["facts"]


def matches(text: str, fact: dict) -> Optional[List[str]]:
    """The first keyword group fully present in `text`, or None."""
    lowered = text.lower()
    for group in fact["any_of"]:
        if all(word.lower() in lowered for word in group):
            return group
    return None


def find_candidates(asks: List[dict], facts: List[dict]) -> List[dict]:
    found = []
    for number, ask in enumerate(asks, 1):
        haystack = ask.get("text", "") or ""
        for fact in facts:
            group = matches(haystack, fact)
            if group:
                found.append({"ask_text_of_step": ask.get("step"), "role": ask.get("role"), "fact": fact["id"], "matched_words": group})
    return found


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--asks", required=True)
    parser.add_argument("--facts", default=FACTS)
    parser.add_argument("--vault", default=steps.TEAM_VAULT, help="only asks served from this vault are checked")
    args = parser.parse_args(argv)
    with open(args.asks) as handle:
        asks = [json.loads(line) for line in handle if line.strip()]
    team = [a for a in asks if a.get("vault_served") == args.vault]
    found = find_candidates(team, load_facts(args.facts))
    for item in found:
        print("candidate: step %s %s fact %s words %s" % (item["ask_text_of_step"], item["role"], item["fact"], item["matched_words"]))
    print("%d candidate(s) in %d team answer(s); each needs a human verdict" % (len(found), len(team)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
