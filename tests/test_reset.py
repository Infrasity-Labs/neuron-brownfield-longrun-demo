import contextlib
import io
import os
import shutil
import tempfile
import unittest

import helpers
import maintainer_edit as me
import reset


def edit(*args):
    with contextlib.redirect_stdout(io.StringIO()):
        return me.edit(*args)


def skeleton():
    """A copy of the notes and scenarios of this repository, to edit and reset without touching the real ones."""
    root = tempfile.mkdtemp()
    shutil.copytree(os.path.join(helpers.REPO, "vault"), os.path.join(root, "vault"))
    shutil.copytree(os.path.join(helpers.REPO, "scenarios"), os.path.join(root, "scenarios"))
    return root


class StartingState(unittest.TestCase):
    def test_this_repository_starts_before_both_rule_changes(self):
        problems = [p for p in reset.drift(helpers.REPO) if not p.startswith("vault-private/")]
        self.assertEqual(problems, [])
        with open(os.path.join(helpers.REPO, "vault", "policy-edit-window.md")) as handle:
            self.assertIn("15 minutes", handle.read())
        self.assertFalse(os.path.exists(os.path.join(helpers.REPO, "vault", "ops-runbook.md")))
        self.assertFalse(os.path.exists(os.path.join(helpers.REPO, "vault", "specs")))

    def test_step_4_changes_the_note_and_reset_restores_it(self):
        root = skeleton()
        vault, scenarios = os.path.join(root, "vault"), os.path.join(root, "scenarios")
        written = edit("step4", vault, scenarios)
        self.assertEqual(written, ["policy-edit-window.md"])
        with open(os.path.join(vault, "policy-edit-window.md")) as handle:
            self.assertIn("30 minutes", handle.read())
        self.assertIn("vault/policy-edit-window.md differs from step04/before/policy-edit-window.md", reset.drift(root))
        reset.reset(root)
        with open(os.path.join(vault, "policy-edit-window.md")) as handle:
            self.assertIn("15 minutes", handle.read())
        self.assertEqual([p for p in reset.drift(root)], [])

    def test_step_7_adds_a_note_and_reset_removes_it_and_the_pilot_specs_folder(self):
        root = skeleton()
        vault, scenarios = os.path.join(root, "vault"), os.path.join(root, "scenarios")
        self.assertEqual(edit("step7", vault, scenarios), ["ops-runbook.md", "policy-error-response.md"])
        os.makedirs(os.path.join(vault, "specs"))
        reset.reset(root)
        self.assertFalse(os.path.exists(os.path.join(vault, "ops-runbook.md")))
        self.assertFalse(os.path.exists(os.path.join(vault, "specs")))
        self.assertEqual(reset.drift(root), [])

    def test_reset_seeds_the_synthetic_private_notes(self):
        root = skeleton()
        reset.reset(root)
        self.assertEqual(sorted(os.listdir(os.path.join(root, "vault-private"))),
                         sorted(os.listdir(os.path.join(root, "scenarios", "private-notes"))))

    def test_an_edit_is_recorded_as_an_event_with_a_utc_time(self):
        root = skeleton()
        events = os.path.join(root, "events.jsonl")
        edit("step4", os.path.join(root, "vault"), os.path.join(root, "scenarios"), events)
        import events as ev
        recorded = ev.read_events(events)
        self.assertEqual((recorded[0]["event"], recorded[0]["label"], recorded[0]["step"]), ("maintainer_edit", "step4", 4))
        self.assertTrue(recorded[0]["ts"].endswith("Z"))


if __name__ == "__main__":
    unittest.main()
