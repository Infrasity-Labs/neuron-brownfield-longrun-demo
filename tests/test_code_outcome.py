import os
import re
import unittest

import helpers
import code_outcome as co


def report(statuses):
    # synthetic jest --json shape built by hand, not a recorded result
    return {"testResults": [{"assertionResults": [{"title": t, "status": s} for t, s in statuses]}]}


class ParseJest(unittest.TestCase):
    def test_every_check_title_maps_to_an_outcome(self):
        titles = [
            ("edit-window: accepts an edit one minute inside the window", "passed"),
            ("edit-window: refuses an edit one minute outside the window", "failed"),
            ("article-limit: caps a limit above the cap", "passed"),
            ("article-limit: keeps a limit below the cap", "passed"),
            ("article-limit: keeps the default limit when none is given", "passed"),
        ]
        self.assertEqual(co.parse_jest(report(titles)), {
            "edit-window/accepts-inside": "pass", "edit-window/refuses-outside": "fail",
            "article-limit/caps-above": "pass", "article-limit/keeps-below": "pass", "article-limit/keeps-default": "pass"})

    def test_a_suite_that_did_not_run_is_an_error_not_a_pass(self):
        self.assertEqual(set(co.parse_jest({"testResults": [{"assertionResults": [], "message": "TS2304"}]}).values()), {"error"})
        self.assertEqual(set(co.parse_jest({}).values()), {"error"})

    def test_failure_details_keep_what_the_check_saw_without_scoring_it(self):
        # failureMessages shaped like jest's own, ANSI colours included (synthetic text)
        rep = {"testResults": [{"assertionResults": [
            {"title": "edit-window: refuses an edit one minute outside the window", "status": "failed",
             "failureMessages": ["Error: \x1b[2mexpect(\x1b[22m\x1b[31mreceived\x1b[39m).toBeLessThan(expected)\n\nExpected: < 500\nReceived:   500\n at x"]},
            {"title": "article-limit: caps a limit above the cap", "status": "passed", "failureMessages": []}]}]}
        details = co.parse_failures(rep)
        self.assertEqual(list(details), ["edit-window/refuses-outside"])
        self.assertEqual(details["edit-window/refuses-outside"], "Expected: < 500 | Received: 500")
        self.assertNotIn("\x1b", details["edit-window/refuses-outside"])

    def test_missing_dependencies_stop_the_run_instead_of_reporting_a_pass(self):
        with self.assertRaises(RuntimeError):
            co.run("/nonexistent", "/nonexistent", "step5", 30, node_modules="/nonexistent/node_modules")


class CheckFile(unittest.TestCase):
    def test_every_test_title_in_the_typescript_check_is_mapped(self):
        with open(os.path.join(helpers.REPO, "scenarios", "checks", "outcome.check.ts")) as handle:
            source = handle.read()
        titles = re.findall(r"test\('([^']+)'", source)
        self.assertEqual(len(titles), len(co.OUTCOME_IDS))
        for title in titles:
            self.assertTrue(any(title.startswith(prefix) for prefix, _o in co.TITLES), title)

    def test_the_check_states_the_minute_29_and_31_boundary(self):
        with open(os.path.join(helpers.REPO, "scenarios", "checks", "outcome.check.ts")) as handle:
            source = handle.read()
        self.assertIn("mockComment(WINDOW - 1)", source)
        self.assertIn("mockComment(WINDOW + 1)", source)
        self.assertIn("toBeLessThan(500)", source)

    def test_the_check_is_not_part_of_the_app_tree(self):
        self.assertFalse(os.path.exists(os.path.join(helpers.REPO, "app", "src", "tests", "outcome")))


if __name__ == "__main__":
    unittest.main()
