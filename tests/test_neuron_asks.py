import copy
import os
import tempfile
import unittest

import helpers
import neuron_asks as na


class RecordAsks(unittest.TestCase):
    def _record(self, response, **kw):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "t.jsonl")
        helpers.write_jsonl(path, helpers.transcript_for(response, **kw))
        calls = na.extract_calls(path)
        self.assertEqual(len(calls), 1)
        return na.build_ask_record(calls[0], 2, "planner", {"team": helpers.TEAM_ROOT})

    def test_ok_answer_is_recorded_and_citations_verified(self):
        rec = self._record(helpers.load_fixture("ask_ok.json"))
        self.assertEqual(rec["synthesis_status"], "ok")
        self.assertEqual(rec["finish_reason"], "stop")
        self.assertEqual(rec["status"], "ok")
        self.assertEqual(len(rec["sources"]), 2)
        self.assertTrue(all(c["ok"] for c in rec["citation_checks"]))
        self.assertIsNone(rec["vault_override_ignored"])
        self.assertEqual(rec["agent_followup"], "Done.")

    def test_provider_error_is_recorded_with_its_status(self):
        rec = self._record(helpers.load_fixture("ask_provider_error.json"))
        self.assertEqual(rec["synthesis_status"], "provider_error")
        self.assertEqual(rec["status"], "degraded")
        self.assertEqual(rec["text"], "")
        self.assertIsNone(rec["finish_reason"])

    def test_vault_override_ignored_is_recorded(self):
        # synthetic: the real fixtures never carried this field, so it is added by hand here
        response = copy.deepcopy(helpers.load_fixture("ask_ok.json"))
        response["vault_override_ignored"] = {"requested": "reviewer-private", "used": "team"}
        rec = self._record(response)
        self.assertEqual(rec["vault_override_ignored"], {"requested": "reviewer-private", "used": "team"})

    def test_unparsable_result_keeps_a_status(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "t.jsonl")
        events = helpers.transcript_for({})
        events[1]["message"]["content"][0]["content"] = "not json"
        helpers.write_jsonl(path, events)
        rec = na.build_ask_record(na.extract_calls(path)[0], 2, "planner")
        self.assertEqual(rec["synthesis_status"], "unparsed")

    def test_events_with_string_messages_are_skipped(self):
        # synthetic: the real Claude Code stream has events whose "message" is a plain string
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "t.jsonl")
        events = [{"type": "system", "message": "init"}, {"type": "user", "message": {"content": "plain text"}}]
        helpers.write_jsonl(path, events + helpers.transcript_for(helpers.load_fixture("ask_ok.json")))
        self.assertEqual(len(na.extract_calls(path)), 1)

    def test_explore_calls_are_separated_from_asks(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "t.jsonl")
        helpers.write_jsonl(path, helpers.transcript_for({"nodes": []}, tool_name="mcp__okto-neuron__explore",
                                                          request={"topic": "error response"}))
        out, ex = os.path.join(tmp, "asks.jsonl"), os.path.join(tmp, "explores.jsonl")
        self.assertEqual(na.record(path, 9, "reviewer", out, ex), {"asks": 0, "explores": 1})
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
