#!/usr/bin/env python3
"""Start, stop and break an isolated Okto Neuron daemon.

The demo never touches the user's own Neuron install. It runs its own daemon with:

  HOME                 a separate folder (default <repo>/.demo-home, git-ignored). Neuron's app home is
                       ~/.okto-neuron, so its vaults, saved key, runtime files and token live in there.
  --port / --mcp-port  non-default ports (default 17777 and 18201)
  OKTO_NEURON_ENDPOINT lets the `okto-neuron` CLI (status, ask, watch-folder) find that daemon

Sources for each point: the `serve --port` and `--mcp-port` options, the `OKTO_NEURON_ENDPOINT` variable and the
`~/.okto-neuron/daemon-<rest port>.token` path are in the public source of okto-neuron 0.3.1
(src/okto_neuron/cli/__init__.py, cli/_client.py, server/runtime.py), not in its README. docs/NEURON-USAGE.md lists
every command and path this repository uses with its source.

  python3 scripts/neuron_ctl.py version          check okto-neuron --version against pins.json
  python3 scripts/neuron_ctl.py start | stop | status
  python3 scripts/neuron_ctl.py outage --hold 60 start a daemon with an invalid key, then restore it
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Dict, Iterator, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import events as event_log  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INVALID_KEY = "invalid-demo-outage-key"


def load_pins(path: str = os.path.join(REPO, "pins.json")) -> dict:
    with open(path) as handle:
        return json.load(handle)


def demo_home() -> str:
    return os.path.abspath(os.environ.get("DEMO_NEURON_HOME", os.path.join(REPO, ".demo-home")))


def rest_port() -> int:
    return int(os.environ.get("DEMO_NEURON_REST_PORT", "17777"))


def mcp_port() -> int:
    return int(os.environ.get("DEMO_NEURON_MCP_PORT", "18201"))


def mcp_url() -> str:
    return "http://127.0.0.1:%d/mcp" % mcp_port()


def token_file() -> str:
    return os.path.join(demo_home(), ".okto-neuron", "daemon-%d.token" % rest_port())


def vaults_dir() -> str:
    return os.path.join(demo_home(), ".okto-neuron", "vaults")


def neuron_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """The environment for every okto-neuron command of the demo: isolated HOME, our endpoint, no browser."""
    env = dict(os.environ)
    env["HOME"] = demo_home()
    env["OKTO_NEURON_ENDPOINT"] = "http://127.0.0.1:%d" % rest_port()
    env["OKTO_NEURON_NO_OPEN"] = "1"
    env["OKTO_NEURON_VAULTS_DIR"] = vaults_dir()
    # scripts/install_neuron.sh installs the pinned release here; it wins over an install of your own on PATH.
    env["PATH"] = os.path.join(demo_home(), "tool", "bin") + os.pathsep + env.get("PATH", "")
    if extra:
        env.update(extra)
    return env


VERSION_LINE = re.compile(r"\b(\d+\.\d+\.\d+(?:[.\w+-]*)?)\b")


def parse_version(output: str) -> Optional[str]:
    """The version in the first line of `okto-neuron --version` ("okto-neuron 0.3.1"), or None."""
    first = output.strip().splitlines()[0] if output.strip() else ""
    match = VERSION_LINE.search(first)
    return match.group(1) if match else None


def installed_version(binary: str = "okto-neuron") -> Optional[str]:
    try:
        out = subprocess.run([binary, "--version"], capture_output=True, text=True, env=neuron_env(), timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_version(out.stdout) if out.returncode == 0 else None


def require_version(expected: str, binary: str = "okto-neuron") -> str:
    """Return the installed version, or raise when it is missing or differs from `expected`."""
    found = installed_version(binary)
    if found is None:
        raise RuntimeError("could not read the version from `%s --version`" % binary)
    if found != expected:
        raise RuntimeError("okto-neuron is %s but this demo is pinned to %s (pins.json)" % (found, expected))
    return found


INGEST_COUNTS = re.compile(r"Ingest:\s+(?:idle|active)\s+\((\d+)/(\d+) terminal")


def parse_ingest_counts(status_output: str) -> Optional[tuple]:
    """(terminal, total) from the `Ingest:` line of `okto-neuron status`, or None. Seen in 0.3.1: `active (20/22 terminal,
    1 processing, 1 queued)` and `idle (22/22 terminal, 0 processing, 0 queued)`. `total` grows when the folder watcher
    queues a file, which is how the demo knows that an edit has been picked up before it waits for the queue to empty."""
    match = INGEST_COUNTS.search(status_output)
    return (int(match.group(1)), int(match.group(2))) if match else None


def ingest_counts(env: Optional[Dict[str, str]] = None) -> Optional[tuple]:
    out = subprocess.run(["okto-neuron", "status"], env=env or neuron_env(), capture_output=True, text=True)
    return parse_ingest_counts(out.stdout)


def _run(args: List[str], env: Dict[str, str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, env=env, capture_output=True, text=True, check=check)


def stop(env: Optional[Dict[str, str]] = None) -> None:
    _run(["okto-neuron", "stop"], env or neuron_env(), check=False)


def reset_state(env: Optional[Dict[str, str]] = None) -> None:
    """Stop the isolated daemon and delete its whole app home, so a run starts from an empty graph.

    Without this, run 2 of `--runs 5` would start on the vaults run 1 left behind (its graph already holds run 1's
    claims and supersession edges for notes that reset.py then restores). The pinned install under <home>/tool stays.
    Only the demo's own isolated home is touched: a safety check refuses any folder that is not named .okto-neuron
    inside demo_home(), and demo_home() itself is never the real home.
    """
    home = demo_home()
    if os.path.realpath(home) == os.path.realpath(os.path.expanduser("~")):
        raise RuntimeError("refusing to reset state: DEMO_NEURON_HOME is the real home")
    stop(env)
    shutil.rmtree(os.path.join(home, ".okto-neuron"), ignore_errors=True)


def start(env: Optional[Dict[str, str]] = None, wait_s: float = 90.0) -> None:
    env = env or neuron_env()
    _run(["okto-neuron", "serve", "--daemon", "--no-open", "--port", str(rest_port()), "--mcp-port", str(mcp_port())], env)
    deadline = time.time() + wait_s
    while time.time() < deadline:
        out = _run(["okto-neuron", "status"], env, check=False)
        if out.returncode == 0:
            return
        time.sleep(2)
    raise RuntimeError("daemon did not report status within %.0f s" % wait_s)


@contextlib.contextmanager
def outage(key_env: str, events_path: Optional[str] = None) -> Iterator[None]:
    """Restart the isolated daemon with an invalid key for the duration of the block, then restore it.

    The daemon reads its saved key from ~/.okto-neuron/env only at start, and a variable in the daemon's
    own environment overrides it (that is how the pilot made its outage). Restoring happens in `finally`,
    so an exception or a Ctrl-C inside the block still brings back a working daemon.
    """
    stop()
    start(neuron_env({key_env: INVALID_KEY}))
    if events_path:
        event_log.log_event(events_path, "outage_start", key_env=key_env)
    try:
        yield
    finally:
        stop()
        start(neuron_env())
        if events_path:
            event_log.log_event(events_path, "outage_end", key_env=key_env)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["version", "start", "stop", "status", "outage"])
    parser.add_argument("--hold", type=float, default=60.0, help="seconds to keep the outage up (outage only)")
    parser.add_argument("--key-env", default=os.environ.get("DEMO_LLM_API_KEY_ENV", "OKTO_NEURON_LLM_API_KEY"))
    args = parser.parse_args(argv)
    if args.action == "version":
        expected = load_pins()["neuron"]["version"]
        print("okto-neuron %s (pinned %s)" % (require_version(expected), expected))
    elif args.action == "start":
        start()
    elif args.action == "stop":
        stop()
    elif args.action == "status":
        out = _run(["okto-neuron", "status"], neuron_env(), check=False)
        print(out.stdout.strip() or out.stderr.strip())
        return out.returncode
    else:
        with outage(args.key_env):
            print("outage up for %.0f s on port %d" % (args.hold, rest_port()))
            time.sleep(args.hold)
        print("daemon restored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
