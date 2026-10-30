#!/usr/bin/env python3
"""A hand-labeled sample that checks whether the cited text SUPPORTS each answer.

The citation verifier proves that cited bytes exist and hash correctly. It does not prove that the answer says what
those bytes say. This script builds a reproducible sample of recorded answers for a person to label, and reports the
rate once the labels are in. It never fills a label.

  python3 scripts/support_sample.py make --asks demo-state/asks.jsonl --n 50 --seed 1 --out labels/support-sample-pilot.json
  python3 scripts/support_sample.py make ... --vault-root team=/path/to/vault   (also writes the cited text, when it can be read)
  python3 scripts/support_sample.py report labels/support-sample-pilot.json

Entries: `supported` is 1 (every claim in the answer is in the cited text), 0.5 (some are) or 0 (none are); null means
not labeled yet. The sheet also holds `labeler` and `labeled_at`, which a person fills in with the labels.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_citations  # noqa: E402

VALID = (0, 0.5, 1, None)


def eligible(asks: List[dict]) -> List[int]:
    """Indexes of asks that returned sources and a non-empty answer."""
    return [i for i, ask in enumerate(asks) if ask.get("sources") and (ask.get("text") or "").strip()]


def cited_text(source: dict, vault: str, roots: Optional[Dict[str, str]]) -> Optional[str]:
    if not vault:
        return None
    root = verify_citations.vault_root(vault, roots)
    ok, _reason = verify_citations.verify_source(source, root)
    if not ok:
        return None
    with open(os.path.join(root, source["path"]), "rb") as handle:
        raw = handle.read()
    return raw[source["byte_start"]:source["byte_end"]].decode("utf-8", "replace")


def make_sample(asks_path: str, n: int, seed: int, roots: Optional[Dict[str, str]] = None) -> dict:
    with open(asks_path) as handle:
        asks = [json.loads(line) for line in handle if line.strip()]
    pool = eligible(asks)
    chosen = sorted(random.Random(seed).sample(pool, min(n, len(pool))))
    entries = []
    for index in chosen:
        ask = asks[index]
        sources, seen = [], set()
        for src in ask["sources"]:
            key = (src.get("path"), src.get("byte_start"), src.get("byte_end"))
            if key in seen:
                continue
            seen.add(key)
            entry = {"path": key[0], "byte_start": key[1], "byte_end": key[2]}
            text = cited_text(src, ask.get("vault_served"), roots)
            if text is not None:
                entry["cited_text"] = text
            sources.append(entry)
        entries.append({"ask": "%s:%d" % (os.path.basename(asks_path), index + 1), "step": ask.get("step"),
                        "role": ask.get("role"), "question": (ask.get("request") or {}).get("question"),
                        "answer": ask.get("text"), "sources": sources, "supported": None, "note": ""})
    return {"schema": "neuron-demo-support-sample/1", "asks_file": os.path.basename(asks_path), "seed": seed,
            "population": len(pool), "labeler": "", "labeled_at": "", "entries": entries}


def report(sheet: dict) -> dict:
    labeled = [e["supported"] for e in sheet["entries"] if e.get("supported") is not None]
    bad = [e["ask"] for e in sheet["entries"] if e.get("supported") not in VALID]
    named = bool(str(sheet.get("labeler") or "").strip()) and str(sheet.get("labeled_at") or "").endswith("Z")
    out = {"entries": len(sheet["entries"]), "labeled": len(labeled), "invalid": bad, "labeler_named": named}
    out["rate"] = round(sum(labeled) / len(labeled), 4) if labeled and named else None
    out["fully_supported"] = sum(1 for v in labeled if v == 1)
    out["partly_supported"] = sum(1 for v in labeled if v == 0.5)
    out["unsupported"] = sum(1 for v in labeled if v == 0)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    make = sub.add_parser("make")
    make.add_argument("--asks", required=True)
    make.add_argument("--n", type=int, default=50)
    make.add_argument("--seed", type=int, default=1)
    make.add_argument("--out", required=True)
    make.add_argument("--vault-root", action="append", default=[], help="name=/path, repeatable")
    rep = sub.add_parser("report")
    rep.add_argument("sheet")
    args = parser.parse_args(argv)
    if args.cmd == "make":
        if os.path.exists(args.out):
            print("%s exists; not overwriting a sheet that may hold labels" % args.out)
            return 2
        roots = dict(item.split("=", 1) for item in args.vault_root)
        sheet = make_sample(args.asks, args.n, args.seed, roots)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as handle:
            json.dump(sheet, handle, indent=2)
            handle.write("\n")
        print("wrote %d entries (population %d) to %s, all unlabeled" % (len(sheet["entries"]), sheet["population"], args.out))
        return 0
    with open(args.sheet) as handle:
        result = report(json.load(handle))
    if result["labeled"] == 0:
        print("not labeled: %d entries, 0 labels" % result["entries"])
    elif result["rate"] is None:
        print("labels present but labeler or labeled_at is missing: no rate reported")
    else:
        print("supported rate %.3f over %d labeled of %d (full %d, partial %d, none %d)" % (
            result["rate"], result["labeled"], result["entries"], result["fully_supported"], result["partly_supported"], result["unsupported"]))
    return 1 if result["invalid"] else 0


if __name__ == "__main__":
    sys.exit(main())
