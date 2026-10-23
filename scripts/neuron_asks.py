#!/usr/bin/env python3
"""Record every Neuron ask an agent made, taken from its Claude Code stream-json transcript.

Why a transcript and not a proxy: each role runs as `claude -p --output-format stream-json`, which
already holds the exact tool call and the exact tool result. Reading it needs no Neuron credential.

Each ask becomes one line in demo-state/asks.jsonl. Every line carries synthesis_status, the
finish_reason, whether Neuron reported vault_override_ignored, and a citation check that ran at
record time (before any later note edit can change the cited bytes).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from typing import Dict, Iterator, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_citations  # noqa: E402

SYNTHESIS_STATUSES = ("ok", "no_llm", "empty", "provider_error", "truncated", "abnormal_stop")


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


def _result_text(block: dict) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def extract_calls(path: str) -> List[dict]:
    """Pair each ask/explore tool call with its result and the agent's next sentence."""
    calls: Dict[str, dict] = {}
    ordered: List[dict] = []
    pending: Optional[dict] = None
    for event in _events(path):
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            name = block.get("name", "")
            if kind == "tool_use" and (name.endswith("__ask") or name.endswith("__explore")):
                call = {
                    "tool": "ask" if name.endswith("__ask") else "explore",
                    "tool_use_id": block.get("id"),
                    "request": block.get("input") or {},
                    "result_text": None,
                    "is_error": False,
                    "followup": "",
                }
                calls[block.get("id")] = call
                ordered.append(call)
            elif kind == "tool_result" and block.get("tool_use_id") in calls:
                call = calls[block["tool_use_id"]]
                call["result_text"] = _result_text(block)
                call["is_error"] = bool(block.get("is_error"))
                pending = call
            elif kind == "text" and event.get("type") == "assistant" and pending is not None:
                if not pending["followup"]:
                    pending["followup"] = (block.get("text") or "").strip()
                pending = None
    return ordered


def build_ask_record(call: dict, step: int, role: str, roots: Optional[Dict[str, str]] = None) -> dict:
    """Turn one paired call into a record. Never invents a field: missing values stay None."""
    request = call["request"]
    raw = call["result_text"] or ""
    try:
        response = json.loads(raw)
        if not isinstance(response, dict):
            raise ValueError("not an object")
    except ValueError:
        response = None

    retrieval = (response or {}).get("retrieval") or {}
    override = (response or {}).get("vault_override_ignored", retrieval.get("vault_override_ignored"))
    vault_served = retrieval.get("vault") or request.get("vault")
    sources = (response or {}).get("sources") or []
    checks = verify_citations.verify_sources(sources, vault_served, roots) if vault_served and sources else []

    return {
        "recorded_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "step": step,
        "role": role,
        "tool_use_id": call["tool_use_id"],
        "request": {
            "question": request.get("question"),
            "vault": request.get("vault"),
            "include_sources": request.get("include_sources"),
        },
        "status": (response or {}).get("status"),
        "synthesis_status": retrieval.get("synthesis_status") if response else "unparsed",
        "finish_reason": retrieval.get("finish_reason"),
        "text": (response or {}).get("text", ""),
        "citation_count": len((response or {}).get("citations") or []),
        "sources": sources,
        "vault_served": vault_served,
        "vault_override_ignored": override,
        "citation_checks": checks,
        "tool_error": call["is_error"],
        "agent_followup": call["followup"],
    }


def record(transcript: str, step: int, role: str, out: str, explores_out: str,
           roots: Optional[Dict[str, str]] = None) -> Dict[str, int]:
    counts = {"asks": 0, "explores": 0}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    for call in extract_calls(transcript):
        if call["tool"] == "ask":
            line, target = build_ask_record(call, step, role, roots), out
            counts["asks"] += 1
        else:
            line = {
                "step": step, "role": role, "tool_use_id": call["tool_use_id"],
                "request": call["request"], "result_text": call["result_text"],
                "agent_followup": call["followup"],
            }
            target = explores_out
            counts["explores"] += 1
        with open(target, "a") as handle:
            handle.write(json.dumps(line) + "\n")
    return counts


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript")
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--out", default="demo-state/asks.jsonl")
    parser.add_argument("--explores-out", default="demo-state/explores.jsonl")
    parser.add_argument("--vault-root", action="append", default=[])
    args = parser.parse_args(argv)
    roots = dict(item.split("=", 1) for item in args.vault_root)
    counts = record(args.transcript, args.step, args.role, args.out, args.explores_out, roots)
    print("recorded %(asks)d ask(s) and %(explores)d explore(s)" % counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
