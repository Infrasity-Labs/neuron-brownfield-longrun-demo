#!/usr/bin/env python3
"""Build the clean working directory each role runs in, and carry its output back.

A role must not be able to read the Maintainer's notes, the plan, the docs or the recorded results with
Read, Grep, Glob or git. So no role runs in this repository. Each role runs in a directory that holds only
what that role needs:

  planner   app/ (read it), specs/ (empty, it writes the spec here)
  builder   app/, specs/ (the Planner's spec), a git repository whose only history is the app baseline
  reviewer  app/ with the Builder's edits, the same git repository, private-out/ (empty, it writes findings here)

The shared channels are therefore exactly: the app/ tree (Builder to Reviewer), the spec files (Planner to
Builder), and the Reviewer's private-out/ folder, which the runner copies into the folder Neuron watches for
the reviewer-private vault. Nothing else crosses between sessions.

  python3 scripts/build_workdir.py init    --canonical DIR
  python3 scripts/build_workdir.py role    --role builder --canonical DIR --dest DIR
  python3 scripts/build_workdir.py collect --role builder --workdir DIR --canonical DIR [--private-dest DIR]
  python3 scripts/build_workdir.py verify  --role builder --workdir DIR
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from typing import Dict, List, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Build and dependency output that is never copied into a role's app/ tree.
APP_EXCLUDE = {"node_modules", "dist", "tmp", ".nx", "coverage", "out-tsc", ".git"}

# What may sit at the top of a role's directory. Anything else fails `verify`.
ALLOWED_TOP = {
    "planner": {"app", "specs"},
    "builder": {"app", "specs", ".git", ".gitignore"},
    "reviewer": {"app", "private-out", ".git", ".gitignore"},
}

MAX_SPEC_BYTES = 20000
MAX_NOTE_BYTES = 20000

GIT_IDENTITY = ["-c", "user.name=neuron-demo", "-c", "user.email=neuron-demo@invalid"]


def _git(canonical: str, *args: str) -> str:
    out = subprocess.run(["git", "-C", canonical] + list(GIT_IDENTITY) + list(args), capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), out.stderr.strip()))
    return out.stdout


def copy_tree(src: str, dst: str, exclude: Optional[set] = None) -> List[str]:
    """Copy regular files and directories. Symlinks are skipped, never followed, and returned."""
    skipped: List[str] = []
    exclude = exclude or set()
    for base, dirs, files in os.walk(src):
        rel_base = os.path.relpath(base, src)
        keep = []
        for d in dirs:
            path = os.path.join(base, d)
            if d in exclude:
                continue
            if os.path.islink(path):
                skipped.append(os.path.relpath(path, src))
                continue
            keep.append(d)
        dirs[:] = keep
        target_dir = dst if rel_base == "." else os.path.join(dst, rel_base)
        os.makedirs(target_dir, exist_ok=True)
        for name in files:
            path = os.path.join(base, name)
            if os.path.islink(path):
                skipped.append(os.path.relpath(path, src))
                continue
            shutil.copy2(path, os.path.join(target_dir, name))
    return skipped


def init_canonical(canonical: str, repo: str = REPO) -> None:
    """Make the run's canonical tree: the pristine app/, an empty specs/, and a git baseline of app/ only."""
    if os.path.exists(canonical):
        shutil.rmtree(canonical)
    os.makedirs(canonical)
    copy_tree(os.path.join(repo, "app"), os.path.join(canonical, "app"), APP_EXCLUDE)
    os.makedirs(os.path.join(canonical, "specs"))
    with open(os.path.join(canonical, ".gitignore"), "w") as handle:
        handle.write("specs/\nprivate-out/\nnode_modules/\n")
    _git(canonical, "init", "-q")
    _git(canonical, "add", "-A")
    _git(canonical, "commit", "-q", "-m", "app baseline")


def build_role_dir(role: str, canonical: str, dest: str) -> Dict[str, object]:
    """Create `dest` for one role from the canonical tree. Returns what the role can see."""
    if role not in ALLOWED_TOP:
        raise ValueError("unknown role: %s" % role)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    copy_tree(os.path.join(canonical, "app"), os.path.join(dest, "app"), APP_EXCLUDE)
    if role == "planner":
        os.makedirs(os.path.join(dest, "specs"))
    if role == "builder":
        shutil.copytree(os.path.join(canonical, "specs"), os.path.join(dest, "specs"))
    if role in ("builder", "reviewer"):
        shutil.copytree(os.path.join(canonical, ".git"), os.path.join(dest, ".git"))
        shutil.copy2(os.path.join(canonical, ".gitignore"), os.path.join(dest, ".gitignore"))
    if role == "reviewer":
        os.makedirs(os.path.join(dest, "private-out"))
    verify(role, dest)
    return {"role": role, "dest": dest, "files": manifest(dest)}


