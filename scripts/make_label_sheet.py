#!/usr/bin/env python3
"""Write an EMPTY label sheet for one recorded run. Never fills a value and never overwrites an existing sheet.

  python3 scripts/make_label_sheet.py runs/neuron/run-01

The sheet goes to labels/<arm>/<run-id>.json with `value: null` for every label product, the labeler and time
empty, and a pointer to what to read for each product. The format is described in labels/README.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metric  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_sheet(run_dir: str, labels_dir: str) -> str:
    run_dir = os.path.abspath(run_dir)
    run_id = os.path.basename(run_dir)
    arm = os.path.basename(os.path.dirname(run_dir))
    target = os.path.join(labels_dir, arm, "%s.json" % run_id)
    if os.path.exists(target):
        raise FileExistsError("%s already exists; sheets are never overwritten" % target)
    spec = metric.load_products()
    labels = {}
    for product in spec["products"]:
        if product["kind"] != "label":
            continue
        labels[product["id"]] = {
            "value": None,
            "evidence": "",
            "note": "",
            "read": "transcripts/step%02d-%s.jsonl and the diff in diffs/step%d.diff; %s" % (
                product["step"], product["role"], product["step"], product["description"]),
        }
    sheet = {"schema": "neuron-demo-labels/1", "arm": arm, "run_id": run_id, "labeler": "", "labeled_at": "",
             "blind": None, "labels": labels}
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w") as handle:
        json.dump(sheet, handle, indent=2)
        handle.write("\n")
    return target


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir")
    parser.add_argument("--labels-dir", default=os.path.join(REPO, "labels"))
    args = parser.parse_args(argv)
    print("wrote empty sheet: %s" % make_sheet(args.run_dir, args.labels_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
