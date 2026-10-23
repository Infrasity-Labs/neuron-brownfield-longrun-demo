#!/usr/bin/env python3
"""Replay the ten steps of the demo.

  python run_demo.py --dry-run              print every prompt for all ten steps, needs no Neuron
  python run_demo.py --steps 4 7 9          run only those steps
  python run_demo.py --start 4              run steps 4 to 10

Each role runs as a fresh `claude -p` session with `--strict-mcp-config`, so it sees only the MCP
configuration this script writes for it, never the user-scope entry the Neuron installer adds.
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

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import steps as step_table  # noqa: E402

MCP_URL = os.environ.get("OKTO_NEURON_MCP_URL", "http://127.0.0.1:8201/mcp")
TOKEN_FILE = os.environ.get("OKTO_NEURON_TOKEN_FILE", os.path.expanduser("~/.okto-neuron/daemon-7777.token"))


def read(rel: str) -> str:
    with open(os.path.join(REPO, rel)) as handle:
        return handle.read()


def role_url(role: str) -> str:
    query = step_table.ROLES[role]["mcp_vault_query"]
    return MCP_URL + ("?vault=" + query if query else "")


def write_mcp_config(role: str, directory: str) -> str:
    """Write the per-role MCP config with the daemon token. The token is read here and never printed."""
    with open(TOKEN_FILE) as handle:
        token = handle.read().strip()
    config = {"mcpServers": {"okto-neuron": {"type": "http", "url": role_url(role),
                                              "headers": {"Authorization": "Bearer " + token}}}}
    path = os.path.join(directory, "mcp-%s.json" % role)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(config, handle)
    return path


def vault_snapshot() -> dict:
    """File modification times under the two watched folders, to see whether a role wrote a note."""
    snap = {}
    for folder in ("vault", "vault-private"):
        for base, _dirs, files in os.walk(os.path.join(REPO, folder)):
            for name in files:
                path = os.path.join(base, name)
                snap[path] = os.path.getmtime(path)
    return snap


def claude_command(role: str, prompt: str, mcp_config: str, max_turns: int, model: Optional[str] = None) -> List[str]:
    spec = step_table.ROLES[role]
    model_args = ["--model", model] if model else []
    return ["claude", "-p", prompt] + model_args + [
            "--strict-mcp-config", "--mcp-config", mcp_config,
            "--append-system-prompt", read(spec["claude_md"]) + "\n\n" + read("agents/neuron-skill.md"),
            "--permission-mode", "acceptEdits",
            "--output-format", "stream-json", "--verbose",
            "--max-turns", str(max_turns),
            "--allowedTools"] + spec["tools"]


def dry_run_step(step: dict) -> None:
    print("=" * 78)
    print("STEP %d  %s" % (step["id"], step["title"]))
    print("=" * 78)
    if step["kind"] == "setup":
        print("[maintainer] bash scripts/setup_vaults.sh   (onboard, create vaults, watch folders, wait for ingest)")
    if step.get("maintainer"):
        print("[maintainer] python scripts/maintainer_edit.py %s, then python scripts/wait_ingest.py" % step["maintainer"])
    for role, prompt_path in step["runs"]:
        spec = step_table.ROLES[role]
        print("\n--- role: %s | prompt: %s" % (role, prompt_path))
        print("MCP url       : %s" % role_url(role))
        print("allowed tools : %s" % ", ".join(spec["tools"]))
        print("system prompt : %s + agents/neuron-skill.md" % spec["claude_md"])
        print("prompt:")
        print("\n".join("    " + line for line in read(prompt_path).strip().splitlines()))
    if step["kind"] == "closeout":
        print("[script] python scripts/closeout.py   (reads demo-state/asks.jsonl)")
    print()


def run_step(step: dict, args: argparse.Namespace) -> int:
    print("\nSTEP %d: %s" % (step["id"], step["title"]))
    if step["kind"] == "setup":
        return subprocess.call(["bash", os.path.join(REPO, "scripts/setup_vaults.sh")], cwd=REPO)
    if step["kind"] == "closeout":
        return subprocess.call([sys.executable, os.path.join(REPO, "scripts/closeout.py"), "--recheck"], cwd=REPO)

    action = step.get("maintainer")
    if action:
        subprocess.check_call([sys.executable, os.path.join(REPO, "scripts/maintainer_edit.py"), action], cwd=REPO)
        if action == "step9" and not args.yes:
            input("Press Enter once the model endpoint is stopped: ")
        if action in ("step4", "step7"):
            subprocess.check_call([sys.executable, os.path.join(REPO, "scripts/wait_ingest.py"),
                                   "--label", "step %d edit" % step["id"], "--vault", step_table.TEAM_VAULT, "--settle", "8"], cwd=REPO)

    os.makedirs(os.path.join(REPO, args.transcripts_dir), exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="neuron-demo-mcp-")
    before = vault_snapshot()
    try:
        for role, prompt_path in step["runs"]:
            transcript = os.path.join(REPO, args.transcripts_dir, "step%02d-%s.jsonl" % (step["id"], role))
            config = write_mcp_config(role, tmp)
            command = claude_command(role, read(prompt_path), config, args.max_turns, args.model)
            print("running %s ..." % role)
            with open(transcript, "w") as out:
                code = subprocess.call(command, cwd=REPO, stdout=out)
            if code != 0:
                print("claude exited with %d, see %s" % (code, transcript))
                return code
            subprocess.check_call([sys.executable, os.path.join(REPO, "scripts/neuron_asks.py"), transcript,
                                   "--step", str(step["id"]), "--role", role], cwd=REPO)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if step["runs"] and vault_snapshot() != before:
        # A role wrote a spec or a private finding into a watched folder, so wait for it to be ingested.
        subprocess.check_call([sys.executable, os.path.join(REPO, "scripts/wait_ingest.py"),
                               "--label", "after step %d" % step["id"], "--vault", step_table.TEAM_VAULT,
                               "--settle", "8"], cwd=REPO)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--steps", type=int, nargs="+", help="run only these steps, for example --steps 4 7 9")
    parser.add_argument("--start", type=int, help="run this step and every step after it")
    parser.add_argument("--dry-run", action="store_true", help="print every prompt, run nothing")
    parser.add_argument("--yes", action="store_true", help="do not pause for the model outage in step 9")
    parser.add_argument("--transcripts-dir", default="demo-state/transcripts")
    parser.add_argument("--max-turns", type=int, default=25)
    parser.add_argument("--model", default="claude-haiku-5-5",
                        help="model for every role session, a fast one by default; pass '' for Claude Code's own default")
    args = parser.parse_args(argv)

    chosen = step_table.STEPS
    if args.steps:
        chosen = [s for s in chosen if s["id"] in args.steps]
    elif args.start:
        chosen = [s for s in chosen if s["id"] >= args.start]
    if not chosen:
        parser.error("no such step; steps are 1 to 10")

    for step in chosen:
        if args.dry_run:
            dry_run_step(step)
        else:
            code = run_step(step, args)
            if code != 0:
                print("stopped at step %d" % step["id"])
                return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
