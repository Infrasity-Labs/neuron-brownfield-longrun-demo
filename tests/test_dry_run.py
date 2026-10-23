import os
import re
import subprocess
import sys
import unittest

import helpers
import steps


def dry(*args):
    return subprocess.run([sys.executable, os.path.join(helpers.REPO, "run_demo.py"), "--dry-run"] + list(args),
                          capture_output=True, text=True, cwd=helpers.REPO)


class DryRun(unittest.TestCase):
    def test_all_ten_steps_print(self):
        out = dry()
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(re.findall(r"^STEP (\d+) ", out.stdout, re.M), [str(n) for n in range(1, 11)])

    def test_every_prompt_file_exists_and_is_printed(self):
        out = dry().stdout
        for step in steps.STEPS:
            for role, prompt in step["runs"]:
                self.assertTrue(os.path.isfile(os.path.join(helpers.REPO, prompt)), prompt)
                with open(os.path.join(helpers.REPO, prompt)) as handle:
                    first = handle.read().strip().splitlines()[0]
                self.assertIn(first, out)
            for role in {r for r, _ in step["runs"]}:
                self.assertTrue(os.path.isfile(os.path.join(helpers.REPO, steps.ROLES[role]["claude_md"])))

    def test_steps_and_start_flags(self):
        self.assertEqual(re.findall(r"^STEP (\d+) ", dry("--steps", "4", "7", "9").stdout, re.M), ["4", "7", "9"])
        self.assertEqual(re.findall(r"^STEP (\d+) ", dry("--start", "9").stdout, re.M), ["9", "10"])

    def test_planner_and_builder_are_pinned_to_the_team_vault(self):
        out = dry("--steps", "2", "3").stdout
        self.assertEqual(out.count("mcp?vault=team"), 2)

    def test_dry_run_reads_no_token(self):
        env = dict(os.environ, OKTO_NEURON_TOKEN_FILE="/nonexistent/token")
        out = subprocess.run([sys.executable, os.path.join(helpers.REPO, "run_demo.py"), "--dry-run"],
                             capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0)


if __name__ == "__main__":
    unittest.main()
