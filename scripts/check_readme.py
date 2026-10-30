#!/usr/bin/env python3
"""Check that the numbers in README.md agree with the recorded files.

Every row of the pilot table in README.md ("The Pilot Run") is compared, cell for cell, with a value computed from
demo-state/closeout-result.json (and demo-state/curation-queue-team.json for the queue row). A row with a label this
script does not know fails, and so does a missing row. It also checks:

  * every "N starting notes" in README.md equals the number of start-state notes in vault/ (7 code summaries and 6 rules);
  * the pilot's recorded Reviewer verdicts named in the README's per-step table match the final report of each Reviewer
    transcript (Approved, Not approved, or no approval verdict);
  * the number of recorded asks and explore calls in the artifacts table equals the line count of the files;
  * README.md states no hard-coded unit test count (a count goes stale; the command is given instead);
  * every generated study block in README.md and docs/METRIC.md (scripts/study_summary.py) equals what the recorded runs under
    runs/ and labels/ give, and README.md has the alignment block as soon as any run is recorded.

  python3 scripts/check_readme.py            exit 1 and a list of differences when the README disagrees
  python3 scripts/check_readme.py --print    print the expected table to paste into the README
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS_ORDER = ("ok", "no_llm", "empty", "provider_error", "truncated", "abnormal_stop", "unparsed")
TABLE_HEADING = "## The Pilot Run"
VERDICT_HEADING = "### Pilot outcomes by step"
VERDICT_STEPS = {"4": "step04-reviewer", "5": "step05-reviewer", "6": "step06-reviewer", "8": "step08-reviewer"}


def _status_cell(counts: Dict[str, int]) -> str:
    present = ["`%s` %d" % (key, counts[key]) for key in STATUS_ORDER if counts.get(key)]
    return ", ".join(present) + ", all other values 0"


def expected_rows(result: dict, queue: dict) -> List[Tuple[str, str]]:
    stale_by_rule: Dict[str, int] = {}
    for item in result["stale_rule_answers_after_replacement"]:
        stale_by_rule[item["rule"]] = stale_by_rule.get(item["rule"], 0) + 1
    notes = result["stale_anchor_failures_by_note"]
    kinds: Dict[Tuple[str, str], int] = {}
    for item in queue["items"]:
        kinds[(item["kind"], item.get("reason"))] = kinds.get((item["kind"], item.get("reason")), 0) + 1
    ingest = next(i for i in result["ingest_seconds_per_note"] if i["label"].startswith("initial"))
    calls = re.search(r"(\d+) successful model calls, (\d+) failed", ingest["note"])
    provider = result["provider_error_answers"]
    return [
        ("Questions asked", str(result["questions_asked"])),
        ("Questions that returned sources and a non-empty answer", "%d of %d" % (result["questions_with_sources_and_answer"], result["questions_asked"])),
        ("Questions that returned a source list, with or without an answer", "%d of %d" % (result["questions_with_sources"], result["questions_asked"])),
        ("`synthesis_status` values", _status_cell(result["synthesis_status_counts"])),
        ("`finish_reason` other than `stop`", str(result["finish_reason_not_stop"])),
        ("Asks with no `finish_reason` at all", str(result["finish_reason_missing"])),
        ("Citations that passed the hash check",
         "%d of %d at record time, %d on a recheck at the end" % (result["citations_passed_at_record_time"],
                                                                result["citations_checked_at_record_time"],
                                                                result["citations_passed_on_recheck"])),
        ("Failed citations that are stale anchors",
         "%d (%s)" % (result["stale_anchor_failures"], ", ".join("%s %d" % (n, c) for n, c in notes.items()))),
        ("Failed citations of any other kind", str(result["other_citation_failures"])),
        ("Rules replaced by the Maintainer", "%d (%s)" % (len(result["claims_replaced"]), ", ".join(result["claims_replaced"]))),
        ("Answers still giving the replaced edit window after the edit", "%d (text match, a heuristic)" % stale_by_rule.get("edit-window", 0)),
        ("Answers still giving the replaced error rule after step 7", "%d (text match, a heuristic)" % stale_by_rule.get("error-response", 0)),
        ("`provider_error` answers", "%d; the agent claimed nothing was found: %s" % (
            len(provider), "yes" if any(p["claimed_nothing_found"] for p in provider) else "no")),
        ("`vault_override_ignored` naming the vault the connection was already pinned to", str(result["vault_override_ignored_same_vault_count"])),
        ("Asks to a vault other than `team` and `reviewer-private`", str(result["asks_to_vaults_other_than_the_two_demo_vaults"])),
        ("Private notes in `team` answers", "%d (checked against the author's private notes, which are not shipped)" % result["private_notes_in_team_answers"]),
        ("Ingest of the starting notes", "at most %d s, %s model calls, %s failed" % (ingest["seconds_upper_bound"], calls.group(1), calls.group(2))),
        ("Curation review queue after step 8", "%d (%d node candidates, %d relation items `queue_predicate`, %d relation items `queue_grounding`)" % (
            queue["count"], kinds.get(("node", "low_confidence"), 0), kinds.get(("relation", "queue_predicate"), 0),
            kinds.get(("relation", "queue_grounding"), 0))),
    ]


def table_after(text: str, heading: str) -> List[Tuple[str, str]]:
    """Rows (first cell, second cell) of the first markdown table after `heading`."""
    start = text.find(heading)
    if start < 0:
        return []
    rows: List[Tuple[str, str]] = []
    in_table = False
    for line in text[start + len(heading):].splitlines():
        if line.startswith("|"):
            in_table = True
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and not set(cells[0]) <= set("-: ") and cells[0] not in ("Measure", "Step"):
                rows.append((cells[0], cells[1]))
        elif in_table:
            break
    return rows


def pilot_verdict(transcript: str) -> str:
    text = ""
    with open(transcript) as handle:
        for line in handle:
            event = json.loads(line)
            if event.get("type") == "result":
                text = event.get("result") or ""
    if re.search(r"\bnot approved\b", text, re.I):
        return "Not approved"
    if re.search(r"\bapproved\b", text, re.I):
        return "Approved"
    return "No approval verdict"


def count_start_notes(repo: str = REPO) -> int:
    return len([n for n in os.listdir(os.path.join(repo, "vault")) if n.endswith(".md")])


def check(repo: str = REPO) -> List[str]:
    problems: List[str] = []
    with open(os.path.join(repo, "README.md")) as handle:
        readme = handle.read()
    with open(os.path.join(repo, "demo-state", "closeout-result.json")) as handle:
        result = json.load(handle)
    with open(os.path.join(repo, "demo-state", "curation-queue-team.json")) as handle:
        queue = json.load(handle)

    expected = expected_rows(result, queue)
    actual = table_after(readme, TABLE_HEADING)
    if not actual:
        problems.append("README.md has no table under %r" % TABLE_HEADING)
    actual_map = dict(actual)
    for label, cell in expected:
        if label not in actual_map:
            problems.append("README row missing: %s" % label)
        elif actual_map[label] != cell:
            problems.append("README row %r says %r but the recorded files give %r" % (label, actual_map[label], cell))
    known = {label for label, _ in expected}
    for label, _cell in actual:
        if label not in known:
            problems.append("README row %r is not checked by scripts/check_readme.py: add it there or remove it" % label)

    verdicts = dict(table_after(readme, VERDICT_HEADING))
    for step, name in VERDICT_STEPS.items():
        label = "%s Reviewer" % step
        want = pilot_verdict(os.path.join(repo, "demo-state", "transcripts", name + ".jsonl"))
        cell = verdicts.get(label)
        if cell is None:
            problems.append("README per-step table has no row %r" % label)
        elif not cell.startswith(want):
            problems.append("README row %r says %r but the recorded Reviewer report gives %r" % (label, cell, want))

    def lines(path: str) -> int:
        with open(os.path.join(repo, path)) as handle:
            return sum(1 for line in handle if line.strip())

    for pattern, path, what in ((r"Pilot, (\d+) asks", "demo-state/asks.jsonl", "asks"),
                                (r"Pilot, (\d+) calls", "demo-state/explores.jsonl", "explore calls")):
        found = re.search(pattern, readme)
        if not found:
            problems.append("README artifacts table does not state the number of recorded %s" % what)
        elif int(found.group(1)) != lines(path):
            problems.append("README says %s recorded %s but %s has %d" % (found.group(1), what, path, lines(path)))

    notes = count_start_notes(repo)
    for found in re.findall(r"(\d+) starting notes", readme):
        if int(found) != notes:
            problems.append("README says %s starting notes but vault/ holds %d" % (found, notes))
    if not re.search(r"\b%d starting notes\b" % notes, readme):
        problems.append("README never states the starting note count (%d)" % notes)
    if re.search(r"\b\d+ (?:unit )?tests\b", readme):
        problems.append("README hard-codes a unit test count: give the command instead, a count goes stale")

    # The study tables are generated from runs/ by scripts/study_summary.py; a table that differs from the runs fails.
    import study_summary
    summary = study_summary.summarize(os.path.join(repo, "runs"), os.path.join(repo, "labels"))
    for rel in ("README.md", os.path.join("docs", "METRIC.md")):
        if not os.path.isfile(os.path.join(repo, rel)):
            continue
        with open(os.path.join(repo, rel)) as handle:
            text = handle.read()
        problems.extend("%s: %s" % (rel, p) for p in study_summary.check_text(text, summary))
    if any(summary["arms"][arm]["runs"] for arm in summary["arms"]) and study_summary.block_in(readme, "study-alignment") is None:
        problems.append("runs are recorded but README.md has no study-alignment block")
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--print", action="store_true", help="print the expected pilot table")
    args = parser.parse_args(argv)
    if args.print:
        with open(os.path.join(REPO, "demo-state", "closeout-result.json")) as handle:
            result = json.load(handle)
        with open(os.path.join(REPO, "demo-state", "curation-queue-team.json")) as handle:
            queue = json.load(handle)
        print("| Measure | Result |\n| ------- | ------ |")
        for label, cell in expected_rows(result, queue):
            print("| %s | %s |" % (label, cell))
        return 0
    problems = check()
    for problem in problems:
        print("MISMATCH: " + problem)
    print("README check: %d problem(s)" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
