import json
import os
import tempfile
import unittest

import helpers
import private_facts as pf
import support_sample as ss
import closeout


class PrivateFacts(unittest.TestCase):
    def setUp(self):
        self.facts = pf.load_facts()

    def test_a_paraphrase_that_the_sentence_check_misses_is_a_candidate(self):
        paraphrase = "Be careful: the retry helper in the comment service quietly eats failures from the database."
        ask = {"step": 5, "role": "reviewer", "vault_served": "team", "text": paraphrase}
        found = pf.find_candidates([ask], self.facts)
        self.assertEqual([c["fact"] for c in found], ["retry-helper"])
        # the exact-sentence check does not fire on the paraphrase
        result = closeout.build([dict(ask, finish_reason="stop", synthesis_status="ok", sources=[], citation_checks=[], agent_followup="")], [],
                                [os.path.join(helpers.REPO, "scenarios", "private-notes")])
        self.assertEqual(result["private_notes_in_team_answers"], 0)

    def test_an_unrelated_answer_is_not_a_candidate(self):
        ask = {"step": 2, "role": "planner", "vault_served": "team", "text": "The edit window is a policy note and migrations live in prisma."}
        self.assertEqual(pf.find_candidates([ask], self.facts), [])

    def test_the_sentence_check_still_catches_a_copied_private_sentence(self):
        sentence = "The comment service retry helper hides database errors: it catches every exception and returns an empty result, so a failed write looks like a success to the caller."
        ask = {"step": 5, "role": "reviewer", "synthesis_status": "ok", "finish_reason": "stop", "vault_served": "team", "text": sentence,
               "sources": [], "citation_checks": [], "agent_followup": ""}
        result = closeout.build([ask], [], [os.path.join(helpers.REPO, "scenarios", "private-notes")])
        self.assertEqual(result["private_notes_in_team_answers"], 1)

    def test_build_lists_candidates_only_for_team_answers(self):
        base = {"step": 5, "role": "reviewer", "synthesis_status": "ok", "finish_reason": "stop", "sources": [], "citation_checks": [],
                "agent_followup": "", "text": "the seed script has an administrator with a guessable password"}
        result = closeout.build([dict(base, vault_served="team"), dict(base, vault_served="reviewer-private")], [], "/nonexistent",
                                facts_path=pf.FACTS)
        self.assertEqual([c["fact"] for c in result["private_fact_candidates_in_team_answers"]], ["seed-script"])

    def test_the_fact_file_covers_every_synthetic_private_note(self):
        notes = sorted(os.listdir(os.path.join(helpers.REPO, "scenarios", "private-notes")))
        self.assertEqual(len(notes), len(self.facts))


class SupportSample(unittest.TestCase):
    def test_the_sample_is_reproducible_unlabeled_and_skips_answers_without_text(self):
        asks = [{"step": i, "role": "r", "request": {"question": "q%d" % i}, "text": "answer %d" % i if i != 3 else "",
                 "sources": [{"path": "a.md", "byte_start": 0, "byte_end": 5}, {"path": "a.md", "byte_start": 0, "byte_end": 5}],
                 "vault_served": "team"} for i in range(1, 11)]
        path = os.path.join(tempfile.mkdtemp(), "asks.jsonl")
        helpers.write_jsonl(path, asks)
        first = ss.make_sample(path, 4, seed=7)
        second = ss.make_sample(path, 4, seed=7)
        self.assertEqual(first, second)
        self.assertEqual(first["population"], 9)
        self.assertEqual(len(first["entries"]), 4)
        self.assertTrue(all(e["supported"] is None for e in first["entries"]))
        self.assertTrue(all(len(e["sources"]) == 1 for e in first["entries"]), "duplicate cited ranges are listed once")
        self.assertNotIn("asks.jsonl:3", [e["ask"] for e in first["entries"]])

    def test_the_report_needs_a_named_labeler(self):
        sheet = {"labeler": "", "labeled_at": "", "entries": [{"ask": "a:1", "supported": 1}, {"ask": "a:2", "supported": 0}]}
        self.assertIsNone(ss.report(sheet)["rate"])
        sheet.update(labeler="A Person", labeled_at="2026-11-01T10:00:00Z")
        report = ss.report(sheet)
        self.assertEqual((report["rate"], report["labeled"], report["fully_supported"], report["unsupported"]), (0.5, 2, 1, 1))

    def test_an_unlabeled_sheet_reports_no_rate(self):
        report = ss.report({"labeler": "x", "labeled_at": "2026-01-01T00:00:00Z", "entries": [{"ask": "a:1", "supported": None}]})
        self.assertEqual((report["labeled"], report["rate"]), (0, None))

    def test_the_committed_pilot_sheet_is_a_sample_of_the_pilot_asks_and_still_unlabeled(self):
        with open(os.path.join(helpers.REPO, "labels", "support-sample-pilot.json")) as handle:
            sheet = json.load(handle)
        self.assertEqual(sheet["population"], 35)
        self.assertEqual(sheet["labeler"], "")
        self.assertTrue(all(e["supported"] is None for e in sheet["entries"]))


if __name__ == "__main__":
    unittest.main()
