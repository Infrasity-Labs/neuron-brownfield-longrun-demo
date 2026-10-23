#!/usr/bin/env python3
"""The Maintainer's own actions: the two rule changes and the model outage. Edits files in vault/ only."""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

VAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vault")

EDIT_WINDOW_30 = """# Edit window (demo policy)

This is a demo policy for this repo, not behaviour of the app.

A comment author may edit their own comment for 30 minutes after the comment was created. After that the API refuses the edit.
"""

ERROR_RULE_NEW = """# Error response rule (demo policy)

This is a demo policy for this repo, not behaviour of the app.

All new error responses use an error object: {"error":{"code":"<machine_code>","message":"<text>"}}. This replaces the older errors-by-field body. HTTP status codes do not change.
"""

OPS_RUNBOOK = """# Ops runbook

When an API call fails, support reads the errors key in the response body. It maps each field name to a list of messages, for example {"errors":{"body":["can't be blank"]}}. New error responses should follow this shape.
"""


def _write(name: str, text: str) -> None:
    with open(os.path.join(VAULT, name), "w") as handle:
        handle.write(text)
    print("wrote vault/%s" % name)


def step4() -> None:
    _write("policy-edit-window.md", EDIT_WINDOW_30)


def step7() -> None:
    _write("policy-error-response.md", ERROR_RULE_NEW)
    _write("ops-runbook.md", OPS_RUNBOOK)


def step9() -> None:
    print("Stop the model endpoint now so every ask returns provider_error.")
    print("A local endpoint: stop its server. A hosted one: disconnect the network or set a bad key.")
    print("Neuron's README does not document a switch for this, so it is done by hand and recorded in docs/VERIFIED.md.")


ACTIONS = {"step4": step4, "step7": step7, "step9": step9}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=sorted(ACTIONS))
    ACTIONS[parser.parse_args(argv).action]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
