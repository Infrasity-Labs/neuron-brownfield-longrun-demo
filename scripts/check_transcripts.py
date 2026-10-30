#!/usr/bin/env python3
"""Fail when a role's transcript shows it reaching a note, a plan document or anything outside its workdir.

A role may get a rule only from its arm's rule source (Neuron, the notes pasted into its prompt, or nothing).
It must not read the Maintainer's notes, the plan, the docs or the recorded results with Read, Grep, Glob, git
or a shell command. This script reads Claude Code stream-json transcripts and reports every tool call that did.

What counts as reaching:
  * Read, Grep, Glob, Edit, Write, MultiEdit, NotebookEdit with a path, glob or file name whose first component
    (relative to the session's working directory) is one of FORBIDDEN_TOP, or whose absolute path is outside
    the working directory;
  * a Bash command that names a forbidden path, or runs git with -C or --git-dir;
  * a Grep or Glob RESULT that lists a forbidden path (this is how the plan document was found in the pilot:
    the Grep that found it named no path, its result did).

A call counts as a VIOLATION only when it succeeded: the matching tool_result exists, is not an error, and no
permission_denied event names the call. A denied or failed attempt is listed as BLOCKED. Blocked attempts do not
fail the check unless --strict is given, because the allow-list did its job, but they are recorded.

  python3 scripts/check_transcripts.py demo-state/transcripts/*.jsonl       exit 1 if any violation
  python3 scripts/check_transcripts.py runs/neuron/run-01/transcripts/*.jsonl --strict

The pilot transcripts in demo-state/transcripts/ were recorded before roles ran in clean workdirs. They fail
this check, and that is a finding about the pilot, not something to fix here: see demo-state/README.md.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from typing import Dict, Iterator, List, Optional, Tuple

# Top-level names that must never be reachable from a role's working directory.
FORBIDDEN_TOP = {
    "vault", "vault-private", "docs", "demo-state", "scenarios", "agents", "labels", "runs", "results",
    "scripts", "tests", "PLAN.md", "README.md", "pins.json", "run_demo.py", "THIRD_PARTY_NOTICES.md",
    ".env", ".env.example", ".mcp.json.example", ".okto-neuron-vault", "docker-compose.yml",
}
# Names a shell command or a git revision path must not mention (directory names only, to keep it precise).
FORBIDDEN_IN_COMMAND = ["vault-private", "vault", "docs", "demo-state", "scenarios", "agents", "labels", "runs", "PLAN.md"]

PATH_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Grep", "Glob"}
PATH_FIELDS = ("file_path", "path", "notebook_path", "glob", "pattern")
# A forbidden name counts where it starts a path: at the start of a word, or right after ./ or ../ . A name that follows a
# directory of the role's own tree (app/docs, app/node_modules/vault) is inside the working directory and reaches nothing.
COMMAND_RE = re.compile(r"(?:^|[\s'\"=:@]|\./|\.\./)(%s)(?=[/\s'\"]|$)" % "|".join(re.escape(n) for n in FORBIDDEN_IN_COMMAND))
RESULT_PATH_RE = re.compile(r"^(?P<path>[^\s:][^:]*?)(?::\d+(?::|-).*)?$")


def _events(path: str) -> Iterator[dict]:
    with open(path) as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def _blocks(event: dict) -> Iterator[dict]:
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                yield block


def _result_text(block: dict) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def relativize(path: str, cwd: Optional[str]) -> Tuple[str, bool]:
    """(path relative to cwd, outside) for a path a tool was given. `outside` is true for an absolute path elsewhere."""
    path = path.strip()
    if not path:
        return "", False
    if os.path.isabs(path) or re.match(r"^<[A-Z]+>/", path):
        if cwd and (path == cwd or path.startswith(cwd.rstrip("/") + "/")):
            return os.path.relpath(path, cwd), False
        return path, True
    return os.path.normpath(path), False


def path_problem(raw: str, cwd: Optional[str]) -> Optional[str]:
    """Why a path (or glob) reaches outside the allowed area, or None."""
    if not raw or raw == ".":
        return None
    rel, outside = relativize(raw, cwd)
    if "node_modules" in rel.split("/"):
        return None
    if outside or rel == ".." or rel.startswith("../"):
        return "outside the working directory: %s" % raw
    parts = [p for p in rel.split("/") if p and p != "."]
    if parts and parts[0] in FORBIDDEN_TOP:
        return "note, plan or harness path: %s" % raw
    for part in parts:
        if part in FORBIDDEN_IN_COMMAND:
            return "note, plan or harness path: %s" % raw
    return None


def command_problem(command: str, cwd: Optional[str]) -> Optional[str]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    if "git" in tokens:
        for index, token in enumerate(tokens):
            if token in ("-C", "--git-dir") or token.startswith("--git-dir="):
                return "git run outside the working directory: %s" % command[:120]
    hit = COMMAND_RE.search(command)
    if hit:
        return "command names %s: %s" % (hit.group(1), command[:120])
    for token in tokens:
        token = token.rstrip(";&|)")  # `cd /own/workdir; ls` is one token ending in ';', not a different path
        if os.path.isabs(token) and cwd and not (token == cwd or token.startswith(cwd.rstrip("/") + "/")):
            # An absolute path whose first component is no top-level directory of this machine (a grep pattern such as
            # '/node_modules/') cannot reach any file.
            first = token.split("/")[1] if token.count("/") >= 1 else ""
            if first and not os.path.exists("/" + first):
                continue
            if not token.startswith(("/dev/", "/usr/", "/bin/", "/opt/homebrew/")) and token != "/":
                return "command names a path outside the working directory: %s" % command[:120]
    return None


def _result_paths(text: str) -> Iterator[str]:
    for line in text.splitlines():
        line = line.strip()
        if not line or " " in line.split(":")[0]:
            continue
        match = RESULT_PATH_RE.match(line)
        if match:
            yield match.group("path")


def result_problem(tool: str, text: str, cwd: Optional[str], base: Optional[str] = None) -> Optional[str]:
    """A Grep or Glob result that lists forbidden paths. Names every distinct one (at most eight).

    Grep and Glob print paths relative to the directory they searched (their `path` input). A result line `tests/x.test.ts`
    from a search of app/src is app/src/tests/x.test.ts, a file of the app, so relative result paths are resolved against
    `base` before they are judged (seen in a live run, where the app's own src/tests folder looked like the harness tests/)."""
    if tool not in ("Grep", "Glob"):
        return None
    found = []
    for path in _result_paths(text):
        if "/" not in path and "." not in path:
            continue
        if base and not os.path.isabs(path) and not path.startswith(".."):
            path = os.path.join(base, path)
        if path_problem(path, cwd) and path not in found:
            found.append(path)
    return "result lists " + ", ".join(found[:8]) if found else None


def check_transcript(path: str, cwd: Optional[str] = None) -> Dict[str, object]:
    """Violations and blocked attempts in one transcript."""
    uses: Dict[str, dict] = {}
    results: Dict[str, dict] = {}
    denied = set()
    session_cwd = cwd
    order: List[str] = []
    for event in _events(path):
        if event.get("type") == "system" and event.get("subtype") == "init" and not session_cwd:
            session_cwd = event.get("cwd")
        if event.get("type") == "system" and event.get("subtype") == "permission_denied" and event.get("tool_use_id"):
            denied.add(event["tool_use_id"])
        for block in _blocks(event):
            if block.get("type") == "tool_use":
                uses[block["id"]] = {"name": block.get("name", ""), "input": block.get("input") or {}}
                order.append(block["id"])
            elif block.get("type") == "tool_result" and block.get("tool_use_id"):
                results[block["tool_use_id"]] = {"is_error": bool(block.get("is_error")), "text": _result_text(block)}

    violations: List[dict] = []
    blocked: List[dict] = []
    for use_id in order:
        use = uses[use_id]
        name, data = use["name"], use["input"]
        if name.startswith("mcp__") or name == "ToolSearch":
            continue
        reasons = []
        if name in PATH_TOOLS:
            for field in PATH_FIELDS:
                value = data.get(field)
                if field == "pattern" and name != "Glob":
                    continue
                if isinstance(value, str):
                    problem = path_problem(value, session_cwd)
                    if problem:
                        reasons.append(problem)
        elif name == "Bash" and isinstance(data.get("command"), str):
            problem = command_problem(data["command"], session_cwd)
            if problem:
                reasons.append(problem)
        result = results.get(use_id)
        if result and not result["is_error"] and use_id not in denied and name in ("Grep", "Glob"):
            problem = result_problem(name, result["text"], session_cwd, data.get("path") if isinstance(data.get("path"), str) else None)
            if problem:
                reasons.append(problem)
        if not reasons:
            continue
        succeeded = bool(result) and not result["is_error"] and use_id not in denied
        # A Grep or Glob whose own input was fine but whose result listed a forbidden path is a success by definition.
        entry = {"tool": name, "tool_use_id": use_id, "reasons": sorted(set(reasons)),
                 "input": {k: (v[:160] if isinstance(v, str) else v) for k, v in data.items() if k in PATH_FIELDS or k == "command"}}
        (violations if succeeded else blocked).append(entry)
    return {"transcript": path, "cwd": session_cwd, "tool_calls": len(order), "violations": violations, "blocked": blocked}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("transcripts", nargs="+")
    parser.add_argument("--cwd", help="the role's working directory; default is the cwd in each transcript's init event")
    parser.add_argument("--strict", action="store_true", help="blocked attempts also fail the check")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = parser.parse_args(argv)

    reports = [check_transcript(path, args.cwd) for path in args.transcripts]
    failing = 0
    for report in reports:
        bad = len(report["violations"]) + (len(report["blocked"]) if args.strict else 0)
        failing += 1 if bad else 0
        if not args.json:
            print("%s  tool calls %d  violations %d  blocked %d" % (
                os.path.basename(report["transcript"]), report["tool_calls"], len(report["violations"]), len(report["blocked"])))
            for entry in report["violations"]:
                print("    VIOLATION %-6s %s" % (entry["tool"], "; ".join(entry["reasons"])))
            for entry in report["blocked"]:
                print("    blocked   %-6s %s" % (entry["tool"], "; ".join(entry["reasons"])))
    if args.json:
        print(json.dumps(reports, indent=2))
    total = sum(len(r["violations"]) for r in reports)
    print("isolation check: %d transcript(s), %d with violations, %d violation(s) in total" % (len(reports), failing, total))
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
