"""Shared helpers for the alignment metric: the fingerprint of its written definition and the work product list."""
from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRIC_FILES = ["docs/METRIC.md", "scenarios/work_products.json"]
# docs/METRIC.md ends its definition with this line. What follows it (the results of recorded runs) is not part of the
# definition and is left out of the fingerprint, so that reporting a result never invalidates the runs it reports.
DEFINITION_END = "<!-- END definition -->"
EQUIVALENTS = os.path.join("scenarios", "metric-equivalents.json")


def metric_fingerprint(repo: str = REPO) -> str:
    """SHA-256 over the written definition (docs/METRIC.md up to DEFINITION_END) and the product list. Stored in every run manifest."""
    digest = hashlib.sha256()
    for rel in METRIC_FILES:
        with open(os.path.join(repo, rel), "rb") as handle:
            raw = handle.read()
        if rel == METRIC_FILES[0] and DEFINITION_END.encode() in raw:
            raw = raw[:raw.index(DEFINITION_END.encode()) + len(DEFINITION_END)]
        digest.update(rel.encode("utf-8") + b"\0" + raw + b"\0")
    return digest.hexdigest()


def accepted_fingerprints(repo: str = REPO) -> List[str]:
    """The current fingerprint plus every earlier one that scenarios/metric-equivalents.json declares to be the same metric,
    each with the reason. A listed fingerprint is an earlier text of the same definition (a changed status paragraph, nothing
    that changes what is scored); a changed definition is never listed."""
    accepted = [metric_fingerprint(repo)]
    path = os.path.join(repo, EQUIVALENTS)
    if os.path.isfile(path):
        with open(path) as handle:
            accepted.extend(item["sha256"] for item in json.load(handle)["equivalent"])
    return accepted


def load_products(repo: str = REPO) -> dict:
    with open(os.path.join(repo, "scenarios", "work_products.json")) as handle:
        return json.load(handle)


def product_ids(kind: str = "", repo: str = REPO) -> List[str]:
    return [p["id"] for p in load_products(repo)["products"] if not kind or p["kind"] == kind]
