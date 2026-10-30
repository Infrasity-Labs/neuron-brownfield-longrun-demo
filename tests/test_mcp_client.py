import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import helpers  # noqa: F401
import mcp_client as mc
import state_probe as sp


class FakeNeuron(BaseHTTPRequestHandler):
    """A local fake MCP server: JSON for initialize, 202 for the notification, an event stream for tools/call."""
    seen = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeNeuron.seen.append({"auth": self.headers.get("Authorization"), "session": self.headers.get("Mcp-Session-Id"),
                                "accept": self.headers.get("Accept"), "method": body.get("method")})
        if body["method"] == "initialize":
            payload = json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": {"protocolVersion": mc.PROTOCOL_VERSION}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Mcp-Session-Id", "session-123")
        elif body["method"] == "notifications/initialized":
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        else:
            args = body["params"]["arguments"]
            if body["params"]["name"] == "ask":
                text = json.dumps({"text": "The comment edit window is 15 minutes.", "sources": []})
            else:
                text = json.dumps({"topic": args.get("topic"), "claims": [{"predicate": "replaces"}]})
            message = {"jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": text}]}}
            payload = ("event: message\ndata: " + json.dumps({"jsonrpc": "2.0", "method": "notifications/progress"}) +
                       "\n\nevent: message\ndata: " + json.dumps(message) + "\n\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class Client(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeNeuron)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:%d/mcp" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeNeuron.seen = []

    def test_parse_json_and_event_stream_bodies(self):
        self.assertEqual(mc.parse_response('{"id": 2, "result": 1}', "application/json", 2)["result"], 1)
        stream = 'data: {"method": "x"}\n\ndata: {"id": 7, "result": "ok"}\n\n'
        self.assertEqual(mc.parse_response(stream, "text/event-stream", 7)["result"], "ok")
        self.assertIsNone(mc.parse_response("", "application/json", 1))
        with self.assertRaises(mc.McpError):
            mc.parse_response('{"id": 3}', "application/json", 9)

    def test_initialize_then_call_sends_bearer_session_and_accept_headers(self):
        client = mc.McpClient(self.url, "secret-token")
        text = client.call_tool("ask", {"question": "q", "vault": "team", "include_sources": True})
        self.assertEqual(json.loads(text)["text"], "The comment edit window is 15 minutes.")
        self.assertEqual([s["method"] for s in FakeNeuron.seen], ["initialize", "notifications/initialized", "tools/call"])
        self.assertTrue(all(s["auth"] == "Bearer secret-token" for s in FakeNeuron.seen))
        self.assertEqual(FakeNeuron.seen[2]["session"], "session-123")
        self.assertIn("text/event-stream", FakeNeuron.seen[0]["accept"])

    def test_the_probe_stores_raw_results_and_derives_plain_booleans(self):
        run_dir = tempfile.mkdtemp()
        events = run_dir + "/events.jsonl"
        summary = sp.probe(mc.McpClient(self.url, "t"), "edit-window", "step4", 4, run_dir, events)
        self.assertTrue(summary["ask_text_matches_old"])
        self.assertFalse(summary["ask_text_matches_new"])
        self.assertTrue(summary["old_value_still_returned"])
        self.assertTrue(summary["supersedes_marker_seen"] is False)  # "replaces" is not the word "supersed"
        for raw in summary["raw"]:
            with open(run_dir + "/" + raw) as handle:
                json.loads(handle.read())
        with open(events) as handle:
            self.assertEqual(json.loads(handle.readline())["event"], "state_probe")

    def test_the_probe_question_is_the_neutral_fixed_one(self):
        question = sp._question("edit-window")
        self.assertEqual(question, "How long after a comment is created may it still be edited?")

    def test_derive_flags_the_word_supersede_and_the_new_value(self):
        ask = json.dumps({"text": "30 minutes now. The 15 minutes value was superseded."})
        fields = sp.derive("edit-window", ask, "{}")
        self.assertTrue(fields["supersedes_marker_seen"])
        self.assertTrue(fields["ask_text_matches_new"] and fields["ask_text_matches_old"])


if __name__ == "__main__":
    unittest.main()
