#!/usr/bin/env python3
"""Ask Neuron about its own state right after an edit has been ingested, before any role runs.

For one rule change this stores the raw result of a neutral ask and a neutral explore, and derives a few plain
booleans from the text. The question is the fixed question from docs/questions.json for that rule, so it contains
no rule value and no claim about a change.

Derived fields (all are text matches on the raw results, saved next to the summary so a person can read them):
  ask_text_matches_old / _new        the answer text matches the replaced / the new value of the rule
  explore_matches_old / _new         the explore result text matches the replaced / the new value
  old_value_still_returned           the replaced value appears in the ask text or the explore text
  supersedes_marker_seen             the word "supersed" appears in either raw result
Neuron's own docs say a superseded claim is filtered from recall and that a supersedes edge links new to old.
`old_value_still_returned` true and `supersedes_marker_seen` false is what the pilot suggested; the probe measures
it directly instead of leaving it to the agents' reading.

  python3 scripts/state_probe.py --rule edit-window --label step4 --step 4 --run-dir runs/neuron/run-01

Status: run against live Neuron 0.3.1 daemons on 2026-10-29, after each edit in the 5 Neuron-arm runs (runs/neuron/run-0N/probes/).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import events as event_log  # noqa: E402
import steps  # noqa: E402

TOPICS = {"edit-window": "comment edit window", "error-response": "error response rule"}
QUESTION_IDS = {"edit-window": "edit-window", "error-response": "errors"}


def _question(rule: str) -> str:
    wanted = QUESTION_IDS[rule]
    for questions in steps.load_questions().values():
        for question in questions:
            if question["id"] == wanted:
                return question["text"]
    raise KeyError(wanted)


def derive(rule: str, ask_raw: str, explore_raw: str) -> dict:
    spec = next(r for r in steps.REPLACEMENTS if r["id"] == rule)
    old, new = re.compile(spec["old"]), re.compile(spec["new"])
    try:
        ask_text = json.loads(ask_raw).get("text", "")
    except (ValueError, AttributeError):
        ask_text = ask_raw
    fields = {
        "ask_text_matches_old": bool(old.search(ask_text)),
        "ask_text_matches_new": bool(new.search(ask_text)),
        "explore_matches_old": bool(old.search(explore_raw)),
        "explore_matches_new": bool(new.search(explore_raw)),
        "supersedes_marker_seen": "supersed" in (ask_raw + explore_raw).lower(),
    }
    fields["old_value_still_returned"] = fields["ask_text_matches_old"] or fields["explore_matches_old"]
    return fields


def probe(client, rule: str, label: str, step: int, run_dir: str, events_path: Optional[str] = None,
          vault: str = steps.TEAM_VAULT) -> dict:
    question = _question(rule)
    ask_raw = client.call_tool("ask", {"question": question, "vault": vault, "include_sources": True})
    explore_raw = client.call_tool("explore", {"topic": TOPICS[rule], "vault": vault})
    folder = os.path.join(run_dir, "probes")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "%s.ask.raw.json" % label), "w") as handle:
        handle.write(ask_raw)
    with open(os.path.join(folder, "%s.explore.raw.json" % label), "w") as handle:
        handle.write(explore_raw)
    summary = {"label": label, "rule": rule, "step": step, "question": question, "vault": vault,
               "raw": ["probes/%s.ask.raw.json" % label, "probes/%s.explore.raw.json" % label]}
    summary.update(derive(rule, ask_raw, explore_raw))
    summary["ts"] = event_log.utc_now()
    with open(os.path.join(folder, "%s.summary.json" % label), "w") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")
    if events_path:
        event_log.log_event(events_path, "state_probe", ts=summary["ts"], **{k: v for k, v in summary.items() if k not in ("ts", "raw")})
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    import mcp_client
    import neuron_ctl
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rule", required=True, choices=sorted(TOPICS))
    parser.add_argument("--label", required=True, help="matches the maintainer_edit label, for example step4")
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--events")
    args = parser.parse_args(argv)
    with open(os.environ.get("OKTO_NEURON_TOKEN_FILE", neuron_ctl.token_file())) as handle:
        token = handle.read().strip()
    url = os.environ.get("OKTO_NEURON_MCP_URL", neuron_ctl.mcp_url())
    summary = probe(mcp_client.McpClient(url, token), args.rule, args.label, args.step, args.run_dir, args.events)
    print(json.dumps({k: v for k, v in summary.items() if k != "raw"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
