#!/usr/bin/env python3
"""Run the executable outcome checks on the Builder's code and record the result.

The checks (scenarios/checks/outcome.check.ts) drive the real Express router with the database mocked:

  edit-window/accepts-inside    an edit made 1 minute inside the current window succeeds (200 or 201)
  edit-window/refuses-outside   an edit made 1 minute outside the window is refused with a 4xx
                                (with a 30 minute window: refuses minute 31, accepts minute 29)
  article-limit/caps-above      GET /api/articles?limit=51 reads at most 50 rows
  article-limit/keeps-below     ?limit=20 reads 20 rows
  article-limit/keeps-default   no limit reads 10 rows

The check file is copied into a temporary copy of the run's app/ tree, never into app/ of this repository and never
into the tree a role works in. A role that sees the check could write to it. Needs Node and the app's
node_modules (`cd app && npm ci`); without them the script stops with an error instead of reporting a pass.

  python3 scripts/code_outcome.py --canonical /tmp/run/canonical --run-dir runs/neuron/run-01 --label step5 --edit-window 30

Node version: the app's dependencies (buffer-equal-constant-time, through jsonwebtoken) use `SlowBuffer`, which Node 25
removed, so on Node 25 or later the suite fails to run ("Cannot read properties of undefined (reading 'prototype')")
and every outcome is "error". Use the Node 22 the pins name (pins.json, node.integration_workflow). `suite_failure` in
the record keeps jest's message when this happens.

Status: parsing is unit-tested on synthetic jest output (tests/test_code_outcome.py). Run live on 2026-10-30, see
docs/VERIFIED.md.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_workdir  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK_SOURCE = os.path.join(REPO, "scenarios", "checks", "outcome.check.ts")

# The app's own jest config with ts-jest type diagnostics turned off, used only for the outcome check. Why: the Prisma client in
# the shared node_modules is generated from the UNMODIFIED schema, so a Builder that adds a column (editedAt, deletedAt) gets a
# type error from ts-jest ("'editedAt' does not exist in type ...") and the whole suite fails to run, which says nothing about the
# behaviour. The database is mocked here, so the generated types do not matter at run time. Found in a live run (2026-10-30):
# with the app's own config every outcome of every Builder who touched schema.prisma was "error". The metric scores behaviour,
# not whether the code type-checks.
OUTCOME_JEST_CONFIG = """module.exports = {
  displayName: 'api-outcome',
  preset: './jest.preset.js',
  testEnvironment: 'node',
  transform: { '^.+\\\\.[tj]s$': ['ts-jest', { tsconfig: '<rootDir>/tsconfig.spec.json', diagnostics: false }] },
  moduleFileExtensions: ['ts', 'js', 'html'],
  testMatch: ['<rootDir>/src/tests/outcome/*.test.ts'],
};
"""

# jest test title prefix -> outcome id. Titles in outcome.check.ts look like "edit-window: accepts an edit ...".
TITLES: List[tuple] = [
    ("edit-window: accepts", "edit-window/accepts-inside"),
    ("edit-window: refuses", "edit-window/refuses-outside"),
    ("article-limit: caps", "article-limit/caps-above"),
    ("article-limit: keeps a limit", "article-limit/keeps-below"),
    ("article-limit: keeps the default", "article-limit/keeps-default"),
]
OUTCOME_IDS = [outcome for _prefix, outcome in TITLES]


def parse_jest(report: dict) -> Dict[str, str]:
    """Map a jest --json report to {outcome id: pass | fail | error}. A suite that did not run is error for every id."""
    outcomes = {outcome: "error" for outcome in OUTCOME_IDS}
    results = report.get("testResults") or []
    for suite in results:
        for assertion in suite.get("assertionResults") or []:
            title = assertion.get("title", "")
            for prefix, outcome in TITLES:
                if title.startswith(prefix):
                    outcomes[outcome] = "pass" if assertion.get("status") == "passed" else "fail"
    return outcomes


def parse_failures(report: dict) -> Dict[str, str]:
    """{outcome id: first line of jest's failure message} for every check that failed. A diagnostic, never a score: it keeps what
    the check saw (for example "Received: 500") so that a person can tell a missing window from a refusal with the wrong status."""
    details: Dict[str, str] = {}
    for suite in report.get("testResults") or []:
        for assertion in suite.get("assertionResults") or []:
            if assertion.get("status") == "passed" or not assertion.get("failureMessages"):
                continue
            for prefix, outcome in TITLES:
                if assertion.get("title", "").startswith(prefix):
                    text = re.sub(r"\x1b\[[0-9;]*m", "", assertion["failureMessages"][0])
                    lines = [" ".join(line.split()) for line in text.splitlines() if re.match(r"\s*(Expected|Received)\b", line)]
                    details[outcome] = " | ".join(lines)[:300] or " ".join(text.split())[:300]
    return details


def run(canonical: str, run_dir: str, label: str, edit_window: int, article_cap: int = 50,
        node_modules: str = os.path.join(REPO, "app", "node_modules")) -> dict:
    if not os.path.isdir(node_modules):
        raise RuntimeError("app dependencies are missing: run `cd app && npm ci` first (%s not found)" % node_modules)
    if shutil.which("npx") is None:
        raise RuntimeError("npx not found: Node is needed to run the outcome checks")
    work = tempfile.mkdtemp(prefix="neuron-demo-outcome-")
    try:
        app = os.path.join(work, "app")
        build_workdir.copy_tree(os.path.join(canonical, "app"), app, build_workdir.APP_EXCLUDE)
        os.symlink(node_modules, os.path.join(app, "node_modules"))
        target = os.path.join(app, "src", "tests", "outcome")
        os.makedirs(target)
        shutil.copyfile(CHECK_SOURCE, os.path.join(target, "outcome.test.ts"))
        with open(os.path.join(app, "jest.outcome.config.js"), "w") as handle:
            handle.write(OUTCOME_JEST_CONFIG)
        report_path = os.path.join(work, "jest.json")
        env = dict(os.environ, EDIT_WINDOW_MINUTES=str(edit_window), ARTICLE_LIMIT_CAP=str(article_cap), CI="true")
        proc = subprocess.run(["npx", "jest", "--config", "jest.outcome.config.js", "--runTestsByPath",
                               "src/tests/outcome/outcome.test.ts", "--json", "--outputFile=" + report_path],
                              cwd=app, env=env, capture_output=True, text=True)
        report = {}
        if os.path.isfile(report_path):
            with open(report_path) as handle:
                report = json.load(handle)
        outcomes = parse_jest(report)
        record = {"label": label, "edit_window_minutes": edit_window, "article_limit_cap": article_cap,
                  "jest_exit_code": proc.returncode, "outcomes": outcomes}
        if proc.returncode != 0 and not report:
            record["stderr_tail"] = proc.stderr[-800:]
        # A suite that failed to run (an import error, a type error, a Node version the app's dependencies do not
        # support) leaves every outcome at "error". Keep jest's own message so the cause is in the record.
        failed_suites = [suite.get("message", "") for suite in report.get("testResults") or []
                         if suite.get("status") == "failed" and not suite.get("assertionResults")]
        failures = parse_failures(report)
        if failures:
            record["failure_details"] = failures
        if failed_suites:
            record["suite_failure"] = failed_suites[0][:1200]
    finally:
        shutil.rmtree(work, ignore_errors=True)
    folder = os.path.join(run_dir, "code-outcome")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "%s.json" % label), "w") as handle:
        json.dump(record, handle, indent=2)
        handle.write("\n")
    return record


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--canonical", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--edit-window", type=int, required=True, help="minutes: 15 before the Maintainer's edit, 30 after")
    parser.add_argument("--article-cap", type=int, default=50)
    args = parser.parse_args(argv)
    record = run(args.canonical, args.run_dir, args.label, args.edit_window, args.article_cap)
    for outcome, status in record["outcomes"].items():
        print("%-6s %s" % (status.upper(), outcome))
    return 0 if all(v == "pass" for v in record["outcomes"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
