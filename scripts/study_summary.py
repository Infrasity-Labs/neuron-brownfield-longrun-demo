#!/usr/bin/env python3
"""Summarise every recorded run per arm and render the tables that README.md and docs/METRIC.md embed.

Everything here is read from files a run wrote (run-manifest.json, code-outcome/, probes/, closeout-result.json,
labels/). Nothing is estimated. The alignment numbers come from scripts/score_runs.py, so a product that needs a hand
label and has none is left out, exactly as docs/METRIC.md says; the tables state how many products that leaves.

  python3 scripts/study_summary.py                          print the tables
  python3 scripts/study_summary.py --out runs/study-summary.json
  python3 scripts/study_summary.py --write README.md        replace the blocks between the study markers
  python3 scripts/study_summary.py --check README.md        exit 1 when a block differs from what the runs give
                                                            (scripts/check_readme.py does this)

A block in a document sits between `<!-- BEGIN study-<name> -->` and `<!-- END study-<name> -->` (names in BLOCKS). It is
generated: edit the runs or this script, not the block.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import statistics
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_transcripts  # noqa: E402
import score_runs  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARMS = [("none", "A, no memory"), ("notes", "B, notes in the prompt"), ("neuron", "C, Neuron")]
OUTCOME_STEPS = ["step3", "step5", "step6"]
PROBES = [("step4", "edit window, after step 4"), ("step7", "error response, after step 7")]


def _load(path: str) -> Optional[dict]:
    if not os.path.isfile(path):
        return None
    with open(path) as handle:
        return json.load(handle)


def _parse(ts: Optional[str]) -> Optional[datetime.datetime]:
    if not ts:
        return None
    return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ")


def spread(values: List[float], digits: int = 3) -> dict:
    if not values:
        return {"n": 0, "mean": None, "stdev": None, "min": None, "max": None}
    return {"n": len(values), "mean": round(statistics.mean(values), digits),
            "stdev": round(statistics.stdev(values), digits) if len(values) >= 2 else None,
            "min": round(min(values), digits), "max": round(max(values), digits)}


def run_facts(run_dir: str) -> dict:
    manifest = _load(os.path.join(run_dir, "run-manifest.json")) or {}
    checks = manifest.get("checks") or {}
    started, finished = _parse(manifest.get("started_at")), _parse(manifest.get("finished_at"))
    sessions = manifest.get("sessions") or []
    outcomes = {}
    for label in OUTCOME_STEPS:
        record = _load(os.path.join(run_dir, "code-outcome", "%s.json" % label))
        outcomes[label] = (record or {}).get("outcomes")
    probes = {}
    for label, _text in PROBES:
        probes[label] = _load(os.path.join(run_dir, "probes", "%s.summary.json" % label))
    # The isolation numbers are recomputed from the recorded transcripts with the checker as it is now, not copied from the
    # manifest: the checker was corrected during the study (docs/VERIFIED.md), and a manifest keeps what the checker of the
    # day said. The manifest's own figure is kept as isolation_at_run_time.
    folder = os.path.join(run_dir, "transcripts")
    reports = [check_transcripts.check_transcript(os.path.join(folder, n)) for n in sorted(os.listdir(folder))] if os.path.isdir(folder) else []
    isolation = {"transcripts": len(reports), "violations": sum(len(r["violations"]) for r in reports),
                 "blocked_attempts": sum(len(r["blocked"]) for r in reports)}
    return {
        "run_id": os.path.basename(run_dir),
        "isolation_at_run_time": checks.get("isolation") or {},
        "complete": bool(manifest.get("finished_at")) and not (manifest.get("claude_flags") or {}).get("partial_run"),
        "hard_failures": checks.get("hard_failures") or [],
        "isolation": isolation,
        "spec_rule_values": checks.get("spec_rule_values") or [],
        "outcomes": outcomes,
        "rescore_step5": _load(os.path.join(run_dir, "code-outcome", "rescore-step5.json")),
        "probes": probes,
        "closeout": _load(os.path.join(run_dir, "closeout-result.json")),
        "wall_seconds": round((finished - started).total_seconds(), 1) if started and finished else None,
        "sessions": len(sessions),
        "session_cost_usd": round(sum(s.get("total_cost_usd") or 0 for s in sessions), 4),
        "session_seconds": round(sum((s.get("duration_ms") or 0) for s in sessions) / 1000.0, 1),
        "versions": manifest.get("versions") or {},
        "model": manifest.get("model"),
        "commit": (manifest.get("repo") or {}).get("commit"),
        "harness_sha256": ((manifest.get("repo") or {}).get("harness") or {}).get("sha256"),
    }


def summarize(runs_dir: str, labels_dir: str) -> dict:
    scored = score_runs.collect(runs_dir, labels_dir)
    arms: Dict[str, dict] = {}
    for arm, title in ARMS:
        arm_dir = os.path.join(runs_dir, arm)
        run_ids = sorted(d for d in os.listdir(arm_dir) if os.path.isfile(os.path.join(arm_dir, d, "run-manifest.json"))) \
            if os.path.isdir(arm_dir) else []
        facts = [run_facts(os.path.join(arm_dir, rid)) for rid in run_ids]
        arms[arm] = {"title": title, "runs": facts, "score": scored["arms"].get(arm)}
    return {"schema": "neuron-demo-study-summary/1", "arms": arms, "skipped": scored["skipped"],
            "metric_sha256": scored["metric_sha256"]}


# ---- rendering ---------------------------------------------------------------------------------------------------------


def _fmt(x: Optional[float], digits: int = 3) -> str:
    return "-" if x is None else ("%%.%df" % digits) % x


def _spread_cell(d: dict, digits: int = 3) -> str:
    if not d["n"]:
        return "none"
    return "mean %s, sd %s, min %s, max %s" % (_fmt(d["mean"], digits), _fmt(d["stdev"], digits), _fmt(d["min"], digits), _fmt(d["max"], digits))


def block_alignment(summary: dict) -> str:
    lines = ["| Arm | Runs recorded | Alignment, rules that change (n, spread) | Alignment, rule that does not change (n, spread) | Products scored per run | Hand labels |",
             "| --- | ------------- | ----------------------------------------- | ------------------------------------------------ | ----------------------- | ----------- |"]
    for arm, title in ARMS:
        data = summary["arms"][arm]
        score = data["score"]
        if not score:
            lines.append("| %s | %d | none | none | none | 0 of %d runs labeled |" % (title, len(data["runs"]), len(data["runs"])))
            continue
        labeled = sum(1 for r in score["runs"] if r["labeled"])
        per_run = ", ".join("%d of %d" % c for c in sorted({(r["scored"], r["of"]) for r in score["runs"]}))
        lines.append("| %s | %d | n=%d, %s | n=%d, %s | %s | %d of %d runs labeled |" % (
            title, len(data["runs"]), score["alignment_changed"]["n"], _spread_cell(score["alignment_changed"]),
            score["alignment_stable"]["n"], _spread_cell(score["alignment_stable"]), per_run, labeled, len(data["runs"])))
    return "\n".join(lines)


OUTCOME_COLUMNS = [("step3", "accepts-inside", "edit-window/accepts-inside"), ("step3", "refuses-outside", "edit-window/refuses-outside"),
                   ("step5", "accepts-inside", "edit-window/accepts-inside"), ("step5", "refuses-outside", "edit-window/refuses-outside"),
                   ("step6", "caps-above", "article-limit/caps-above"), ("step6", "keeps-below", "article-limit/keeps-below"),
                   ("step6", "keeps-default", "article-limit/keeps-default")]


def block_outcomes(summary: dict) -> str:
    header = "| Arm | Runs | " + " | ".join("step %s %s" % (label[-1], name) for label, name, _ in OUTCOME_COLUMNS) + " |"
    lines = [header, "| --- | ---- | " + " | ".join("---" for _ in OUTCOME_COLUMNS) + " |"]
    for arm, title in ARMS:
        facts = summary["arms"][arm]["runs"]
        cells = []
        for label, _name, outcome in OUTCOME_COLUMNS:
            states = [(f["outcomes"].get(label) or {}).get(outcome) for f in facts]
            passed = sum(1 for s in states if s == "pass")
            errored = sum(1 for s in states if s in ("error", None))
            cells.append("%d of %d%s" % (passed, len(facts), " (%d not run)" % errored if errored else ""))
        lines.append("| %s | %d | %s |" % (title, len(facts), " | ".join(cells)))
    return "\n".join(lines)


def refusal_kind(facts: dict) -> str:
    """How one run's step 5 code treated an edit made one minute outside the 30 minute window, from the rescored check."""
    record = facts.get("rescore_step5")
    if not record:
        return "not rescored"
    outcomes = record.get("outcomes") or {}
    if outcomes.get("edit-window/refuses-outside") == "pass":
        return "refused with a 4xx"
    if outcomes.get("edit-window/refuses-outside") != "fail":
        return "not run"
    detail = (record.get("failure_details") or {}).get("edit-window/refuses-outside", "")
    status = re.search(r"Received:\s*(\d+)", detail)
    if not status:
        return "failed, status unknown"
    return "refused with a 5xx (an unhandled error)" if int(status.group(1)) >= 500 else "did not refuse (status %s)" % status.group(1)


