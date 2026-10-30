import os
import re
import tempfile
import unittest

import helpers  # noqa: F401
import events as ev


class Timeline(unittest.TestCase):
    def test_timestamps_are_utc_milliseconds(self):
        self.assertRegex(ev.utc_now(), r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")

    def test_log_and_read_round_trip(self):
        path = os.path.join(tempfile.mkdtemp(), "sub", "events.jsonl")
        ev.log_event(path, "maintainer_edit", ts="2026-01-01T00:00:00.000Z", label="step4", files=["a.md"])
        ev.log_event(path, "ingest_complete", ts="2026-01-01T00:05:00.000Z", label="step4")
        events = ev.read_events(path)
        self.assertEqual([e["event"] for e in events], ["maintainer_edit", "ingest_complete"])
        self.assertEqual(events[0]["files"], ["a.md"])

    def test_timeline_sorts_events_that_were_written_late(self):
        events = [{"ts": "2026-01-01T00:10:00.000Z", "event": "ask"}, {"ts": "2026-01-01T00:01:00.000Z", "event": "maintainer_edit"}]
        self.assertEqual([e["event"] for e in ev.timeline(events)], ["maintainer_edit", "ask"])

    def test_order_check_passes_when_the_ask_follows_ingest_and_probe(self):
        events = [
            {"ts": "2026-01-01T00:00:00.000Z", "event": "maintainer_edit", "label": "step4", "step": 4},
            {"ts": "2026-01-01T00:11:00.000Z", "event": "ingest_complete", "label": "step4"},
            {"ts": "2026-01-01T00:12:00.000Z", "event": "state_probe", "label": "step4"},
            {"ts": "2026-01-01T00:13:00.000Z", "event": "ask", "step": 4},
        ]
        self.assertEqual(ev.check_edit_order(events), [])

    def test_order_check_flags_an_ask_inside_the_ingest_window(self):
        events = [
            {"ts": "2026-01-01T00:00:00.000Z", "event": "maintainer_edit", "label": "step4", "step": 4},
            {"ts": "2026-01-01T00:05:00.000Z", "event": "ask", "step": 4},
            {"ts": "2026-01-01T00:11:00.000Z", "event": "ingest_complete", "label": "step4"},
        ]
        problems = ev.check_edit_order(events)
        self.assertEqual(len(problems), 1)
        self.assertIn("before ingest/probe", problems[0])

    def test_order_check_flags_an_edit_with_no_ingest(self):
        events = [{"ts": "2026-01-01T00:00:00.000Z", "event": "maintainer_edit", "label": "step7", "step": 7}]
        self.assertIn("no later ingest_complete", ev.check_edit_order(events)[0])


if __name__ == "__main__":
    unittest.main()
