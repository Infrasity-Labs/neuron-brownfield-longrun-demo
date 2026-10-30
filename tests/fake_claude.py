#!/usr/bin/env python3
"""A stand-in for the claude CLI, used only by tests/test_run_demo_offline.py. It calls no model.

It reads the same flags run_demo.py passes, writes a stream-json transcript to stdout in the shape Claude Code writes
(an init event with the working directory, tool_use and tool_result blocks, a result event), and makes the file change
that the role's directory allows: the Planner writes a spec, the Builder edits app/, the Reviewer writes private-out/.
FAKE_CLAUDE_LEAK=1 makes it also Read a note path, to prove the isolation check fails the run.
"""
import json
import os
import sys

if "--version" in sys.argv:
    print("9.9.9 (Claude Code)")
    sys.exit(0)

argv = sys.argv
prompt = argv[argv.index("-p") + 1]
system = argv[argv.index("--append-system-prompt") + 1]
cwd = os.getcwd()
role = "planner" if "Role: Planner" in system else "builder" if "Role: Builder" in system else "reviewer"


def emit(event):
    print(json.dumps(event), flush=True)


def tool(use_id, name, **inp):
    emit({"type": "assistant", "timestamp": "2026-11-01T10:00:00.000Z",
          "message": {"content": [{"type": "tool_use", "id": use_id, "name": name, "input": inp}]}})
    emit({"type": "user", "timestamp": "2026-11-01T10:00:01.000Z",
          "message": {"content": [{"type": "tool_result", "tool_use_id": use_id, "content": "ok"}]}})


emit({"type": "system", "subtype": "init", "cwd": cwd, "claude_code_version": "9.9.9", "model": "fake-model"})
tool("t1", "Read", file_path=os.path.join(cwd, "app", "src", "main.ts"))
if role == "planner":
    os.makedirs("specs", exist_ok=True)
    with open("specs/feature.md", "w") as handle:
        handle.write("# Spec\n\nRules: the edit rule, the error rule. Values come from the rule source.\n")
        if os.environ.get("FAKE_CLAUDE_SPEC_VALUE") == "1":
            handle.write("Add a nullable editedAt column.\n")
    tool("t2", "Write", file_path="specs/feature.md")
elif role == "builder":
    with open("app/src/main.ts", "a") as handle:
        handle.write("\n// builder was here\n")
    tool("t2", "Edit", file_path="app/src/main.ts")
else:
    os.makedirs("private-out", exist_ok=True)
    with open("private-out/finding.md", "w") as handle:
        handle.write("# Finding\n\nA private finding written by the fake reviewer.\n")
    tool("t2", "Write", file_path="private-out/finding.md")
if os.environ.get("FAKE_CLAUDE_LEAK") == "1":
    tool("t3", "Read", file_path="vault/policy-edit-window.md")
emit({"type": "result", "subtype": "success", "result": "NOT APPROVED. fake report for %s" % role})
