"""Shared test helpers. Python 3.9, standard library only."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FIXTURES = os.path.join(HERE, "fixtures")
sys.path.insert(0, os.path.join(REPO, "scripts"))


def load_fixture(name):
    with open(os.path.join(FIXTURES, name)) as handle:
        return json.load(handle)


TEAM_ROOT = os.path.join(FIXTURES, "vaults", "team")


def transcript_for(response, tool_name="mcp__okto-neuron__ask", request=None, followup="Done."):
    """Wrap a response in the stream-json shape Claude Code writes. The wrapper is synthetic."""
    request = request or {"question": "q", "vault": "team", "include_sources": True}
    return [
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": tool_name, "input": request}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": json.dumps(response)}]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": followup}]}},
    ]


def write_jsonl(path, events):
    with open(path, "w") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")
