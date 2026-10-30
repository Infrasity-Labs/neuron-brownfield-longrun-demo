"""The ten steps of the demo, the three arms and the three roles, in one place.

run_demo.py, the checkers and the tests all read this file.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NEURON_TOOLS = [
    "mcp__okto-neuron__ask",
    "mcp__okto-neuron__explore",
    "mcp__okto-neuron__list_vaults",
]

# The three arms of the comparison. The prompts, the model, the turn limit and the tool limits are the
# same in every arm. Only the rule source differs.
ARMS: Dict[str, dict] = {
    "none": {"label": "A", "memory": "no memory: no notes and no Neuron", "neuron": False, "notes_in_prompt": False},
    "notes": {"label": "B", "memory": "the current notes are pasted into each prompt", "neuron": False, "notes_in_prompt": True},
    "neuron": {"label": "C", "memory": "Okto Neuron (ask, explore, list_vaults)", "neuron": True, "notes_in_prompt": False},
}
DEFAULT_ARM = "neuron"

# Every role runs in its own clean working directory (scripts/build_workdir.py). Nothing but app/, the
# spec channel and the reviewer's private-out/ exists there, so note files cannot be read with Read, Grep,
# Glob or git. `builtin_tools` is passed to `claude --tools`, which removes every other built-in tool
# (no web tools, no sub-agents). `allowed` is passed to `--allowedTools`. Neuron's MCP tools are added to
# `allowed` in arm C only.
ROLES: Dict[str, dict] = {
    "planner": {
        "claude_md": "agents/planner/CLAUDE.md",
        "neuron_md": "agents/planner/neuron.md",
        # Pinned to the team vault at the connection, so the Planner cannot read the private one.
        "mcp_vault_query": "team",
        "builtin_tools": ["Read", "Grep", "Glob", "Write"],
        "allowed": ["Read(./**)", "Grep", "Glob", "Edit(specs/**)"],
        "writes": "specs",
    },
    "builder": {
        "claude_md": "agents/builder/CLAUDE.md",
        "neuron_md": "agents/builder/neuron.md",
        "mcp_vault_query": "team",
        "builtin_tools": ["Read", "Grep", "Glob", "Edit", "Write", "Bash"],
        "allowed": ["Read(./**)", "Grep", "Glob", "Edit(app/**)", "Bash(git diff*)", "Bash(git status*)"],
        "writes": "app",
    },
    "reviewer": {
        "claude_md": "agents/reviewer/CLAUDE.md",
        "neuron_md": "agents/reviewer/neuron.md",
        # No selector on the connection: the Reviewer names the vault on each call. This is a prompt rule.
        "mcp_vault_query": None,
        "builtin_tools": ["Read", "Grep", "Glob", "Write", "Bash"],
        "allowed": ["Read(./**)", "Grep", "Glob", "Edit(private-out/**)", "Bash(git diff*)", "Bash(git status*)",
                    "Bash(git log*)", "Bash(git show*)"],
        "writes": "private-out",
    },
}

COMMON_MD = "agents/common.md"
NEURON_SKILL_MD = "agents/neuron-skill.md"


def allowed_tools(role: str, arm: str) -> List[str]:
    return list(ROLES[role]["allowed"]) + (NEURON_TOOLS if ARMS[arm]["neuron"] else [])


# kind: "setup" (Maintainer script), "agents" (one or more role runs), "closeout" (script only).
# maintainer: an action in scripts/maintainer_edit.py that runs BEFORE the role runs.
# neuron_only: the step needs the Neuron daemon and is skipped in the arms that have none.
STEPS: List[dict] = [
    {"id": 1, "title": "Install the pinned Neuron, create both vaults, load the 13 starting notes", "kind": "setup", "runs": []},
    {"id": 2, "title": "Planner gathers the rules for feature 1 (comment editing) and writes the spec", "kind": "agents",
     "runs": [("planner", "docs/prompts/02-planner.md")]},
    {"id": 3, "title": "Builder adds the edit endpoint and the edit marker migration", "kind": "agents",
     "runs": [("builder", "docs/prompts/03-builder.md")]},
    {"id": 4, "title": "Maintainer changes the edit window; a fresh Reviewer checks the diff", "kind": "agents",
     "maintainer": "step4", "runs": [("reviewer", "docs/prompts/04-reviewer.md")]},
    {"id": 5, "title": "A fresh Builder checks the change against the current rules; Reviewer reviews it and logs a private finding",
     "kind": "agents",
     "runs": [("builder", "docs/prompts/05-builder.md"), ("reviewer", "docs/prompts/05-reviewer.md")]},
    {"id": 6, "title": "Feature 2, the article list limit cap, planned, built and reviewed", "kind": "agents",
     "runs": [("planner", "docs/prompts/06-planner.md"), ("builder", "docs/prompts/06-builder.md"),
              ("reviewer", "docs/prompts/06-reviewer.md")]},
    {"id": 7, "title": "Maintainer replaces the error response rule and adds ops-runbook.md", "kind": "agents",
     "maintainer": "step7", "runs": []},
    {"id": 8, "title": "Feature 3, soft delete for comments, planned, built and reviewed", "kind": "agents",
     "runs": [("planner", "docs/prompts/08-planner.md"), ("builder", "docs/prompts/08-builder.md"),
              ("reviewer", "docs/prompts/08-reviewer.md")]},
    {"id": 9, "title": "Model outage made by the script: the Reviewer's asks hit a provider error", "kind": "agents",
     "maintainer": "step9", "neuron_only": True, "runs": [("reviewer", "docs/prompts/09-reviewer.md")]},
    {"id": 10, "title": "Close-out: total the run, verify every citation, run the isolation and outcome checks", "kind": "closeout",
     "runs": []},
]

# Rules that the Maintainer replaces. Used by closeout.py to look for a stale rule still being followed.
# old and new are regular expressions matched against an answer's text. This is a heuristic, see README.
REPLACEMENTS = [
    {"id": "edit-window", "step": 4, "old": r"\b15[- ]?minutes?\b", "new": r"\b30[- ]?minutes?\b"},
    {"id": "error-response", "step": 7, "old": r"\"errors\"\s*:", "new": r"\"error\"\s*:\s*\{"},
]

# Vault names, never paths, in anything an agent sees.
TEAM_VAULT = "team"
PRIVATE_VAULT = "reviewer-private"
# A third vault that exists only for the negative test, see docs/prompts/negative/.
DECOY_VAULT = "decoy"


def prompt_key(prompt_path: str) -> str:
    """docs/prompts/02-planner.md -> 02-planner"""
    return os.path.splitext(os.path.basename(prompt_path))[0]


def load_questions(path: str = os.path.join(REPO, "docs", "questions.json")) -> Dict[str, List[dict]]:
    with open(path) as handle:
        return json.load(handle)["steps"]


def questions_for(prompt_path: str) -> List[dict]:
    return load_questions().get(prompt_key(prompt_path), [])
