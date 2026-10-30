import json
import os
import unittest

import helpers
import closeout


def ask(sources=1, text="an answer", checks=None, step=3):
    # synthetic record built by hand for a unit test, not a recorded result
    return {"step": step, "role": "builder", "synthesis_status": "ok", "finish_reason": "stop", "vault_served": "team",
            "text": text, "sources": [{}] * sources, "citation_checks": checks or [], "agent_followup": ""}


def failed(reason, path=".marginalia/sources/abc123/specs/feature-1.md"):
    return {"ok": False, "reason": reason, "path": path}


class DerivedKeys(unittest.TestCase):
    def test_returned_sources_needs_an_answer(self):
        extra = closeout.derive_extra([ask(), ask(sources=20, text=""), ask(sources=0)])
        self.assertEqual(extra["questions_with_sources_and_answer"], 1)

    def test_stale_anchors_are_split_from_other_failures_and_grouped_by_note(self):
        checks = [failed("byte range is past the end of the file"), failed("hash mismatch"),
                  failed("hash mismatch", ".marginalia/sources/abc123/policy-error-response.md"),
                  failed("file not found"), {"ok": True, "reason": "ok", "path": "x"}]
        extra = closeout.derive_extra([ask(checks=checks), ask(checks=[failed("hash mismatch")], step=4)])
        self.assertEqual(extra["stale_anchor_failures"], 4)
        self.assertEqual(extra["other_citation_failures"], 1)
        self.assertEqual(extra["stale_anchor_failures_by_note"], {"policy-error-response.md": 1, "specs/feature-1.md": 3})
        self.assertEqual(extra["stale_anchor_asks"], [{"ask_number": 1, "step": 3, "role": "builder", "stale_anchors": 3},
                                                      {"ask_number": 2, "step": 4, "role": "builder", "stale_anchors": 1}])

    def test_build_includes_the_derived_keys_and_the_missing_finish_reason_count(self):
        result = closeout.build([ask(), dict(ask(), finish_reason=None)], [], "/nonexistent")
        self.assertEqual(result["finish_reason_missing"], 1)
        for key in closeout.DERIVED_KEYS:
            self.assertIn(key, result)

    def test_amend_adds_only_the_derived_keys_and_keeps_every_other_value(self):
        existing = {"questions_asked": 2, "citations_passed_on_recheck": 616, "private_notes_in_team_answers": 0}
        merged = closeout.amend(existing, [ask()])
        self.assertEqual({k: merged[k] for k in existing}, existing)
        self.assertEqual(set(merged) - set(existing), set(closeout.DERIVED_KEYS))


class PilotFileStaysTruthful(unittest.TestCase):
    """demo-state/closeout-result.json is recorded evidence plus keys derived from asks.jsonl. Both are recomputed here."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(helpers.REPO, "demo-state", "asks.jsonl")) as handle:
            cls.asks = [json.loads(line) for line in handle if line.strip()]
        with open(os.path.join(helpers.REPO, "demo-state", "closeout-result.json")) as handle:
            cls.recorded = json.load(handle)

    def test_derived_keys_equal_a_recomputation_from_the_recorded_asks(self):
        extra = closeout.derive_extra(self.asks)
        for key in closeout.DERIVED_KEYS:
            self.assertEqual(self.recorded[key], extra[key], key)

    def test_the_numbers_that_depend_only_on_the_asks_are_unchanged_by_the_new_code(self):
        fresh = closeout.build(self.asks, [], "/nonexistent")
        for key in ("questions_asked", "questions_with_sources", "synthesis_status_counts", "finish_reason_not_stop",
                    "finish_reason_missing", "vault_override_ignored_count", "vault_override_ignored_same_vault_count",
                    "citations_checked_at_record_time", "citations_passed_at_record_time", "claims_replaced",
                    "stale_rule_answers_after_replacement", "provider_error_answers",
                    "asks_to_vaults_other_than_the_two_demo_vaults"):
            self.assertEqual(self.recorded[key], fresh[key], key)

    def test_every_failed_pilot_citation_is_a_stale_anchor_and_the_notes_sum_to_125(self):
        self.assertEqual(self.recorded["stale_anchor_failures"], 125)
        self.assertEqual(self.recorded["other_citation_failures"], 0)
        self.assertEqual(sum(self.recorded["stale_anchor_failures_by_note"].values()), 125)
        self.assertEqual(self.recorded["citations_checked_at_record_time"] - self.recorded["citations_passed_at_record_time"], 125)


if __name__ == "__main__":
    unittest.main()
