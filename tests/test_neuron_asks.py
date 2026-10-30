import copy
import json
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


class RecorderCrashRegression(unittest.TestCase):
    """The first recorded attempt of step 2 crashed with AttributeError: 'str' object has no attribute 'get'."""

    def test_the_fixture_has_the_shape_that_crashed_the_old_code(self):
        event = helpers.load_fixture("permission_denied_event.json")
        self.assertIsInstance(event["message"], str)
        with self.assertRaises(AttributeError):
            (event.get("message") or {}).get("content")  # the expression the pilot's recorder ran on every event

    def test_a_real_permission_denied_event_between_a_call_and_its_result_is_skipped(self):
        event = helpers.load_fixture("permission_denied_event.json")
        events = helpers.transcript_for(helpers.load_fixture("ask_ok.json"))
        events.insert(1, event)
        path = os.path.join(tempfile.mkdtemp(), "t.jsonl")
        helpers.write_jsonl(path, events)
        calls = na.extract_calls(path)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["followup"], "Done.")

    def test_the_whole_transcript_that_crashed_is_recorded_and_matches_the_pilot_asks(self):
        transcript = os.path.join(helpers.REPO, "demo-state", "transcripts", "step02-planner.jsonl")
        tmp = tempfile.mkdtemp()
        counts = na.record(transcript, 2, "planner", os.path.join(tmp, "asks.jsonl"), os.path.join(tmp, "explores.jsonl"),
                           {"team": helpers.TEAM_ROOT})
        with open(os.path.join(helpers.REPO, "demo-state", "asks.jsonl")) as handle:
            pilot = [json.loads(line) for line in handle if line.strip()]
        self.assertEqual(counts["asks"], len([a for a in pilot if a["step"] == 2 and a["role"] == "planner"]))
        self.assertEqual(counts["explores"], 1)


class AskTimestamps(unittest.TestCase):
    def test_ask_and_answer_times_come_from_the_transcript_in_utc(self):
        events = helpers.transcript_for(helpers.load_fixture("ask_ok.json"))
        events[0]["timestamp"] = "2026-10-23T05:41:51.123Z"
        events[1]["timestamp"] = "2026-10-23T11:11:55.900+05:30"
        path = os.path.join(tempfile.mkdtemp(), "t.jsonl")
        helpers.write_jsonl(path, events)
        call = na.extract_calls(path)[0]
        self.assertEqual(call["asked_at"], "2026-10-23T05:41:51.123Z")
        self.assertEqual(call["answered_at"], "2026-10-23T05:41:55.900Z")
        record = na.build_ask_record(call, 4, "reviewer", {"team": helpers.TEAM_ROOT})
        self.assertEqual(record["asked_at"], "2026-10-23T05:41:51.123Z")

    def test_a_transcript_without_timestamps_records_none_not_a_guess(self):
        path = os.path.join(tempfile.mkdtemp(), "t.jsonl")
        helpers.write_jsonl(path, helpers.transcript_for(helpers.load_fixture("ask_ok.json")))
        call = na.extract_calls(path)[0]
        self.assertIsNone(call["asked_at"])
        self.assertIsNone(call["answered_at"])

    def test_recording_writes_an_event_with_the_ask_time(self):
        events = helpers.transcript_for(helpers.load_fixture("ask_ok.json"))
        events[0]["timestamp"] = "2026-10-23T05:41:51.000Z"
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "t.jsonl")
        helpers.write_jsonl(path, events)
        timeline = os.path.join(tmp, "events.jsonl")
        na.record(path, 4, "reviewer", os.path.join(tmp, "a.jsonl"), os.path.join(tmp, "e.jsonl"), {"team": helpers.TEAM_ROOT}, timeline)
        with open(timeline) as handle:
            event = json.loads(handle.readline())
        self.assertEqual((event["event"], event["ts"], event["step"], event["role"]), ("ask", "2026-10-23T05:41:51.000Z", 4, "reviewer"))


if __name__ == "__main__":
    unittest.main()
