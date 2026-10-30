import json
import os
import re
import shutil
import tempfile
import unittest

import helpers
import check_readme as cr


def copy_repo_pieces():
    root = tempfile.mkdtemp()
    shutil.copy(os.path.join(helpers.REPO, "README.md"), root)
    os.makedirs(os.path.join(root, "demo-state", "transcripts"))
    for name in ("closeout-result.json", "curation-queue-team.json", "asks.jsonl", "explores.jsonl"):
        shutil.copy(os.path.join(helpers.REPO, "demo-state", name), os.path.join(root, "demo-state", name))
    for name in os.listdir(os.path.join(helpers.REPO, "demo-state", "transcripts")):
        shutil.copy(os.path.join(helpers.REPO, "demo-state", "transcripts", name), os.path.join(root, "demo-state", "transcripts", name))
    shutil.copytree(os.path.join(helpers.REPO, "vault"), os.path.join(root, "vault"))
    return root


def rewrite(root, old, new):
    path = os.path.join(root, "README.md")
    with open(path) as handle:
        text = handle.read()
    assert old in text, old
    with open(path, "w") as handle:
        handle.write(text.replace(old, new, 1))


def pilot_problems(root):
    # the fixture holds the README and the pilot files only, not runs/, so the generated study blocks are left to their own test
    return [p for p in cr.check(root) if "study-" not in p]


class ReadmeAgainstRecordedFiles(unittest.TestCase):
    def test_the_committed_readme_agrees_with_the_recorded_files(self):
        self.assertEqual(cr.check(helpers.REPO), [])

    def test_a_changed_number_is_caught(self):
        root = copy_repo_pieces()
        rewrite(root, "| 638 of 763 at record time", "| 640 of 763 at record time")
        problems = pilot_problems(root)
        self.assertEqual(len(problems), 1)
        self.assertIn("Citations that passed the hash check", problems[0])

    def test_a_missing_row_and_an_unknown_row_are_caught(self):
        root = copy_repo_pieces()
        rewrite(root, "| Failed citations of any other kind | 0 |\n", "| A row nobody checks | 7 |\n")
        problems = pilot_problems(root)
        self.assertTrue(any("missing" in p and "any other kind" in p for p in problems))
        self.assertTrue(any("not checked" in p for p in problems))

    def test_a_wrong_pilot_verdict_is_caught(self):
        root = copy_repo_pieces()
        rewrite(root, "| 5 Reviewer | Not approved |", "| 5 Reviewer | Approved |")
        self.assertTrue(any("5 Reviewer" in p for p in pilot_problems(root)))

    def test_a_wrong_note_count_and_a_hard_coded_test_count_are_caught(self):
        root = copy_repo_pieces()
        rewrite(root, "13 starting notes live", "14 starting notes live")
        rewrite(root, "Run the unit tests yourself", "All 31 tests pass. Run the unit tests yourself")
        problems = pilot_problems(root)
        self.assertTrue(any("14 starting notes" in p for p in problems))
        self.assertTrue(any("unit test count" in p for p in problems))

    def test_a_wrong_recorded_ask_count_is_caught(self):
        root = copy_repo_pieces()
        rewrite(root, "Pilot, 36 asks", "Pilot, 40 asks")
        self.assertTrue(any("recorded asks" in p for p in pilot_problems(root)))

    def test_expected_rows_come_from_the_json_not_from_the_readme(self):
        with open(os.path.join(helpers.REPO, "demo-state", "closeout-result.json")) as handle:
            result = json.load(handle)
        with open(os.path.join(helpers.REPO, "demo-state", "curation-queue-team.json")) as handle:
            queue = json.load(handle)
        rows = dict(cr.expected_rows(result, queue))
        self.assertEqual(rows["Questions asked"], "36")
        self.assertEqual(rows["Asks with no `finish_reason` at all"], "1")
        self.assertEqual(rows["Questions that returned sources and a non-empty answer"], "35 of 36")


if __name__ == "__main__":
    unittest.main()
