import os
import tempfile
import unittest

import helpers  # noqa: F401
import closeout


def ask(status, step=2, vault="team", text="", finish="stop", **extra):
    # synthetic record built by hand for a unit test, not a recorded result
    rec = {"step": step, "role": "reviewer", "synthesis_status": status, "finish_reason": finish,
           "vault_served": vault, "text": text, "sources": [], "citation_checks": [], "agent_followup": ""}
    rec.update(extra)
    return rec


class Closeout(unittest.TestCase):
    def build(self, asks, private_dir="/nonexistent"):
        return closeout.build(asks, [], private_dir)

    def test_all_six_statuses_are_counted(self):
        asks = [ask(s) for s in ("ok", "no_llm", "empty", "provider_error", "truncated", "abnormal_stop")]
        counts = self.build(asks)["synthesis_status_counts"]
        for key in ("ok", "no_llm", "empty", "provider_error", "truncated", "abnormal_stop"):
            self.assertEqual(counts[key], 1, key)
        self.assertEqual(counts["unparsed"], 0)

    def test_unknown_status_is_not_dropped(self):
        self.assertEqual(self.build([ask("brand_new")])["synthesis_status_counts"]["unparsed"], 1)

    def test_finish_reason_other_than_stop_is_counted_apart(self):
        result = self.build([ask("ok", finish="stop"), ask("truncated", finish="length"), ask("provider_error", finish=None)])
        self.assertEqual(result["finish_reason_not_stop"], 1)
        self.assertEqual(result["finish_reason_missing"], 1)

    def test_override_ignored_is_counted(self):
        result = self.build([ask("ok", vault_override_ignored="reviewer-private"),
                             ask("ok", vault_override_ignored="team")])
        self.assertEqual(result["vault_override_ignored_count"], 1)
        self.assertEqual(result["vault_override_ignored_same_vault_count"], 1)

    def test_citation_totals_come_from_recorded_checks(self):
        checks = [{"ok": True}, {"ok": False}]
        result = self.build([ask("ok", citation_checks=checks, sources=[{}, {}])])
        self.assertEqual((result["citations_checked_at_record_time"], result["citations_passed_at_record_time"]), (2, 1))
        self.assertEqual(result["questions_with_sources"], 1)

    def test_private_note_in_team_answer_is_a_leak(self):
        tmp = tempfile.mkdtemp()
        with open(os.path.join(tmp, "p.md"), "w") as f:
            f.write("# Private\n\nThe reviewer found that the retry helper swallows every database error.\n")
        leak = ask("ok", text="The reviewer found that the retry helper swallows every database error.")
        clean = ask("ok", text="The edit window is 15 minutes.")
        result = self.build([leak, clean, dict(leak, vault_served="reviewer-private")], tmp)
        self.assertEqual(result["private_notes_in_team_answers"], 1)

    def test_stale_rule_after_replacement(self):
        stale = ask("ok", step=5, text="The edit window is 15 minutes.")
        fine = ask("ok", step=5, text="The window is 30 minutes. The old 15 minutes was replaced.")
        early = ask("ok", step=3, text="The edit window is 15 minutes.")
        result = self.build([stale, fine, early])
        self.assertEqual([s["step"] for s in result["stale_rule_answers_after_replacement"]], [5])

    def test_provider_error_followup_is_checked_for_false_nothing_found(self):
        bad = ask("provider_error", agent_followup="I couldn't find anything about that rule.")
        good = ask("provider_error", agent_followup="The model was unreachable, so I used explore.")
        flags = [p["claimed_nothing_found"] for p in self.build([bad, good])["provider_error_answers"]]
        self.assertEqual(flags, [True, False])

    def test_asks_to_other_vaults_are_counted(self):
        result = self.build([ask("ok", vault="mynotes"), ask("ok", vault="team"), ask("ok", vault="reviewer-private")])
        self.assertEqual(result["asks_to_vaults_other_than_the_two_demo_vaults"], 1)

    def test_missing_ingest_times_stay_null(self):
        self.assertIsNone(self.build([ask("ok")])["ingest_seconds_per_note"])


if __name__ == "__main__":
    unittest.main()
