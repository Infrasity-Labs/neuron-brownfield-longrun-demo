#!/usr/bin/env python3
"""A minimal MCP client over streamable HTTP, standard library only.

Used by scripts/state_probe.py to ask Neuron a question without a model session in between: initialize, send the
`initialized` notification, then `tools/call`. The server may answer a POST with plain JSON or with a
`text/event-stream` body holding one `data:` event per message, so both are parsed. The bearer token is read from
a file and is never printed.

Status: the framing follows the MCP streamable-HTTP transport. It is tested against a local fake server in
tests/test_mcp_client.py, and it ran against live Neuron 0.3.1 daemons on 2026-10-29 (state probes of all 5 Neuron-arm runs).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

PROTOCOL_VERSION = "2025-03-26"


class McpError(RuntimeError):
    pass


def parse_response(body: str, content_type: str, request_id: Optional[int]) -> Optional[dict]:
    """The JSON-RPC message answering `request_id` from a JSON or event-stream body. None for an empty body."""
    body = body.strip()
    if not body:
        return None
    if "text/event-stream" in content_type:
        messages = []
        for block in body.replace("\r\n", "\n").split("\n\n"):
            data = "\n".join(line[5:].lstrip() for line in block.split("\n") if line.startswith("data:"))
            if data.strip():
                messages.append(json.loads(data))
    else:
        parsed = json.loads(body)
        messages = parsed if isinstance(parsed, list) else [parsed]
    for message in messages:
        if request_id is None or message.get("id") == request_id:
            return message
    raise McpError("no response with id %s in %d message(s)" % (request_id, len(messages)))


class McpClient:
    def __init__(self, url: str, token: str, timeout: float = 300.0) -> None:
        self.url = url
        self._token = token
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self._next_id = 0

    def _post(self, payload: dict, expect_id: Optional[int]) -> Optional[dict]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer " + self._token,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        request = urllib.request.Request(self.url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                session = response.headers.get("Mcp-Session-Id")
                if session:
                    self.session_id = session
                body = response.read().decode("utf-8")
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as error:
            raise McpError("HTTP %d from %s" % (error.code, self.url))
        return parse_response(body, content_type, expect_id)

    def initialize(self) -> dict:
        self._next_id += 1
        message = self._post({"jsonrpc": "2.0", "id": self._next_id, "method": "initialize", "params": {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "neuron-demo-probe", "version": "1"}}}, self._next_id)
        if not message or "error" in message:
            raise McpError("initialize failed: %s" % (message,))
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, None)
        return message["result"]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool and return the text of its result. Raises McpError on a JSON-RPC error or isError."""
        if self.session_id is None and self._next_id == 0:
            self.initialize()
        self._next_id += 1
        message = self._post({"jsonrpc": "2.0", "id": self._next_id, "method": "tools/call",
                              "params": {"name": name, "arguments": arguments}}, self._next_id)
        if not message:
            raise McpError("empty response to tools/call")
        if "error" in message:
            raise McpError("tools/call error: %s" % (message["error"],))
        result = message.get("result") or {}
        text = "".join(part.get("text", "") for part in result.get("content", []) if isinstance(part, dict))
        if result.get("isError"):
            raise McpError("tool reported an error: %s" % text[:300])
        return text