def block_refusal(summary: dict) -> str:
    kinds = ["refused with a 4xx", "refused with a 5xx (an unhandled error)", "did not refuse (status 200)"]
    lines = ["| Arm | Runs | Step 5 code accepts minute 29 | Edit at minute 31: refused with a 4xx (counts as aligned) | refused with a 5xx (an unhandled error; does not count) | not refused, the edit went through | other |",
             "| --- | ---- | ----------------------------- | ---------------------------------------------------------- | -------------------------------------------------------- | ---------------------------------- | ----- |"]
    for arm, title in ARMS:
        facts = summary["arms"][arm]["runs"]
        got = [refusal_kind(f) for f in facts]
        accepts = sum(1 for f in facts if ((f.get("rescore_step5") or {}).get("outcomes") or {}).get("edit-window/accepts-inside") == "pass")
        counted = [sum(1 for k in got if k == kind) for kind in kinds]
        other = len(got) - sum(counted)
        lines.append("| %s | %d | %d of %d | %d | %d | %d | %d |" % (title, len(facts), accepts, len(facts), counted[0], counted[1], counted[2], other))
    return "\n".join(lines)


def block_conduct(summary: dict) -> str:
    lines = ["| Arm | Runs | Role sessions | Sessions that reached a note, plan or outside path | Blocked attempts | Runs whose specs carry a rule value | Hard failures | Cost in USD per run | Wall time per run (s) |",
             "| --- | ---- | ------------- | -------------------------------------------------- | ---------------- | ----------------------------------- | ------------- | ------------------- | -------------------- |"]
    for arm, title in ARMS:
        facts = summary["arms"][arm]["runs"]
        sessions = sum(f["sessions"] for f in facts)
        violations = sum((f["isolation"] or {}).get("violations", 0) for f in facts)
        blocked = sum((f["isolation"] or {}).get("blocked_attempts", 0) for f in facts)
        with_values = sum(1 for f in facts if f["spec_rule_values"])
        hard = sum(len(f["hard_failures"]) for f in facts)
        cost = spread([f["session_cost_usd"] for f in facts], 3)
        wall = spread([f["wall_seconds"] for f in facts if f["wall_seconds"] is not None], 0)
        lines.append("| %s | %d | %d | %d | %d | %d of %d | %d | %s | %s |" % (
            title, len(facts), sessions, violations, blocked, with_values, len(facts), hard,
            _spread_cell(cost, 3), _spread_cell(wall, 0)))
    return "\n".join(lines)


