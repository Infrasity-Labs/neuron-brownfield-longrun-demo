#!/usr/bin/env python3
"""Wait until the Neuron daemon reports its ingest queue idle, and record how long that took.

The wait is an upper bound: it is sampled every --poll seconds, and the daemon's folder watcher
needs a few quiet seconds before it picks a changed file up, so --settle seconds pass first.

The watcher polls its folders on an interval and a file must then be quiet for a few seconds, so right after an edit the
queue is still "idle" for up to tens of seconds. A live run showed the state probe running before the edit was ingested
because of that. Pass --after-total N (the ingest total read BEFORE the edit) and --min-new K (how many files the edit
changed): the wait then refuses to accept "idle" until the daemon's ingest total has grown by K, and fails when it has not
within --queue-timeout seconds. Idle must also be seen on two consecutive samples.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import events as event_log  # noqa: E402
import neuron_ctl  # noqa: E402

IDLE = re.compile(r"Ingest:\s+idle\b.*?\b0 processing\b.*?\b0 queued\b")


def ingest_idle() -> bool:
    out = subprocess.run(["okto-neuron", "status"], capture_output=True, text=True).stdout
    return bool(IDLE.search(out))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="what was ingested, for example policy-edit-window.md")
    parser.add_argument("--vault", required=True)
    parser.add_argument("--settle", type=float, default=15.0)
    parser.add_argument("--poll", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=3600.0)
    parser.add_argument("--after-total", type=int, help="the daemon's ingest total read before the edit (okto-neuron status)")
    parser.add_argument("--min-new", type=int, default=1, help="with --after-total: files the edit changed")
    parser.add_argument("--queue-timeout", type=float, default=180.0, help="with --after-total: give up when the daemon never queued them")
    parser.add_argument("--out", required=True, help="where to append the ingest time record (never the pilot file in demo-state/)")
    parser.add_argument("--events", help="also append an ingest_complete event to this events.jsonl")
    parser.add_argument("--event-label", help="label of the maintainer_edit event this wait belongs to (default: --label)")
    args = parser.parse_args(argv)

    started = time.time()
    started_at = event_log.utc_now()
    time.sleep(args.settle)
    idle_samples = 0
    while True:
        queued_ok = True
        if args.after_total is not None:
            counts = neuron_ctl.ingest_counts()
            queued_ok = counts is not None and counts[1] >= args.after_total + args.min_new
            if not queued_ok and time.time() - started > args.queue_timeout:
                print("the daemon did not queue %d new file(s) within %.0f s (ingest total %s, was %d)" % (
                    args.min_new, args.queue_timeout, counts[1] if counts else "unknown", args.after_total))
                return 2
        idle_samples = idle_samples + 1 if (queued_ok and ingest_idle()) else 0
        if idle_samples >= 2:
            break
        if time.time() - started > args.timeout:
            print("timed out after %.0f s with ingest still busy" % (time.time() - started))
            return 1
        time.sleep(args.poll)
    seconds = round(time.time() - started, 1)
    record = {
        "label": args.label,
        "vault": args.vault,
        "seconds_upper_bound": seconds,
        "sampled_every_s": args.poll,
        "settle_s": args.settle,
        "finished_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "a") as handle:
        handle.write(json.dumps(record) + "\n")
    if args.events:
        event_log.log_event(args.events, "ingest_complete", label=args.event_label or args.label, vault=args.vault,
                            started_at=started_at, seconds_upper_bound=seconds)
    print("ingest idle after %.1f s (%s, %s)" % (seconds, args.vault, args.label))
    return 0


if __name__ == "__main__":
    sys.exit(main())
