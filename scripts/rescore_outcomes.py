#!/usr/bin/env python3
"""Re-run the executable outcome check on every recorded Builder tree, rebuilt from the run's own diffs.

A run records `diffs/stepN.diff`, the `git diff` of the code after each Builder step against the starting app. This script
rebuilds that tree (the starting app/ of this repository plus the diff), runs scenarios/checks/outcome.check.ts on it with
the same edit window the live run used, and writes `code-outcome/rescore-stepN.json`. It then compares the outcomes with the
ones the live run recorded in `code-outcome/stepN.json`.

Why: it shows that the scored numbers can be reproduced from the recorded files alone (the live trees are deleted after a run),
and the rescored files carry `failure_details` (what the check saw, for example "Received: 500"), which runs recorded before
that field existed do not have. The scorer reads the live files, not these.

  python3 scripts/rescore_outcomes.py                    every run under runs/
  python3 scripts/rescore_outcomes.py --runs-dir DIR --arm notes

Needs Node 22 and `cd app && npm ci` (see scripts/code_outcome.py).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_workdir  # noqa: E402
import code_outcome  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDIT_WINDOW_AT_STEP = {3: 15, 5: 30, 6: 30, 8: 30}


def rebuild(diff_path: str, repo: str = REPO) -> str:
    """A temporary canonical tree: the starting app/ plus the recorded diff. The caller deletes it."""
    root = tempfile.mkdtemp(prefix="neuron-demo-rescore-")
    build_workdir.copy_tree(os.path.join(repo, "app"), os.path.join(root, "app"), build_workdir.APP_EXCLUDE)
    if os.path.getsize(diff_path):
        done = subprocess.run(["git", "apply", "--whitespace=nowarn", os.path.abspath(diff_path)], cwd=root, capture_output=True, text=True)
        if done.returncode != 0:
            shutil.rmtree(root, ignore_errors=True)
            raise RuntimeError("could not apply %s: %s" % (diff_path, done.stderr.strip()[:300]))
    return root


def rescore_run(run_dir: str) -> List[dict]:
    rows = []
    for number, window in sorted(EDIT_WINDOW_AT_STEP.items()):
        diff = os.path.join(run_dir, "diffs", "step%d.diff" % number)
        if not os.path.isfile(diff):
            continue
        root = rebuild(diff)
        try:
            record = code_outcome.run(root, run_dir, "rescore-step%d" % number, window)
        finally:
            shutil.rmtree(root, ignore_errors=True)
        live_path = os.path.join(run_dir, "code-outcome", "step%d.json" % number)
        live = None
        if os.path.isfile(live_path):
            with open(live_path) as handle:
                live = json.load(handle)["outcomes"]
        record["live_outcomes"] = live
        record["matches_live"] = (live == record["outcomes"]) if live is not None else None
        path = os.path.join(run_dir, "code-outcome", "rescore-step%d.json" % number)
        with open(path, "w") as handle:
            json.dump(record, handle, indent=2)
            handle.write("\n")
        rows.append({"run": run_dir, "step": number, "matches_live": record["matches_live"], "outcomes": record["outcomes"], "live": live})
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs-dir", default=os.path.join(REPO, "runs"))
    parser.add_argument("--arm", action="append", help="only this arm (repeatable)")
    args = parser.parse_args(argv)
    total = mismatched = 0
    for arm in sorted(os.listdir(args.runs_dir)):
        arm_dir = os.path.join(args.runs_dir, arm)
        if not os.path.isdir(arm_dir) or arm == "negative" or (args.arm and arm not in args.arm):
            continue
        for run_id in sorted(os.listdir(arm_dir)):
            run_dir = os.path.join(arm_dir, run_id)
            if not os.path.isdir(os.path.join(run_dir, "diffs")):
                continue
            for row in rescore_run(run_dir):
                total += 1
                if row["matches_live"] is False:
                    mismatched += 1
                    print("DIFFERS %s/%s step %d: live %s, rescored %s" % (arm, run_id, row["step"], row["live"], row["outcomes"]))
    print("rescored %d tree(s); %d differ from the live result" % (total, mismatched))
    return 1 if mismatched else 0


if __name__ == "__main__":
    sys.exit(main())
