import contextlib
import io
import os
import unittest

import helpers
import scan_rule_values as srv


def hits(text):
    return [(rule, match) for _line, rule, match in srv.scan_text(text, srv.load_patterns())]


class Patterns(unittest.TestCase):
    # synthetic sentences built by hand

    def test_edit_window_values_are_found(self):
        self.assertEqual(hits("Is it 15 minutes or 30-minutes?")[0][0], "edit-window-minutes")
        self.assertEqual(len(hits("Is it 15 minutes or 30-minutes?")), 2)

    def test_article_cap_and_field_names_and_shapes(self):
        self.assertEqual([r for r, _ in hits("at most 50 articles")], ["article-limit-cap"])
        self.assertEqual([r for r, _ in hits("set editedAt and deletedAt")], ["edited-marker-name", "soft-delete-field"])
        self.assertEqual([r for r, _ in hits('{"error":{"code":"x"}}')], ["error-object-shape"])
        self.assertEqual([r for r, _ in hits('{"errors":{"body":[]}}')], ["errors-by-field-shape"])

    def test_near_misses_are_not_hits(self):
        self.assertEqual(hits("HTTP 500 and 150 rows, 1500 characters, 3 minutes"), [])


class RepositoryInputs(unittest.TestCase):
    def test_prompts_agent_files_and_fixed_questions_carry_no_rule_value(self):
        self.assertEqual(srv.scan(helpers.REPO), [])

    def test_the_scan_covers_every_prompt_and_agent_file(self):
        names = {os.path.relpath(p, helpers.REPO) for p in srv.default_files(helpers.REPO)}
        self.assertIn(os.path.join("docs", "prompts", "05-builder.md"), names)
        self.assertIn(os.path.join("docs", "prompts", "negative", "N3-reviewer.md"), names)
        self.assertIn(os.path.join("agents", "neuron-skill.md"), names)
        self.assertIn(os.path.join("agents", "builder", "CLAUDE.md"), names)

    def test_the_pilot_questions_are_caught(self):
        found = srv.scan(helpers.REPO, asks=os.path.join(helpers.REPO, "demo-state", "asks.jsonl"))
        self.assertTrue(any(h["where"].endswith("asks.jsonl:15") and h["rule"] == "edit-window-minutes" for h in found))
        self.assertTrue(any(h["where"].endswith("asks.jsonl:31") and h["rule"] == "soft-delete-field" for h in found))

    def test_a_value_copied_into_a_spec_is_caught(self):
        found = srv.scan(helpers.REPO, specs=os.path.join(helpers.REPO, "demo-state", "pilot-specs"))
        self.assertTrue(any(h["rule"] == "edit-window-minutes" for h in found))

    def test_main_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(srv.main([]), 0)
            self.assertEqual(srv.main(["--asks", os.path.join(helpers.REPO, "demo-state", "asks.jsonl")]), 1)


if __name__ == "__main__":
    unittest.main()
