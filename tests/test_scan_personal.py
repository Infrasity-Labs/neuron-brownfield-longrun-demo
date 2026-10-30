import os
import tempfile
import unittest

import helpers
import scan_personal as sp

# built from pieces so this file holds no personal literal itself
VAULT_NAME = "my" + "notes"
FOLDER = "Infra" + "sity/" + "ne" + "u"


class Patterns(unittest.TestCase):
    def test_home_paths_working_folder_and_vault_name_are_found(self):
        text = "see /Users/someone/%s/vault and /home/alice/x and the vault %s" % (FOLDER, VAULT_NAME)
        labels = [label for _n, label, _t in sp.find_matches(text)]
        self.assertIn("working copy path", labels)
        self.assertIn("personal vault name", labels)
        self.assertIn("user home path", labels)

    def test_ci_runner_homes_and_placeholders_are_allowed(self):
        self.assertEqual(sp.find_matches("/home/runner/work/x and /Users/runner/y and <HOME>/.okto-neuron"), [])

    def test_redaction_is_mechanical_and_idempotent(self):
        text = '{"cwd": "/Users/someone/%s", "p": "/Users/someone/.okto-neuron/vaults/%s"}' % (FOLDER, VAULT_NAME)
        once = sp.redact(text)
        self.assertEqual(once, '{"cwd": "<REPO>", "p": "<HOME>/.okto-neuron/vaults/<other-vault>"}')
        self.assertEqual(sp.redact(once), once)
        self.assertEqual(sp.find_matches(once), [])

    def test_redact_files_rewrites_only_files_with_a_match(self):
        root = tempfile.mkdtemp()
        with open(os.path.join(root, "a.txt"), "w") as handle:
            handle.write("home /Users/someone/x\n")
        with open(os.path.join(root, "b.txt"), "w") as handle:
            handle.write("nothing here\n")
        changed = sp.redact_files(root)
        self.assertEqual(list(changed), ["a.txt"])
        with open(os.path.join(root, "a.txt")) as handle:
            self.assertEqual(handle.read(), "home <HOME>/x\n")


class Repository(unittest.TestCase):
    def test_no_tracked_file_holds_a_home_path_the_working_folder_or_the_personal_vault_name(self):
        matches, _binary = sp.scan(helpers.REPO)
        self.assertEqual(matches, {}, "personal data found: run python3 scripts/scan_personal.py")


if __name__ == "__main__":
    unittest.main()