def verify(role: str, workdir: str) -> None:
    """Raise unless the role directory holds nothing outside its allowed top-level entries."""
    extra = sorted(set(os.listdir(workdir)) - ALLOWED_TOP[role])
    if extra:
        raise RuntimeError("role %s directory has unexpected entries: %s" % (role, ", ".join(extra)))
    for base, dirs, files in os.walk(workdir):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in dirs + files:
            if os.path.islink(os.path.join(base, name)):
                raise RuntimeError("symlink in role directory: %s" % os.path.relpath(os.path.join(base, name), workdir))


def manifest(workdir: str) -> List[dict]:
    """Every file a role can see, with its size and sha256. Recorded in the run manifest."""
    found = []
    for base, dirs, files in os.walk(workdir):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for name in sorted(files):
            path = os.path.join(base, name)
            with open(path, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            found.append({"path": os.path.relpath(path, workdir), "bytes": os.path.getsize(path), "sha256": digest})
    return found


def _copy_markdown(src_dir: str, dst_dir: str, limit: int) -> List[str]:
    copied = []
    if not os.path.isdir(src_dir):
        return copied
    os.makedirs(dst_dir, exist_ok=True)
    for name in sorted(os.listdir(src_dir)):
        path = os.path.join(src_dir, name)
        if not name.endswith(".md") or os.path.islink(path) or not os.path.isfile(path):
            continue
        if os.path.getsize(path) > limit:
            continue
        shutil.copy2(path, os.path.join(dst_dir, name))
        copied.append(name)
    return copied


def collect(role: str, workdir: str, canonical: str, private_dest: Optional[str] = None) -> Dict[str, object]:
    """Carry a role's output back: specs/ to the canonical tree, app/ to the canonical tree, private-out/ to the vault folder."""
    result: Dict[str, object] = {"role": role, "specs": [], "private": [], "app_changed": False, "symlinks_skipped": []}
    if role == "planner":
        result["specs"] = _copy_markdown(os.path.join(workdir, "specs"), os.path.join(canonical, "specs"), MAX_SPEC_BYTES)
    elif role == "builder":
        before = {f["path"]: f["sha256"] for f in manifest(os.path.join(canonical, "app"))}
        shutil.rmtree(os.path.join(canonical, "app"))
        result["symlinks_skipped"] = copy_tree(os.path.join(workdir, "app"), os.path.join(canonical, "app"), APP_EXCLUDE)
        after = {f["path"]: f["sha256"] for f in manifest(os.path.join(canonical, "app"))}
        result["app_changed"] = before != after
        # New files are untracked, so `git diff` would not show them to the Reviewer. Intent-to-add fixes that.
        _git(canonical, "add", "-N", "app")
    elif role == "reviewer" and private_dest:
        result["private"] = _copy_markdown(os.path.join(workdir, "private-out"), private_dest, MAX_NOTE_BYTES)
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("--canonical", required=True)
    p_role = sub.add_parser("role")
    p_role.add_argument("--role", required=True, choices=sorted(ALLOWED_TOP))
    p_role.add_argument("--canonical", required=True)
    p_role.add_argument("--dest", required=True)
    p_collect = sub.add_parser("collect")
    p_collect.add_argument("--role", required=True, choices=sorted(ALLOWED_TOP))
    p_collect.add_argument("--workdir", required=True)
    p_collect.add_argument("--canonical", required=True)
    p_collect.add_argument("--private-dest")
    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--role", required=True, choices=sorted(ALLOWED_TOP))
    p_verify.add_argument("--workdir", required=True)
    args = parser.parse_args(argv)

    if args.cmd == "init":
        init_canonical(args.canonical)
        print("canonical tree ready: %s" % args.canonical)
    elif args.cmd == "role":
        info = build_role_dir(args.role, args.canonical, args.dest)
        print("%s directory ready: %s (%d files visible)" % (args.role, args.dest, len(info["files"])))
    elif args.cmd == "collect":
        print(collect(args.role, args.workdir, args.canonical, args.private_dest))
    else:
        verify(args.role, args.workdir)
        print("ok: %s directory holds only %s" % (args.role, ", ".join(sorted(ALLOWED_TOP[args.role]))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