def block_probes(summary: dict) -> str:
    facts = summary["arms"]["neuron"]["runs"]
    lines = ["| Neuron's own state right after the edit was ingested | Runs probed | Answer gives the new value | Answer gives the replaced value | `explore` result has the new value | `explore` result has the replaced value | Word \"supersed\" in either result |",
             "| ---------------------------------------------------- | ----------- | -------------------------- | ------------------------------- | ---------------------------------- | ---------------------------------------- | -------------------------------- |"]
    for label, text in PROBES:
        probed = [f["probes"][label] for f in facts if f["probes"].get(label)]

        def count(key: str) -> str:
            return "%d of %d" % (sum(1 for p in probed if p.get(key)), len(probed))
        lines.append("| %s | %d | %s | %s | %s | %s | %s |" % (
            text, len(probed), count("ask_text_matches_new"), count("ask_text_matches_old"), count("explore_matches_new"),
            count("explore_matches_old"), count("supersedes_marker_seen")))
    return "\n".join(lines)


def block_citations(summary: dict) -> str:
    facts = [f for f in summary["arms"]["neuron"]["runs"] if f["closeout"]]
    lines = ["| Neuron arm | Questions | Sources and a non-empty answer | Citations passing the hash check (record time) | Stale anchors | Other citation failures | Answers still giving a replaced value after its edit | `provider_error` answers (step 9) | of which the agent claimed nothing was found |",
             "| ---------- | --------- | ------------------------------ | ---------------------------------------------- | ------------- | ----------------------- | ----------------------------------------------------- | --------------------------------- | ------------------------------------------- |"]

    def row(label: str, group: List[dict]) -> str:
        def total(key: str) -> int:
            return sum(f["closeout"][key] for f in group)

        def length(key: str) -> int:
            return sum(len(f["closeout"].get(key) or []) for f in group)
        claimed = sum(1 for f in group for p in (f["closeout"].get("provider_error_answers") or []) if p.get("claimed_nothing_found"))
        return "| %s | %d | %d | %d of %d | %d | %d | %d | %d | %d |" % (
            label, total("questions_asked"), total("questions_with_sources_and_answer"), total("citations_passed_at_record_time"),
            total("citations_checked_at_record_time"), total("stale_anchor_failures"), total("other_citation_failures"),
            length("stale_rule_answers_after_replacement"), length("provider_error_answers"), claimed)
    for f in facts:
        lines.append(row(f["run_id"], [f]))
    if facts:
        lines.append(row("all %d runs" % len(facts), facts))
    return "\n".join(lines)


