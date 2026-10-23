"""The ten steps of the demo, in one place. run_demo.py and the tests both read this."""
from __future__ import annotations

import os
from typing import Dict, List

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NEURON_TOOLS = [
    "mcp__okto-neuron__ask",
    "mcp__okto-neuron__explore",
    "mcp__okto-neuron__list_vaults",
]

# Tool permissions are passed to `claude -p --allowedTools`. The Planner and Reviewer cannot run code.
ROLES: Dict[str, dict] = {
    "planner": {
        "claude_md": "agents/planner/CLAUDE.md",
        # Pinned to the team vault at the connection, so the Planner cannot read the private one.
        "mcp_vault_query": "team",
        "tools": NEURON_TOOLS + ["Read", "Grep", "Glob", "Bash(ls*)", "Bash(wc *)", "Edit(vault/specs/**)"],
    },
    "builder": {
        "claude_md": "agents/builder/CLAUDE.md",
        "mcp_vault_query": "team",
        "tools": NEURON_TOOLS
        + ["Read", "Grep", "Glob", "Edit(app/**)", "Bash(npx nx test api*)", "Bash(cd app && npx nx test api*)",
           "Bash(npx prisma *)", "Bash(cd app && npx prisma *)", "Bash(git diff*)", "Bash(git status*)",
           "Bash(ls*)", "Bash(wc *)"],
    },
    "reviewer": {
        "claude_md": "agents/reviewer/CLAUDE.md",
        # No selector on the connection: the Reviewer names the vault on each call.
        "mcp_vault_query": None,
        "tools": NEURON_TOOLS
        + ["Read", "Grep", "Glob", "Bash(git diff*)", "Bash(git -C * diff*)", "Bash(git status*)", "Bash(git log*)",
           "Bash(git show*)", "Bash(ls*)", "Edit(vault-private/**)"],
    },
}

# kind: "setup" (Maintainer script), "agents" (one or more role runs), "closeout" (script only).
# maintainer: an action in scripts/maintainer_edit.py that runs BEFORE the role runs.
STEPS: List[dict] = [
    {"id": 1, "title": "Install Neuron, create both vaults, load the 14 notes", "kind": "setup", "runs": []},
    {"id": 2, "title": "Planner asks the rules for feature 1 (comment editing) and writes the spec", "kind": "agents",
     "runs": [("planner", "docs/prompts/02-planner.md")]},
    {"id": 3, "title": "Builder adds the edit endpoint and the editedAt migration", "kind": "agents",
     "runs": [("builder", "docs/prompts/03-builder.md")]},
    {"id": 4, "title": "Maintainer changes the edit window to 30 minutes; a fresh Reviewer checks the diff", "kind": "agents",
     "maintainer": "step4", "runs": [("reviewer", "docs/prompts/04-reviewer.md")]},
    {"id": 5, "title": "A fresh Builder fixes the window; Reviewer approves and logs a private finding", "kind": "agents",
     "runs": [("builder", "docs/prompts/05-builder.md"), ("reviewer", "docs/prompts/05-reviewer.md")]},
    {"id": 6, "title": "Feature 2, the article list limit cap, planned, built and reviewed", "kind": "agents",
     "runs": [("planner", "docs/prompts/06-planner.md"), ("builder", "docs/prompts/06-builder.md"),
              ("reviewer", "docs/prompts/06-reviewer.md")]},
    {"id": 7, "title": "Maintainer replaces the error response rule and adds ops-runbook.md", "kind": "agents",
     "maintainer": "step7", "runs": []},
    {"id": 8, "title": "Feature 3, soft delete for comments, built to the new error rule and reviewed", "kind": "agents",
     "runs": [("planner", "docs/prompts/08-planner.md"), ("builder", "docs/prompts/08-builder.md"),
              ("reviewer", "docs/prompts/08-reviewer.md")]},
    {"id": 9, "title": "Model endpoint stopped: agents report provider_error and fall back to explore", "kind": "agents",
     "maintainer": "step9", "runs": [("reviewer", "docs/prompts/09-reviewer.md")]},
    {"id": 10, "title": "Close-out: total the run and verify every citation", "kind": "closeout", "runs": []},
]

# Rules that the Maintainer replaces. Used by closeout.py to look for a stale rule still being followed.
# old and new are regular expressions matched against an answer's text. This is a heuristic, see README.
REPLACEMENTS = [
    {"id": "edit-window", "step": 4, "old": r"\b15[- ]?minutes?\b", "new": r"\b30[- ]?minutes?\b"},
    {"id": "error-response", "step": 7, "old": r"\"errors\"\s*:", "new": r"\"error\"\s*:\s*\{"},
]

# Where each role's notes and the vaults live. Names only, never paths, in anything an agent sees.
TEAM_VAULT = "team"
PRIVATE_VAULT = "reviewer-private"
