#!/usr/bin/env python3
"""Wait until the Neuron daemon reports its ingest queue idle, and record how long that took.

The wait is an upper bound: it is sampled every --poll seconds, and the daemon's folder watcher
needs a few quiet seconds before it picks a changed file up, so --settle seconds pass first.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
import time
from typing import List, Optional

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
    parser.add_argument("--out", default="demo-state/ingest-times.jsonl")
    args = parser.parse_args(argv)

    started = time.time()
    time.sleep(args.settle)
    while not ingest_idle():
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
    with open(args.out, "a") as handle:
        handle.write(json.dumps(record) + "\n")
    print("ingest idle after %.1f s (%s, %s)" % (seconds, args.vault, args.label))
    return 0


if __name__ == "__main__":
    sys.exit(main())
