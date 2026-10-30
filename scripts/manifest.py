#!/usr/bin/env python3
"""The run manifest: every version and setting that can change a run, in one file per run.

runs/<arm>/<run-id>/run-manifest.json records the Neuron version, the claude CLI version, the model, Node, Python, the
OS, the commit of this repository (and whether the tree was dirty), the written metric's fingerprint, the pins in
pins.json, and per session the Claude Code version and model its own init event reported. Model output is not
deterministic: `claude -p` is called with no sampling control (the CLI help lists no seed or temperature option), so two
runs with the same manifest still differ. The spread over repeated runs is what scores report.

  python3 scripts/manifest.py            print the manifest for this machine (no run needed)
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import events as event_log  # noqa: E402
import metric  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NONDETERMINISM = ("Model output is not deterministic. claude -p is run without a seed or temperature setting because the CLI "
                  "offers none. Repeat runs and report the spread (docs/METRIC.md).")


def _out(args: List[str], cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> Optional[str]:
    if shutil.which(args[0]) is None:
        return None
    try:
        proc = subprocess.run(args, capture_output=True, text=True, cwd=cwd, env=env, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (proc.stdout or proc.stderr).strip() if proc.returncode == 0 else None


def first_version(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"\bv?(\d+\.\d+\.\d+[\w.+-]*)", text.splitlines()[0])
    return match.group(1) if match else None


def git_state(repo: str = REPO) -> Dict[str, object]:
    sha = _out(["git", "-C", repo, "rev-parse", "HEAD"])
    if not sha:
        return {"commit": None, "dirty": None}
    status = _out(["git", "-C", repo, "status", "--porcelain"])
    return {"commit": sha, "dirty": bool(status)}


HARNESS_PATHS = ("run_demo.py", "pins.json", "scripts/", "agents/", "docs/prompts/", "docs/questions.json", "scenarios/", "vault/",
                 "app/")


def harness_fingerprint(repo: str = REPO) -> Dict[str, object]:
    """SHA-256 over the path and content of every file that can change what a run does (the runner, the scripts, the prompts,
    the agent files, the scenarios, the starting notes, the app, the pins), tracked or not. The repository's commit alone does
    not identify the harness of a run when the working tree is dirty; this does. Documents, labels and runs are not included."""
    out = _out(["git", "-C", repo, "ls-files", "--cached", "--others", "--exclude-standard"])
    if not out:
        return {"sha256": None, "files": 0}
    digest = hashlib.sha256()
    count = 0
    for rel in sorted(set(out.splitlines())):
        if not rel.startswith(HARNESS_PATHS):
            continue
        path = os.path.join(repo, rel)
        if not os.path.isfile(path):
            continue
        digest.update(rel.encode() + b"\0" + file_sha256(path).encode() + b"\0")
        count += 1
    return {"sha256": digest.hexdigest(), "files": count}


def file_sha256(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def session_versions(transcript: str) -> Dict[str, Optional[object]]:
    """Claude Code version, model and working directory a session's own init event reported, and what its own `result`
    event reported about the session (cost in USD, duration, turns, error flag). Nothing here is estimated."""
    info: Dict[str, Optional[object]] = {"claude_code_version": None, "model": None, "cwd": None}
    with open(transcript) as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "system" and event.get("subtype") == "init" and info["cwd"] is None:
                info.update({"claude_code_version": event.get("claude_code_version"), "model": event.get("model"),
                             "cwd": event.get("cwd")})
            elif event.get("type") == "result":
                info.update({"total_cost_usd": event.get("total_cost_usd"), "duration_ms": event.get("duration_ms"),
                             "num_turns": event.get("num_turns"), "is_error": event.get("is_error"),
                             "result_subtype": event.get("subtype")})
    return info


def collect(arm: str, run_id: str, model: str, max_turns: int, flags: Dict[str, object],
            neuron_version: Optional[str], neuron_env: Optional[Dict[str, str]] = None, repo: str = REPO) -> dict:
    with open(os.path.join(repo, "pins.json")) as handle:
        pins = json.load(handle)
    return {
        "schema": "neuron-demo-run-manifest/1",
        "run_id": run_id,
        "arm": arm,
        "started_at": event_log.utc_now(),
        "finished_at": None,
        "repo": dict(git_state(repo), harness=harness_fingerprint(repo)),
        "versions": {
            "neuron": neuron_version,
            "neuron_pinned": pins["neuron"]["version"],
            "claude_cli": first_version(_out(["claude", "--version"])),
            "claude_cli_pinned": pins["claude_cli"]["expected_version"],
            "node": _out(["node", "--version"]),
            "npm": _out(["npm", "--version"]),
            "python": platform.python_version(),
            "os": "%s %s %s" % (platform.system(), platform.release(), platform.machine()),
        },
        "model": model,
        "model_pinned": pins["model"],
        "max_turns": max_turns,
        "claude_flags": flags,
        "metric": {"sha256": metric.metric_fingerprint(repo), "files": metric.METRIC_FILES},
        "pins_sha256": file_sha256(os.path.join(repo, "pins.json")),
        "nondeterminism": NONDETERMINISM,
        "sessions": [],
        "checks": {},
    }


def write(path: str, manifest: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")


def main() -> int:
    print(json.dumps(collect("neuron", "preview", "claude-haiku-5-5", 25, {}, None), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
