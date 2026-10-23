#!/usr/bin/env python3
"""Build demo-state/closeout-result.json from demo-state/asks.jsonl and nothing else.

Every number comes from a recorded ask or a recorded ingest time. A number with no source stays null.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import steps  # noqa: E402
import verify_citations  # noqa: E402

STATUS_KEYS = ("ok", "no_llm", "empty", "provider_error", "truncated", "abnormal_stop")
FALSE_NOTHING_FOUND = re.compile(r"(couldn'?t find|could not find|no information|nothing (in|about)|not (found|covered))", re.I)


def _load_jsonl(path: str) -> List[dict]:
    if not os.path.isfile(path):
        return []
    with open(path) as handle:
        return [json.loads(line) for line in handle if line.strip()]


def private_markers(private_dir: str) -> List[str]:
    """Distinctive sentences from the private notes. Their appearance in a team answer is a leak."""
    markers: List[str] = []
    if not os.path.isdir(private_dir):
        return markers
    for name in sorted(os.listdir(private_dir)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(private_dir, name)) as handle:
            lines = handle.read().splitlines()
        for line in lines:
            if line.lstrip().startswith("#"):
                continue
            for sentence in re.split(r"(?<=[.!?])\s+", line):
                sentence = sentence.strip()
                if len(sentence) >= 40:
                    markers.append(sentence.lower())
    return markers


def build(asks: List[dict], ingest: List[dict], private_dir: str, live_recheck: bool = False,
          roots: Optional[Dict[str, str]] = None) -> dict:
    statuses = {key: 0 for key in STATUS_KEYS}
    statuses["unparsed"] = 0
    with_sources = suspect_finish = missing_finish = override_flagged = override_redundant = 0
    cites_total = cites_ok = cites_live_ok = 0
    provider_errors = []
    team_leaks = []
    other_vault_asks = 0
    markers = private_markers(private_dir)

    for ask in asks:
        status = ask.get("synthesis_status")
        statuses[status if status in statuses else "unparsed"] += 1
        if ask.get("sources"):
            with_sources += 1
        finish = ask.get("finish_reason")
        if finish is None:
            missing_finish += 1
        elif finish != "stop":
            suspect_finish += 1
        if ask.get("vault_served") not in (steps.TEAM_VAULT, steps.PRIVATE_VAULT):
            other_vault_asks += 1
        override = ask.get("vault_override_ignored")
        if override:
            # Planner and Builder connect pinned to team and also pass vault "team", so Neuron reports their
            # override as ignored. That is redundant, not a mis-scoped agent. Only a different vault counts.
            if override == ask.get("vault_served"):
                override_redundant += 1
            else:
                override_flagged += 1
        for check in ask.get("citation_checks", []):
            cites_total += 1
            cites_ok += 1 if check.get("ok") else 0
        if live_recheck and ask.get("vault_served"):
            for res in verify_citations.verify_sources(ask.get("sources", []), ask["vault_served"], roots):
                cites_live_ok += 1 if res["ok"] else 0
        if status == "provider_error":
            follow = ask.get("agent_followup", "")
            provider_errors.append({
                "step": ask.get("step"), "role": ask.get("role"), "agent_followup": follow,
                "claimed_nothing_found": bool(FALSE_NOTHING_FOUND.search(follow)),
            })
        if ask.get("vault_served") == steps.TEAM_VAULT:
            haystack = (ask.get("text", "") + " " + json.dumps(ask.get("sources", []))).lower()
            if any(marker in haystack for marker in markers):
                team_leaks.append({"step": ask.get("step"), "role": ask.get("role")})

    stale = []
    for rule in steps.REPLACEMENTS:
        for ask in asks:
            if ask.get("step", 0) < rule["step"] or ask.get("vault_served") != steps.TEAM_VAULT:
                continue
            text = ask.get("text", "")
            if re.search(rule["old"], text) and not re.search(rule["new"], text):
                stale.append({"rule": rule["id"], "step": ask.get("step"), "role": ask.get("role")})

    return {
        "questions_asked": len(asks),
        "questions_with_sources": with_sources,
        "synthesis_status_counts": statuses,
        "finish_reason_not_stop": suspect_finish,
        "finish_reason_missing": missing_finish,
        "vault_override_ignored_count": override_flagged,
        "vault_override_ignored_same_vault_count": override_redundant,
        "citations_checked_at_record_time": cites_total,
        "citations_passed_at_record_time": cites_ok,
        "citations_passed_on_recheck": cites_live_ok if live_recheck else None,
        "claims_replaced": [r["id"] for r in steps.REPLACEMENTS if any(a.get("step", 0) >= r["step"] for a in asks)],
        "stale_rule_answers_after_replacement": stale,
        "provider_error_answers": provider_errors,
        "asks_to_vaults_other_than_the_two_demo_vaults": other_vault_asks,
        "private_notes_in_team_answers": len(team_leaks),
        "private_leak_details": team_leaks,
        "ingest_seconds_per_note": ingest or None,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asks", default="demo-state/asks.jsonl")
    parser.add_argument("--ingest", default="demo-state/ingest-times.jsonl")
    parser.add_argument("--private-dir", default="vault-private")
    parser.add_argument("--out", default="demo-state/closeout-result.json")
    parser.add_argument("--recheck", action="store_true", help="also re-read the cited bytes now")
    args = parser.parse_args(argv)
    asks = _load_jsonl(args.asks)
    if not asks:
        print("no recorded asks in %s; nothing to total" % args.asks)
        return 2
    result = build(asks, _load_jsonl(args.ingest), args.private_dir, live_recheck=args.recheck)
    with open(args.out, "w") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