BLOCKS = {
    "study-alignment": block_alignment,
    "study-outcomes": block_outcomes,
    "study-refusal": block_refusal,
    "study-conduct": block_conduct,
    "study-probes": block_probes,
    "study-citations": block_citations,
}


def marker(name: str, begin: bool) -> str:
    return "<!-- %s %s -->" % ("BEGIN" if begin else "END", name)


def render(summary: dict) -> Dict[str, str]:
    return {name: fn(summary) for name, fn in BLOCKS.items()}


def _pattern(name: str) -> "re.Pattern[str]":
    return re.compile(re.escape(marker(name, True)) + r"\n(.*?)\n" + re.escape(marker(name, False)), re.S)


def block_in(text: str, name: str) -> Optional[str]:
    match = _pattern(name).search(text)
    return match.group(1) if match else None


def replace_block(text: str, name: str, body: str) -> str:
    return _pattern(name).sub(lambda _m: marker(name, True) + "\n" + body + "\n" + marker(name, False), text, count=1)


def check_text(text: str, summary: dict) -> List[str]:
    """Differences between the generated blocks and the blocks present in `text` (a block that is absent is not an error)."""
    problems = []
    for name, body in render(summary).items():
        present = block_in(text, name)
        if present is not None and present != body:
            problems.append("the %s block differs from what the recorded runs give; run scripts/study_summary.py --write" % name)
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs-dir", default=os.path.join(REPO, "runs"))
    parser.add_argument("--labels-dir", default=os.path.join(REPO, "labels"))
    parser.add_argument("--out")
    parser.add_argument("--write", nargs="+", metavar="FILE", help="replace the study blocks in these documents")
    parser.add_argument("--check", nargs="+", metavar="FILE")
    args = parser.parse_args(argv)
    summary = summarize(args.runs_dir, args.labels_dir)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as handle:
            json.dump(summary, handle, indent=2)
            handle.write("\n")
    status = 0
    for path in args.write or []:
        with open(path) as handle:
            text = handle.read()
        for name, body in render(summary).items():
            if block_in(text, name) is not None:
                text = replace_block(text, name, body)
        with open(path, "w") as handle:
            handle.write(text)
    for path in args.check or []:
        with open(path) as handle:
            for problem in check_text(handle.read(), summary):
                print("%s: %s" % (path, problem))
                status = 1
    if not (args.write or args.check or args.out):
        for name, body in render(summary).items():
            print("## %s\n\n%s\n" % (name, body))
    return status


if __name__ == "__main__":
    sys.exit(main())
