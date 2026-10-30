import json
import os
import re
import unittest

import helpers
import prompts
import steps

PILOT_STEPS_WITH_ROLES = [(s["id"], role, path) for s in steps.STEPS for role, path in s["runs"]]


def questions_of(text):
    return re.findall(r"^\d+\. (?:\[[a-z-]+\] )?(.*)$", text.split("Questions:")[1].split("###")[0], re.M)


class Arms(unittest.TestCase):
    def build(self, arm, path="docs/prompts/06-reviewer.md"):
        return prompts.build_prompt(arm, path, os.path.join(helpers.REPO, "vault"), os.path.join(helpers.REPO, "scenarios", "private-notes"))

    def test_the_same_questions_and_task_text_are_in_every_arm(self):
        texts = {arm: self.build(arm) for arm in steps.ARMS}
        task = prompts.read("docs/prompts/06-reviewer.md").strip()
        for arm, text in texts.items():
            self.assertTrue(text.startswith(task), arm)
        self.assertEqual(questions_of(texts["neuron"]), questions_of(texts["notes"]))
        self.assertEqual(questions_of(texts["neuron"]), questions_of(texts["none"]))
        self.assertEqual(len(questions_of(texts["none"])), 2)

    def test_only_the_neuron_arm_mentions_neuron_and_vault_tags(self):
        self.assertIn("Okto Neuron", self.build("neuron"))
        self.assertIn("[reviewer-private]", self.build("neuron"))
        for arm in ("notes", "none"):
            self.assertNotIn("Neuron", self.build(arm))
            self.assertNotIn("[team]", self.build(arm))

    def test_notes_arm_pastes_the_current_notes_and_the_none_arm_pastes_nothing(self):
        notes = self.build("notes")
        with open(os.path.join(helpers.REPO, "vault", "policy-article-list-limit.md")) as handle:
            self.assertIn(handle.read().strip(), notes)
        self.assertIn("Your private notes", notes)
        none = self.build("none")
        self.assertNotIn("policy-article-list-limit", none)
        self.assertNotIn("Team notes", none)

    def test_private_notes_are_pasted_only_for_a_question_about_them(self):
        self.assertNotIn("Your private notes", self.build("notes", "docs/prompts/05-builder.md"))

    def test_notes_arm_shows_the_notes_as_they_stand_in_the_vault_folder(self):
        self.assertIn("15 minutes", self.build("notes", "docs/prompts/05-builder.md"))

    def test_system_prompt_adds_neuron_files_only_in_arm_c(self):
        for role in steps.ROLES:
            self.assertIn("Neuron", prompts.build_system_prompt("neuron", role))
            self.assertNotIn("Neuron", prompts.build_system_prompt("none", role))
            self.assertNotIn("Neuron", prompts.build_system_prompt("notes", role))
            self.assertIn("Standing rules", prompts.build_system_prompt("none", role))


class ToolLimits(unittest.TestCase):
    def test_no_role_may_read_outside_its_directory_or_run_git_elsewhere(self):
        for role, spec in steps.ROLES.items():
            self.assertNotIn("Read", spec["allowed"], "blanket Read for %s" % role)
            for rule in spec["allowed"]:
                self.assertNotIn("-C", rule)
                self.assertNotIn("nx test", rule)
                self.assertNotIn("prisma", rule)
            self.assertNotIn("WebFetch", spec["builtin_tools"])
            self.assertNotIn("WebSearch", spec["builtin_tools"])
            self.assertNotIn("Task", spec["builtin_tools"])

    def test_each_role_may_edit_only_its_own_folder(self):
        for role, spec in steps.ROLES.items():
            edits = [r for r in spec["allowed"] if r.startswith("Edit(")]
            self.assertEqual(edits, ["Edit(%s/**)" % spec["writes"]])

    def test_neuron_tools_exist_only_in_arm_c(self):
        for role in steps.ROLES:
            self.assertTrue(set(steps.NEURON_TOOLS) <= set(steps.allowed_tools(role, "neuron")))
            for arm in ("none", "notes"):
                self.assertFalse(set(steps.NEURON_TOOLS) & set(steps.allowed_tools(role, arm)))

    def test_planner_and_builder_are_pinned_reviewer_is_not(self):
        self.assertEqual(steps.ROLES["planner"]["mcp_vault_query"], "team")
        self.assertEqual(steps.ROLES["builder"]["mcp_vault_query"], "team")
        self.assertIsNone(steps.ROLES["reviewer"]["mcp_vault_query"])

    def test_the_app_tests_are_not_asked_for_anywhere_an_agent_reads(self):
        for path in list(prompts_files()):
            with open(path) as handle:
                text = handle.read().lower()
            self.assertNotIn("run the app tests", text, path)
            self.assertNotIn("npx nx test", text, path)


def prompts_files():
    for base in ("docs/prompts", "agents"):
        for root, _d, files in os.walk(os.path.join(helpers.REPO, base)):
            for name in files:
                if name.endswith(".md"):
                    yield os.path.join(root, name)


class Inputs(unittest.TestCase):
    def test_every_question_belongs_to_a_prompt_that_exists_and_names_a_known_vault(self):
        with open(os.path.join(helpers.REPO, "docs", "questions.json")) as handle:
            data = json.load(handle)["steps"]
        known = {steps.prompt_key(p) for _i, _r, p in PILOT_STEPS_WITH_ROLES}
        self.assertEqual(set(data), known)
        for key, questions in data.items():
            for question in questions:
                self.assertIn(question["vault"], (steps.TEAM_VAULT, steps.PRIVATE_VAULT))

    def test_no_prompt_tells_a_role_what_a_previous_review_found_or_that_a_rule_changed(self):
        banned = re.compile(r"\b(flagged|was changed|has changed|replaced|the replaced|changed the)\b", re.I)
        for path in prompts_files():
            if os.sep + "neuron-skill" in path:
                continue
            with open(path) as handle:
                text = handle.read()
            self.assertIsNone(banned.search(text), "%s: %s" % (path, banned.search(text)))

    def test_pins_are_complete(self):
        with open(os.path.join(helpers.REPO, "pins.json")) as handle:
            pins = json.load(handle)
        self.assertRegex(pins["neuron"]["wheel_sha256"], r"^[0-9a-f]{64}$")
        self.assertIn(pins["neuron"]["version"], pins["neuron"]["wheel_url"])
        self.assertRegex(pins["claude_cli"]["expected_version"], r"^\d+\.\d+\.\d+$")
        with open(os.path.join(helpers.REPO, "README.md")) as handle:
            self.assertIn(pins["neuron"]["version"], handle.read())


if __name__ == "__main__":
    unittest.main()
