import hashlib
import os
import shutil
import tempfile
import unittest

import helpers  # noqa: F401  (sets sys.path)
import verify_citations as vc


class VerifyCitations(unittest.TestCase):
    def test_real_recorded_sources_pass(self):
        ask = helpers.load_fixture("ask_ok.json")
        results = vc.verify_sources(ask["sources"], "team", {"team": helpers.TEAM_ROOT})
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["ok"] for r in results), results)

    def test_provider_error_response_still_has_checkable_sources(self):
        ask = helpers.load_fixture("ask_provider_error.json")
        results = vc.verify_sources(ask["sources"], "team", {"team": helpers.TEAM_ROOT})
        self.assertTrue(results and all(r["ok"] for r in results))

    def _tmp_vault(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        return root

    def test_changed_bytes_fail(self):
        root = self._tmp_vault()
        with open(os.path.join(root, "note.md"), "wb") as f:
            f.write(b"hello world")
        good = {"path": "note.md", "byte_start": 0, "byte_end": 5,
                "content_hash": "sha256:" + hashlib.sha256(b"hello").hexdigest()}
        self.assertEqual(vc.verify_source(good, root), (True, "ok"))
        with open(os.path.join(root, "note.md"), "wb") as f:
            f.write(b"jello world")
        self.assertEqual(vc.verify_source(good, root), (False, "hash mismatch"))

    def test_bad_inputs_fail_cleanly(self):
        root = self._tmp_vault()
        with open(os.path.join(root, "n.md"), "wb") as f:
            f.write(b"abc")
        base = {"path": "n.md", "byte_start": 0, "byte_end": 3, "content_hash": "sha256:00"}
        self.assertEqual(vc.verify_source(dict(base, path="missing.md"), root)[1], "file not found")
        self.assertEqual(vc.verify_source(dict(base, byte_end=99), root)[1], "byte range is past the end of the file")
        self.assertEqual(vc.verify_source(dict(base, byte_start=2, byte_end=1), root)[1], "bad byte range")
        self.assertEqual(vc.verify_source(dict(base, path="/etc/hosts"), root)[1], "path missing or absolute")
        self.assertEqual(vc.verify_source(dict(base, path="../x"), root)[1], "path escapes the vault")


if __name__ == "__main__":
    unittest.main()
