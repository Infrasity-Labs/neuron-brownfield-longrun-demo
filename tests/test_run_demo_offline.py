import contextlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

import helpers

sys.path.insert(0, helpers.REPO)
import run_demo  # noqa: E402


class OfflineRun(unittest.TestCase):
    """run_demo.py end to end for the no-memory arm with a stand-in claude: no Neuron, no model, no network."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        target = os.path.join(self.bin, "claude")
        shutil.copy(os.path.join(helpers.HERE, "fake_claude.py"), target)
        os.chmod(target, os.stat(target).st_mode | stat.S_IEXEC)
        self.vault = os.path.join(self.tmp, "vault")
        self.private = os.path.join(self.tmp, "vault-private")
        shutil.copytree(os.path.join(helpers.REPO, "vault"), self.vault)
        os.makedirs(self.private)
        self.runs = os.path.join(self.tmp, "runs")

    def run_main(self, extra=(), leak=False, spec_value=False):
        env = {"PATH": self.bin + os.pathsep + os.environ["PATH"], "FAKE_CLAUDE_LEAK": "1" if leak else "0",
               "FAKE_CLAUDE_SPEC_VALUE": "1" if spec_value else "0"}
        patches = [mock.patch.dict(os.environ, env), mock.patch.object(run_demo, "VAULT_DIR", self.vault),
                   mock.patch.object(run_demo, "PRIVATE_DIR", self.private),
                   mock.patch.object(run_demo.reset_mod, "reset", lambda: []),
                   # hermetic: whether app/node_modules is installed on this machine must not change the result
                   mock.patch.object(run_demo.code_outcome, "run", side_effect=RuntimeError("app dependencies are missing (test)")),
                   mock.patch.object(run_demo.maintainer_edit, "VAULT", self.vault)]
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            return run_demo.main(["--arm", "none", "--run-id", "t1", "--runs-dir", self.runs] + list(extra))

    def manifest(self):
        with open(os.path.join(self.runs, "none", "t1", "run-manifest.json")) as handle:
            return json.load(handle)

    def test_a_full_run_of_the_no_memory_arm_records_everything_and_passes_the_isolation_check(self):
        self.assertEqual(self.run_main(), 0)
        run_dir = os.path.join(self.runs, "none", "t1")
        manifest = self.manifest()
        self.assertEqual(manifest["arm"], "none")
        self.assertEqual(manifest["checks"]["hard_failures"], [])
        self.assertEqual(manifest["checks"]["isolation"]["violations"], 0)
        self.assertEqual(manifest["checks"]["isolation"]["transcripts"], 11)  # steps 2 to 8, step 9 is skipped in this arm
        self.assertEqual(manifest["versions"]["claude_cli"], "9.9.9")
        self.assertEqual(len(manifest["metric"]["sha256"]), 64)
        self.assertIn("not run", manifest["checks"]["code_outcome_step3"])  # no node_modules: reported, not faked
        self.assertTrue(os.path.isfile(os.path.join(run_dir, "diffs", "step3.diff")))
        with open(os.path.join(run_dir, "diffs", "step3.diff")) as handle:
            self.assertIn("builder was here", handle.read())
        with open(os.path.join(run_dir, "events.jsonl")) as handle:
            events = [json.loads(line)["event"] for line in handle]
        self.assertEqual(events.count("maintainer_edit"), 2)
        self.assertEqual(events.count("role_start"), 11)
        self.assertEqual(events[0], "run_start")
        self.assertEqual(events[-1], "run_end")

    def test_the_maintainer_edits_reach_the_watched_folder_and_the_findings_the_private_folder(self):
        self.run_main()
        with open(os.path.join(self.vault, "policy-edit-window.md")) as handle:
            self.assertIn("30 minutes", handle.read())
        self.assertTrue(os.path.isfile(os.path.join(self.vault, "ops-runbook.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.private, "finding.md")))

    def test_the_builders_edit_is_carried_to_the_reviewer_through_the_canonical_tree_only(self):
        self.run_main()
        shas = {}
        folder = os.path.join(self.runs, "none", "t1", "workdir-manifests")
        for name in ("step03-builder.json", "step04-reviewer.json"):
            with open(os.path.join(folder, name)) as handle:
                shas[name] = {f["path"]: f["sha256"] for f in json.load(handle)}
        changed = [p for p in shas["step04-reviewer.json"] if shas["step04-reviewer.json"][p] != shas["step03-builder.json"].get(p)]
        self.assertIn("app/src/main.ts", changed)
        self.assertFalse([p for p in shas["step04-reviewer.json"] if p.split("/")[0] in ("vault", "docs", "PLAN.md", "demo-state")])

    def test_a_role_that_reads_a_note_fails_the_run(self):
        self.assertEqual(self.run_main(["--steps", "2"], leak=True), 1)
        failures = self.manifest()["checks"]["hard_failures"]
        self.assertTrue(any("isolation" in f for f in failures), failures)

    def test_a_rule_value_in_a_spec_is_recorded_once_per_spec_and_does_not_fail_the_run(self):
        self.assertEqual(self.run_main(["--steps", "2", "6"], spec_value=True), 0)
        checks = self.manifest()["checks"]
        self.assertEqual(checks["hard_failures"], [])
        self.assertEqual([(h["step"], h["spec"], h["rule"]) for h in checks["spec_rule_values"]],
                         [(2, "feature.md", "edited-marker-name")])

    def test_a_failed_run_stops_a_series_unless_keep_going_is_given(self):
        self.assertEqual(self.run_main(["--steps", "2", "--runs", "2"], leak=True), 1)
        self.assertEqual(sorted(os.listdir(os.path.join(self.runs, "none"))), ["t1-01"])
        shutil.rmtree(self.runs)
        self.assertEqual(self.run_main(["--steps", "2", "--runs", "2", "--keep-going"], leak=True), 1)
        self.assertEqual(sorted(os.listdir(os.path.join(self.runs, "none"))), ["t1-01", "t1-02"])

    def test_a_recorded_run_is_never_overwritten(self):
        self.run_main(["--steps", "2"])
        with self.assertRaises(SystemExit):
            self.run_main(["--steps", "2"])

    def test_a_partial_run_says_so_in_its_manifest(self):
        self.run_main(["--steps", "2"])
        self.assertTrue(self.manifest()["claude_flags"]["partial_run"])


if __name__ == "__main__":
    unittest.main()
