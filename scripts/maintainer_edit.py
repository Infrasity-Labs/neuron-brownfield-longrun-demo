#!/usr/bin/env python3
"""The Maintainer's own actions: the two rule changes and the scripted model outage.

A rule change is a copy of the files under scenarios/<step>/after/ into the watched vault/ folder. The starting
state of every note is committed in vault/ itself (and in scenarios/<step>/before/ for the notes that change),
so a fresh clone starts before the change and `python3 scripts/reset.py` goes back to it.

  python3 scripts/maintainer_edit.py step4      edit window changes (scenarios/step04/after/)
  python3 scripts/maintainer_edit.py step7      error rule replaced, ops-runbook.md added (scenarios/step07/after/)
  python3 scripts/maintainer_edit.py step9      break the isolated daemon's model key, hold, restore in a finally block

Each edit is recorded as a maintainer_edit event with a UTC timestamp when --events is given.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import events as event_log  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENARIOS = os.path.join(REPO, "scenarios")
VAULT = os.path.join(REPO, "vault")

SCENARIO_DIRS: Dict[str, str] = {"step4": "step04", "step7": "step07"}


def scenario_files(action: str, scenarios: str = SCENARIOS) -> List[str]:
    folder = os.path.join(scenarios, SCENARIO_DIRS[action], "after")
    return sorted(n for n in os.listdir(folder) if n.endswith(".md"))


def apply_scenario(action: str, vault: str = VAULT, scenarios: str = SCENARIOS) -> List[str]:
    """Copy the post-change notes of one step into the vault folder. Returns the file names written."""
    folder = os.path.join(scenarios, SCENARIO_DIRS[action], "after")
    written = scenario_files(action, scenarios)
    for name in written:
        shutil.copyfile(os.path.join(folder, name), os.path.join(vault, name))
    return written


def edit(action: str, vault: str = VAULT, scenarios: str = SCENARIOS, events_path: Optional[str] = None) -> List[str]:
    written = apply_scenario(action, vault, scenarios)
    label = action
    if events_path:
        event_log.log_event(events_path, "maintainer_edit", label=label, step=int(action[-1]), files=written)
    for name in written:
        print("wrote vault/%s" % name)
    return written


def step9(hold: float, key_env: str, events_path: Optional[str] = None) -> None:
    """Break the model key of the isolated daemon for `hold` seconds, and always restore it."""
    import neuron_ctl
    with neuron_ctl.outage(key_env, events_path):
        print("isolated daemon restarted with an invalid key on port %d; holding %.0f s" % (neuron_ctl.rest_port(), hold))
        time.sleep(hold)
    print("daemon restored with the saved key")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["step4", "step7", "step9"])
    parser.add_argument("--vault", default=VAULT, help="the watched notes folder (default: vault/)")
    parser.add_argument("--events", help="append a maintainer_edit event to this events.jsonl")
    parser.add_argument("--hold", type=float, default=60.0, help="step9 only: seconds to keep the outage up")
    parser.add_argument("--key-env", default=os.environ.get("DEMO_LLM_API_KEY_ENV", "OKTO_NEURON_LLM_API_KEY"))
    args = parser.parse_args(argv)
    if args.action == "step9":
        step9(args.hold, args.key_env, args.events)
    else:
        edit(args.action, args.vault, SCENARIOS, args.events)
    return 0


if __name__ == "__main__":
    sys.exit(main())
