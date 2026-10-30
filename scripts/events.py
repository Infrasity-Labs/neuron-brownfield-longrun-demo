#!/usr/bin/env python3
"""One timeline file for every event of a run, with a UTC timestamp on each.

The order of events must be checkable from one file: a Maintainer edit, the moment Neuron finished ingest of
that edit, the state probe after it, and every ask. Each line of events.jsonl is

  {"ts": "2026-10-30T09:15:02.123Z", "event": "maintainer_edit", ...}

`ts` is always UTC with millisecond precision. Event names in use:

  run_start, run_end            the run
  role_start, role_end          one role session (role, step, session transcript)
  maintainer_edit               a note was written or removed (files)
  ingest_complete               wait_ingest.py saw Neuron's ingest queue idle (label, seconds_upper_bound)
  state_probe                   scripts/state_probe.py asked Neuron about its own state after an edit
  ask                           one Neuron ask by a role (asked_at, answered_at come from the transcript)
  explore                       one Neuron explore by a role
  outage_start, outage_end      the scripted step 9 outage
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from typing import Iterator, List, Optional


def utc_now() -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (now.microsecond // 1000)


def log_event(path: str, event: str, ts: Optional[str] = None, **fields) -> dict:
    record = {"ts": ts or utc_now(), "event": event}
    record.update(fields)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a") as handle:
        handle.write(json.dumps(record) + "\n")
    return record


def read_events(path: str) -> List[dict]:
    if not os.path.isfile(path):
        return []
    with open(path) as handle:
        return [json.loads(line) for line in handle if line.strip()]


def timeline(events: List[dict]) -> List[dict]:
    """Events in time order. ask and explore events are written after their role session ends, with the
    timestamp the transcript gave them, so file order is not time order and analysis must sort."""
    return sorted(events, key=lambda e: e["ts"])


def check_edit_order(events: List[dict]) -> List[str]:
    """Problems with the order of edit, ingest, probe and first later ask. Empty when the order is right.

    For every maintainer_edit event: an ingest_complete with the same label must exist after it. Then no ask of
    the edit's own step may fall between the edit and the end of the ingest and the probe that follows it. (The
    Reviewer of step 4 starts only after ingest, so any ask of step 4 inside that window means the runner did
    not wait.)
    """
    problems = []
    ordered = timeline(events)
    for edit in [e for e in ordered if e["event"] == "maintainer_edit"]:
        label = edit.get("label")
        ingest = next((e for e in ordered if e["event"] == "ingest_complete" and e.get("label") == label
                       and e["ts"] >= edit["ts"]), None)
        if ingest is None:
            problems.append("edit %s at %s has no later ingest_complete" % (label, edit["ts"]))
            continue
        probe = next((e for e in ordered if e["event"] == "state_probe" and e.get("label") == label
                      and e["ts"] >= ingest["ts"]), None)
        gate = probe["ts"] if probe else ingest["ts"]
        step = edit.get("step", 0)
        early = [a for a in ordered if a["event"] == "ask" and a.get("step", 0) == step and edit["ts"] <= a["ts"] < gate]
        for ask in early:
            problems.append("ask at %s (step %s) came before ingest/probe for edit %s finished at %s" % (
                ask["ts"], ask.get("step"), label, gate))
    return problems


def iter_pairs(events: List[dict], first: str, then: str) -> Iterator[tuple]:
    """Yield (first event, next `then` event after it) for each `first` event, in file order."""
    for index, event in enumerate(events):
        if event["event"] != first:
            continue
        follow = next((e for e in events[index + 1:] if e["event"] == then), None)
        yield event, follow


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "events.jsonl"
    events = read_events(path)
    for event in timeline(events):
        print("%s  %-16s %s" % (event["ts"], event["event"], {k: v for k, v in event.items() if k not in ("ts", "event")}))
    problems = check_edit_order(events)
    for problem in problems:
        print("PROBLEM: " + problem)
    print("%d event(s), %d ordering problem(s)" % (len(events), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
