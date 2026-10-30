#!/usr/bin/env python3
"""Find, or mechanically redact, personal data in committed text files.

What counts as personal data here: an absolute user-home path (macOS or Linux), the author's working
folder name, and the name of the personal vault that sat on the author's Neuron daemon. The literals
are built from pieces so that this file does not contain them and therefore does not flag itself.

  python3 scripts/scan_personal.py              list every match in tracked files, exit 1 if any
  python3 scripts/scan_personal.py --redact     replace matches with placeholders, in place

Replacements are mechanical and never touch anything else: a home path becomes <HOME>, the author's
working copy becomes <REPO>, the personal vault name becomes <other-vault>. Binary files are not
scanned and are listed, because an image can still show a path in its pixels.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from typing import Dict, Iterator, List, Optional, Tuple

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ORG = "Infra" + "sity"
_WORKDIR = "ne" + "u"
_PERSONAL_VAULT = "my" + "notes"

# Order matters: the more specific working-copy path is replaced before the generic home path.
RULES: List[Tuple["re.Pattern[str]", str, str]] = [
    (re.compile(r"/(?:Users|home)/[^/\s\"'\\<>]+/%s/%s\b" % (_ORG, _WORKDIR)), "<REPO>", "working copy path"),
    (re.compile(r"/(?:Users|home)/[^/\s\"'\\<>]+"), "<HOME>", "user home path"),
    (re.compile(r"[A-Za-z]:\\Users\\[^\\\s\"']+"), "<HOME>", "windows user home path"),
    (re.compile(r"\b%s\b" % _PERSONAL_VAULT), "<other-vault>", "personal vault name"),
    (re.compile(r"\b%s/%s\b" % (_ORG, _WORKDIR)), "<REPO>", "working folder name"),
]

# Paths that are generic and carry no person: CI runners and containers.
ALLOWED_HOMES = ("/home/runner", "/home/vsts", "/home/node", "/home/user", "/Users/runner", "/home/<", "/Users/<")

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "tmp"}
SKIP_FILES = {"scripts/scan_personal.py", "tests/test_scan_personal.py"}


def tracked_files(root: str = REPO) -> List[str]:
    """Tracked plus not-yet-tracked (not ignored) files. Falls back to a directory walk without git."""
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                             capture_output=True, check=True)
        names = [n for n in out.stdout.decode("utf-8").split("\0") if n]
        return sorted(n for n in names if os.path.isfile(os.path.join(root, n)))
    except (OSError, subprocess.CalledProcessError):
        found = []
        for base, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in files:
                found.append(os.path.relpath(os.path.join(base, name), root))
        return sorted(found)


def read_text(path: str) -> Optional[str]:
    """The text of a file, or None when it is binary."""
    with open(path, "rb") as handle:
        raw = handle.read()
    if b"\0" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _allowed(text: str) -> bool:
    return any(text.startswith(prefix) for prefix in ALLOWED_HOMES)


def find_matches(text: str) -> List[Tuple[int, str, str]]:
    """(line number, label, matched text) for every personal-data match in `text`."""
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        for pattern, _replacement, label in RULES:
            for match in pattern.finditer(line):
                if _allowed(match.group(0)):
                    continue
                hits.append((number, label, match.group(0)))
    return hits


def redact(text: str) -> str:
    for pattern, replacement, _label in RULES:
        text = pattern.sub(lambda m, r=replacement: m.group(0) if _allowed(m.group(0)) else r, text)
    return text


def scan(root: str = REPO, files: Optional[List[str]] = None) -> Tuple[Dict[str, List[Tuple[int, str, str]]], List[str]]:
    """(matches by file, binary files that were not scanned)."""
    matches: Dict[str, List[Tuple[int, str, str]]] = {}
    binary: List[str] = []
    for rel in files if files is not None else tracked_files(root):
        if rel in SKIP_FILES:
            continue
        text = read_text(os.path.join(root, rel))
        if text is None:
            binary.append(rel)
            continue
        hits = find_matches(text)
        if hits:
            matches[rel] = hits
    return matches, binary


def redact_files(root: str = REPO) -> Dict[str, int]:
    """Rewrite every file that has a match. Returns files changed and how many matches each had."""
    changed: Dict[str, int] = {}
    matches, _binary = scan(root)
    for rel, hits in matches.items():
        path = os.path.join(root, rel)
        with open(path, encoding="utf-8", newline="") as handle:
            text = handle.read()
        new = redact(text)
        if new != text:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(new)
            changed[rel] = len(hits)
    return changed


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--redact", action="store_true", help="rewrite matching files with placeholders")
    parser.add_argument("--root", default=REPO)
    args = parser.parse_args(argv)
    if args.redact:
        changed = redact_files(args.root)
        for rel in sorted(changed):
            print("redacted %-55s %d match(es)" % (rel, changed[rel]))
        print("%d file(s) rewritten" % len(changed))
    matches, binary = scan(args.root)
    total = sum(len(v) for v in matches.values())
    for rel in sorted(matches):
        for number, label, text in matches[rel][:5]:
            print("%s:%d: %s: %s" % (rel, number, label, text))
        if len(matches[rel]) > 5:
            print("%s: ... %d more" % (rel, len(matches[rel]) - 5))
    print("personal-data scan: %d match(es) in %d file(s); %d binary file(s) not scanned" % (total, len(matches), len(binary)))
    for rel in binary:
        if rel.lower().endswith((".png", ".jpg", ".jpeg", ".gif")) and not rel.startswith("app/"):
            print("  not scanned (image, may show a path in its pixels): %s" % rel)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
