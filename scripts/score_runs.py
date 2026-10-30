#!/usr/bin/env python3
"""Score recorded runs with the written metric (docs/METRIC.md) and report mean, spread and n per arm.

Reads runs/<arm>/<run-id>/ (the run directory written by run_demo.py) and labels/<arm>/<run-id>.json (a named
human's labels). Nothing is estimated: a product with no label and no executable result is left out and counted.

  python3 scripts/score_runs.py                      all runs under runs/
  python3 scripts/score_runs.py --runs-dir DIR --labels-dir DIR --out results/summary.json

With no recorded runs it says so and exits 0. With fewer than 5 runs in an arm it prints that no comparison is
supported for that arm.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metric  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_RUNS = 5
ARM_ORDER = ["none", "notes", "neuron"]


def _load(path: str) -> Optional[dict]:
    if not os.path.isfile(path):
        return None
    with open(path) as handle:
        return json.load(handle)


def validate_labels(labels: dict, arm: str, run_id: str) -> List[str]:
    problems = []
    if labels.get("schema") != "neuron-demo-labels/1":
        problems.append("schema is not neuron-demo-labels/1")
    if not str(labels.get("labeler") or "").strip():
        problems.append("labeler is empty: a label sheet must name who labeled")
    if not str(labels.get("labeled_at") or "").endswith("Z"):
        problems.append("labeled_at must be a UTC time ending in Z")
    if labels.get("arm") != arm or labels.get("run_id") != run_id:
        problems.append("arm or run_id does not match the file location")
    known = set(metric.product_ids("label"))
    for key, entry in (labels.get("labels") or {}).items():
        if key.startswith("private-leak/"):
            continue
        if key not in known:
            problems.append("unknown product %s" % key)
        elif entry.get("value") not in (0, 1, None):
            problems.append("%s: value must be 0, 1 or null" % key)
    return problems


def exec_value(spec: dict, run_dir: str) -> Optional[int]:
    record = _load(os.path.join(run_dir, "code-outcome", "%s.json" % spec["label"]))
    if not record:
        return None
    outcomes = record.get("outcomes", {})
    statuses = [outcomes.get(o) for o in spec["outcomes"]]
    if any(s is None or s == "error" for s in statuses):
        return None
    return 1 if all(s == "pass" for s in statuses) else 0


def score_run(run_dir: str, labels: Optional[dict]) -> dict:
    spec = metric.load_products()
    values: Dict[str, Optional[int]] = {}
    for product in spec["products"]:
        if product["kind"] == "exec":
            values[product["id"]] = exec_value(spec["exec_checks"][product["id"]], run_dir)
        else:
            entry = ((labels or {}).get("labels") or {}).get(product["id"]) or {}
            values[product["id"]] = entry.get("value")

    def fraction(selected: List[dict]) -> Optional[float]:
        scored = [values[p["id"]] for p in selected if values[p["id"]] is not None]
        return sum(scored) / len(scored) if scored else None

    changed = [p for p in spec["products"] if p["rule"] in spec["changed_rules"]]
    stable = [p for p in spec["products"] if p["rule"] in spec["stable_rules"]]
    roles = sorted({p["role"] for p in spec["products"]})
    return {
        "alignment_changed": fraction(changed),
        "alignment_stable": fraction(stable),
        "by_role": {role: fraction([p for p in changed if p["role"] == role]) for role in roles},
        "by_rule": {rule: fraction([p for p in spec["products"] if p["rule"] == rule]) for rule in spec["changed_rules"] + spec["stable_rules"]},
        "scored": sum(1 for v in values.values() if v is not None),
        "of": len(values),
        "products": values,
    }


def describe(values: List[float]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "stdev": None, "min": None, "max": None}
    return {"n": len(values), "mean": round(statistics.mean(values), 4),
            "stdev": round(statistics.stdev(values), 4) if len(values) >= 2 else None,
            "min": min(values), "max": max(values)}


def collect(runs_dir: str, labels_dir: str, allow_metric_change: bool = False) -> dict:
    current = metric.metric_fingerprint()
    accepted = metric.accepted_fingerprints()
    arms: Dict[str, dict] = {}
    skipped: List[dict] = []
    if not os.path.isdir(runs_dir):
        return {"arms": {}, "skipped": [], "metric_sha256": current}
    for arm in sorted(os.listdir(runs_dir)):
        arm_dir = os.path.join(runs_dir, arm)
        if not os.path.isdir(arm_dir):
            continue
        entry = {"runs": [], "changed": [], "stable": []}
        for run_id in sorted(os.listdir(arm_dir)):
            run_dir = os.path.join(arm_dir, run_id)
            manifest = _load(os.path.join(run_dir, "run-manifest.json"))
            if manifest is None:
                continue
            if not allow_metric_change and (manifest.get("metric") or {}).get("sha256") not in accepted:
                skipped.append({"arm": arm, "run_id": run_id, "reason": "recorded under a different metric definition"})
                continue
            labels = _load(os.path.join(labels_dir, arm, "%s.json" % run_id))
            if labels is not None:
                problems = validate_labels(labels, arm, run_id)
                if problems:
                    skipped.append({"arm": arm, "run_id": run_id, "reason": "labels rejected: " + "; ".join(problems)})
                    labels = None
            scored = score_run(run_dir, labels)
            scored["run_id"] = run_id
            scored["labeled"] = labels is not None
            entry["runs"].append(scored)
            if scored["alignment_changed"] is not None:
                entry["changed"].append(scored["alignment_changed"])
            if scored["alignment_stable"] is not None:
                entry["stable"].append(scored["alignment_stable"])
        if entry["runs"]:
            arms[arm] = {"runs": entry["runs"], "alignment_changed": describe(entry["changed"]),
                         "alignment_stable": describe(entry["stable"])}
    return {"arms": arms, "skipped": skipped, "metric_sha256": current}


def render(summary: dict) -> str:
    lines = []
    if not summary["arms"]:
        lines.append("no recorded runs to score")
    for arm in [a for a in ARM_ORDER if a in summary["arms"]] + [a for a in summary["arms"] if a not in ARM_ORDER]:
        data = summary["arms"][arm]
        lines.append("arm %s" % arm)
        for name in ("alignment_changed", "alignment_stable"):
            d = data[name]
            fmt = lambda x: "-" if x is None else "%.3f" % x
            lines.append("  %-18s n=%d mean=%s stdev=%s min=%s max=%s" % (
                name, d["n"], fmt(d["mean"]), fmt(d["stdev"]), fmt(d["min"]), fmt(d["max"])))
        for run in data["runs"]:
            lines.append("    %-10s scored %2d of %d  labeled=%s" % (run["run_id"], run["scored"], run["of"], run["labeled"]))
        if data["alignment_changed"]["n"] < MIN_RUNS:
            lines.append("  fewer than %d scored runs: no comparison is supported for this arm" % MIN_RUNS)
    for skip in summary["skipped"]:
        lines.append("skipped %s/%s: %s" % (skip["arm"], skip["run_id"], skip["reason"]))
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs-dir", default=os.path.join(REPO, "runs"))
    parser.add_argument("--labels-dir", default=os.path.join(REPO, "labels"))
    parser.add_argument("--out", help="write the summary as JSON")
    parser.add_argument("--allow-metric-change", action="store_true")
    args = parser.parse_args(argv)
    summary = collect(args.runs_dir, args.labels_dir, args.allow_metric_change)
    print(render(summary))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as handle:
            json.dump(summary, handle, indent=2)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
