#!/usr/bin/env python3
"""Count the model calls an isolated Neuron daemon made, from its own log, and write daemon-usage.json into a run folder.

The daemon logs one `litellm usage model=... prompt_tokens=N completion_tokens=M ... step=S` line per successful model call
and one `litellm completion failed ...` line per failed one (okto-neuron 0.3.1, `<HOME>/.okto-neuron/logs/okto-neuron-serve.log`).
Tokens only: nothing is converted to dollars. Run it before the isolated HOME is deleted.

  python3 scripts/daemon_usage.py --log <HOME>/.okto-neuron/logs/okto-neuron-serve.log --out runs/neuron/run-01/daemon-usage.json
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
from typing import List, Optional

USAGE = re.compile(r"litellm usage model=(\S+) prompt_tokens=(\d+) completion_tokens=(\d+).*?step=(\w+)")
EXCEPTION = re.compile(r"(\w+Error)")


def summarize(log_path: str) -> dict:
    calls: "collections.Counter[str]" = collections.Counter()
    failed_by: "collections.Counter[str]" = collections.Counter()
    levels: "collections.Counter[str]" = collections.Counter()
    prompt = completion = 0
    models = set()
    first = last = None
    with open(log_path) as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            first = first or event.get("ts")
            last = event.get("ts")
            levels[event.get("level", "?")] += 1
            message = event.get("msg", "")
            usage = USAGE.search(message)
            if usage:
                models.add(usage.group(1))
                prompt += int(usage.group(2))
                completion += int(usage.group(3))
                calls[usage.group(4)] += 1
            elif "litellm completion failed" in message:
                kind = EXCEPTION.search(message)
                failed_by[kind.group(1) if kind else "other"] += 1
    return {
        "source": "daemon log okto-neuron-serve.log of this run's isolated daemon ('litellm usage ...' and 'litellm completion failed ...' lines)",
        "models": sorted(models), "successful_model_calls": sum(calls.values()), "calls_by_step": dict(calls),
        "prompt_tokens": prompt, "completion_tokens": completion, "failed_model_calls": sum(failed_by.values()),
        "failed_by_exception": dict(failed_by), "log_first_ts": first, "log_last_ts": last, "log_levels": dict(levels),
        "note": "tokens only: not converted to dollars. In a full run the failed calls are the scripted step 9 outage (invalid key).",
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--log", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    result = summarize(args.log)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print("%d successful calls, %d failed, %d prompt and %d completion tokens" % (
        result["successful_model_calls"], result["failed_model_calls"], result["prompt_tokens"], result["completion_tokens"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
