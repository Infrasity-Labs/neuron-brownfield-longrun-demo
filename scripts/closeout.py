#!/usr/bin/env python3
"""Build closeout-result.json from asks.jsonl and nothing else.

Every number comes from a recorded ask or a recorded ingest time. A number with no source stays null.

Definitions (fixed here so the README table can be checked against the JSON):
  returned sources            an ask that returned a non-empty source list AND a non-empty answer text. A provider_error
                              ask can carry sources and no text; it is counted in `questions_with_sources` only.
  stale anchor                a source whose cited byte range no longer matches the note: record-time check reason
                              "byte range is past the end of the file" or "hash mismatch". That is Neuron answering with an
                              anchor into an earlier version of a note, which is a product behaviour. Every other failed check
                              (file not found, bad range, bad path) is counted as `other_citation_failures`.
  finish_reason_missing       an ask whose response carried no finish_reason at all. It is reported apart from finish_reason
                              values other than stop.

  python3 scripts/closeout.py --asks A --out O [--recheck]            build a fresh file
  python3 scripts/closeout.py --amend demo-state/closeout-result.json  add the new derived keys to an existing file and leave
                                                                       every existing key byte for byte as it was (used on the
                                                                       pilot, whose live recheck and private-note check cannot be repeated)
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

STALE_REASONS = ("byte range is past the end of the file", "hash mismatch")
ANCHOR_PREFIX = re.compile(r"^\.marginalia/sources/[^/]+/")
DERIVED_KEYS = ("questions_with_sources_and_answer", "stale_anchor_failures", "other_citation_failures",
                "stale_anchor_failures_by_note", "stale_anchor_asks")
STATUS_KEYS = ("ok", "no_llm", "empty", "provider_error", "truncated", "abnormal_stop")
FALSE_NOTHING_FOUND = re.compile(r"(couldn'?t find|could not find|no information|nothing (in|about)|not (found|covered))", re.I)


def _load_jsonl(path: str) -> List[dict]:
    if not os.path.isfile(path):
        return []
    with open(path) as handle:
        return [json.loads(line) for line in handle if line.strip()]


def private_markers(private_dirs) -> List[str]:
    """Distinctive sentences from the private notes. Their appearance in a team answer is a leak.

    `private_dirs` is one folder or a list of folders. A sentence of 40 characters or more is a marker. This check
    misses a paraphrase; scripts/private_facts.py covers that with a short list of facts.
    """
    if isinstance(private_dirs, str):
        private_dirs = [private_dirs]
    markers: List[str] = []
    for private_dir in private_dirs:
        if not os.path.isdir(private_dir):
            continue
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


def derive_extra(asks: List[dict]) -> dict:
    """The keys added after the pilot: the returned-sources definition and the stale-anchor split. Pure function of the asks."""
    with_answer = 0
    stale = other = 0
    by_note: Dict[str, int] = {}
    stale_asks = []
    for number, ask in enumerate(asks, 1):
        if ask.get("sources") and (ask.get("text") or "").strip():
            with_answer += 1
        ask_stale = 0
        for check in ask.get("citation_checks", []):
            if check.get("ok"):
                continue
            if check.get("reason") in STALE_REASONS:
                stale += 1
                ask_stale += 1
                note = ANCHOR_PREFIX.sub("", check.get("path") or "unknown")
                by_note[note] = by_note.get(note, 0) + 1
            else:
                other += 1
        if ask_stale:
            stale_asks.append({"ask_number": number, "step": ask.get("step"), "role": ask.get("role"), "stale_anchors": ask_stale})
    return {
        "questions_with_sources_and_answer": with_answer,
        "stale_anchor_failures": stale,
        "other_citation_failures": other,
        "stale_anchor_failures_by_note": dict(sorted(by_note.items())),
        "stale_anchor_asks": stale_asks,
    }


def build(asks: List[dict], ingest: List[dict], private_dir, live_recheck: bool = False,
          roots: Optional[Dict[str, str]] = None, facts_path: Optional[str] = None) -> dict:
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

    candidates = []
    if facts_path:
        import private_facts
        candidates = private_facts.find_candidates([a for a in asks if a.get("vault_served") == steps.TEAM_VAULT],
                                                   private_facts.load_facts(facts_path))
    result = {
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
    result.update(derive_extra(asks))
    if facts_path:
        result["private_fact_candidates_in_team_answers"] = candidates
    return result


def amend(existing: dict, asks: List[dict]) -> dict:
    """Add the derived keys to an existing result. Every existing key keeps its value and its position."""
    extra = derive_extra(asks)
    merged = dict(existing)
    for key in DERIVED_KEYS:
        merged[key] = extra[key]
    return merged


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asks", required=True)
    parser.add_argument("--ingest", default="")
    parser.add_argument("--private-dir", action="append",
                        help="folder of private notes whose sentences are leak markers (repeatable; default: "
                             "scenarios/private-notes and vault-private)")
    parser.add_argument("--facts", default=os.path.join(steps.REPO, "scenarios", "private-facts.json"),
                        help="private facts for the paraphrase-aware leak candidates ('' to skip)")
    parser.add_argument("--out", help="where to write the result (required unless --amend)")
    parser.add_argument("--recheck", action="store_true", help="also re-read the cited bytes now")
    parser.add_argument("--amend", metavar="FILE", help="add the derived keys to this existing result and change nothing else")
    args = parser.parse_args(argv)
    asks = _load_jsonl(args.asks)
    if not asks:
        print("no recorded asks in %s; nothing to total" % args.asks)
        return 2
    if args.amend:
        with open(args.amend) as handle:
            existing = json.load(handle)
        merged = amend(existing, asks)
        with open(args.amend, "w") as handle:
            json.dump(merged, handle, indent=2)
            handle.write("\n")
        print(json.dumps({k: merged[k] for k in DERIVED_KEYS}, indent=2))
        return 0
    if not args.out:
        parser.error("--out is required (the pilot's demo-state/closeout-result.json is never a default)")
    private_dirs = args.private_dir or [os.path.join(steps.REPO, "scenarios", "private-notes"), os.path.join(steps.REPO, "vault-private")]
    result = build(asks, _load_jsonl(args.ingest), private_dirs, live_recheck=args.recheck, facts_path=args.facts or None)
    with open(args.out, "w") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
