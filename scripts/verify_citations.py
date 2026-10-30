#!/usr/bin/env python3
"""Check that a cited source still matches its content_hash.

Neuron returns, per source, a vault-relative path, a byte range and
content_hash = sha256(raw[byte_start:byte_end]). This script re-reads those bytes and compares.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

def default_vaults_dir() -> str:
    """Neuron's vault folder under the CURRENT home. Read at call time so a run with an isolated HOME looks there."""
    return os.path.expanduser("~/.okto-neuron/vaults")


def vault_root(vault: str, roots: Optional[Dict[str, str]] = None) -> str:
    if roots and vault in roots:
        return roots[vault]
    return os.path.join(os.environ.get("OKTO_NEURON_VAULTS_DIR") or default_vaults_dir(), vault)


def verify_source(source: dict, root: str) -> Tuple[bool, str]:
    """Return (ok, reason). reason is "ok" on success."""
    rel = source.get("path")
    if not rel or os.path.isabs(rel):
        return False, "path missing or absolute"
    full = os.path.realpath(os.path.join(root, rel))
    real_root = os.path.realpath(root)
    if not (full == real_root or full.startswith(real_root + os.sep)):
        return False, "path escapes the vault"
    if not os.path.isfile(full):
        return False, "file not found"
    start, end = source.get("byte_start"), source.get("byte_end")
    if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end < start:
        return False, "bad byte range"
    with open(full, "rb") as handle:
        raw = handle.read()
    if end > len(raw):
        return False, "byte range is past the end of the file"
    digest = "sha256:" + hashlib.sha256(raw[start:end]).hexdigest()
    expected = source.get("content_hash") or ""
    if not expected.startswith("sha256:"):
        expected = "sha256:" + expected
    if digest != expected:
        return False, "hash mismatch"
    return True, "ok"


def verify_sources(sources: List[dict], vault: str, roots: Optional[Dict[str, str]] = None) -> List[dict]:
    root = vault_root(vault, roots)
    results = []
    for source in sources or []:
        ok, reason = verify_source(source, root)
        results.append({"id": source.get("id"), "path": source.get("path"), "ok": ok, "reason": reason})
    return results


def _parse_roots(items: List[str]) -> Dict[str, str]:
    roots = {}
    for item in items or []:
        name, _, path = item.partition("=")
        if not name or not path:
            raise SystemExit("--vault-root must look like name=/path")
        roots[name] = path
    return roots


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asks", help="asks.jsonl, or a single ask response saved as .json")
    parser.add_argument("--vault", help="vault name, needed when the input is a single response")
    parser.add_argument("--vault-root", action="append", default=[], help="name=/path, repeatable")
    args = parser.parse_args(argv)
    roots = _parse_roots(args.vault_root)

    if args.asks.endswith(".jsonl"):
        with open(args.asks) as handle:
            records = [json.loads(line) for line in handle if line.strip()]
    else:
        with open(args.asks) as handle:
            single = json.load(handle)
        records = [{"vault_served": args.vault or (single.get("retrieval") or {}).get("vault"), "sources": single.get("sources", [])}]

    failed = total = 0
    for rec in records:
        vault = rec.get("vault_served") or (rec.get("request") or {}).get("vault")
        if not vault:
            print("skip: record has no vault name")
            continue
        for res in verify_sources(rec.get("sources", []), vault, roots):
            total += 1
            if not res["ok"]:
                failed += 1
            print("%s %s %s" % ("PASS" if res["ok"] else "FAIL", res["path"], "" if res["ok"] else res["reason"]))
    print("%d of %d citations passed" % (total - failed, total))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
