"""Build the prompt and the system prompt for one role in one arm.

The task text (docs/prompts/*.md) and the fixed questions (docs/questions.json) are identical in every
arm. Only the "Where the rules come from" section differs:

  neuron  the role asks Neuron the questions, verbatim
  notes   the current version of every note is pasted into the prompt, and the same questions are listed
  none    no notes and no Neuron: the same questions are listed and the role answers from the repository
"""
from __future__ import annotations

import os
from typing import List, Optional

import steps

REPO = steps.REPO


def read(rel: str, root: str = REPO) -> str:
    with open(os.path.join(root, rel)) as handle:
        return handle.read()


def read_notes(folder: str) -> List[tuple]:
    """(file name, text) for every Markdown note directly inside `folder`, sorted by name."""
    if not os.path.isdir(folder):
        return []
    notes = []
    for name in sorted(os.listdir(folder)):
        if name.endswith(".md"):
            with open(os.path.join(folder, name)) as handle:
                notes.append((name, handle.read().strip()))
    return notes


def _question_lines(questions: List[dict], arm: str) -> str:
    lines = []
    for number, question in enumerate(questions, 1):
        tag = "[%s] " % question["vault"] if steps.ARMS[arm]["neuron"] else ""
        lines.append("%d. %s%s" % (number, tag, question["text"]))
    return "\n".join(lines)


def rule_source_section(arm: str, questions: List[dict], team_notes: Optional[List[tuple]] = None,
                        private_notes: Optional[List[tuple]] = None) -> str:
    if not questions:
        return ""
    lines = _question_lines(questions, arm)
    if arm == "neuron":
        return ("## Where the rules come from\n\n"
                "The rules come from Okto Neuron. Call its ask tool once for each question below, with the question "
                "text exactly as written, include_sources true, and the vault named in square brackets. You may ask "
                "further questions only if they contain no rule value and no claim about a change.\n\n"
                "Questions:\n" + lines + "\n")
    if arm == "notes":
        parts = ["## Where the rules come from\n\n"
                 "The rules come from the notes below, which are the current version of every note at the start of "
                 "this session. Answer each question below from them.\n\n"
                 "Questions:\n" + lines + "\n\n### Team notes\n"]
        for name, text in team_notes or []:
            parts.append("#### %s\n\n%s\n" % (name, text))
        if any(q["vault"] == steps.PRIVATE_VAULT for q in questions):
            parts.append("\n### Your private notes\n")
            for name, text in private_notes or []:
                parts.append("#### %s\n\n%s\n" % (name, text))
        return "\n".join(parts)
    if arm == "none":
        return ("## Where the rules come from\n\n"
                "No notes and no memory service are available to you. Answer each question below from the repository "
                "if the repository answers it. If it does not, say that you do not know and state the assumption you "
                "make.\n\nQuestions:\n" + lines + "\n")
    raise ValueError("unknown arm: %s" % arm)


def build_prompt(arm: str, prompt_path: str, vault_dir: str, private_dir: str) -> str:
    task = read(prompt_path).strip()
    questions = steps.questions_for(prompt_path)
    team = read_notes(vault_dir) if arm == "notes" else None
    private = read_notes(private_dir) if arm == "notes" else None
    section = rule_source_section(arm, questions, team, private)
    return task + ("\n\n" + section if section else "") + "\n"


def build_system_prompt(arm: str, role: str) -> str:
    spec = steps.ROLES[role]
    parts = [read(spec["claude_md"]).strip(), read(steps.COMMON_MD).strip()]
    if steps.ARMS[arm]["neuron"]:
        parts += [read(spec["neuron_md"]).strip(), read(steps.NEURON_SKILL_MD).strip()]
    return "\n\n".join(parts) + "\n"
