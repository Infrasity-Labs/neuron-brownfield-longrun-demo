import os
import re
import subprocess
import unittest

import helpers

try:
    import yaml
except ImportError:  # the fast workflow runs on a plain Python without PyYAML
    yaml = None


def read(rel):
    with open(os.path.join(helpers.REPO, rel)) as handle:
        return handle.read()


class Workflows(unittest.TestCase):
    @unittest.skipIf(yaml is None, "PyYAML is not installed")
    def test_workflows_parse(self):
        for name in ("validate.yml", "integration.yml"):
            data = yaml.safe_load(read(".github/workflows/" + name))
            self.assertIn("jobs", data, name)

    def test_the_fast_job_says_what_it_checks_and_never_starts_neuron(self):
        text = read(".github/workflows/validate.yml")
        self.assertIn("static-checks-and-recorded-file-validation", text)
        self.assertIn("scripts/check_all.py", text)
        self.assertNotIn("okto-neuron", text.replace("# ", ""))
        self.assertNotIn("claude ", text)

    def test_the_integration_workflow_is_opt_in_pinned_and_uploads_on_failure(self):
        text = read(".github/workflows/integration.yml")
        self.assertIn("workflow_dispatch", text)
        self.assertIn("run-integration", text)
        self.assertIn("scripts/install_neuron.sh", text)
        self.assertNotIn("/main/install.sh", text)
        self.assertIn("run_demo.py --arm neuron", text)
        self.assertIn("--fail-on-outcome", text)
        self.assertRegex(text, r"if: always\(\)\s+uses: actions/upload-artifact")
        self.assertIn("runs/neuron/", text)
        self.assertNotIn(".demo-home", text.split("upload-artifact")[1], "Neuron's home holds the saved key and must not be uploaded")
        self.assertIn("setup_vaults.sh", text)
        self.assertNotRegex(text, r"on:\s*\[?push")

    def test_workflows_do_not_inline_secrets(self):
        for name in ("validate.yml", "integration.yml"):
            text = read(".github/workflows/" + name)
            self.assertNotRegex(text, r"sk-[A-Za-z0-9]{10,}")


class Scripts(unittest.TestCase):
    def test_shell_scripts_parse(self):
        for rel in ("scripts/setup_vaults.sh", "scripts/install_neuron.sh"):
            self.assertEqual(subprocess.run(["bash", "-n", os.path.join(helpers.REPO, rel)]).returncode, 0, rel)

    def test_setup_never_puts_the_key_on_a_command_line_and_runs_isolated(self):
        text = read("scripts/setup_vaults.sh")
        self.assertNotRegex(text, r"--api-key(?!-env)")
        self.assertIn("--api-key-env", text)
        self.assertIn("export HOME=", text)
        self.assertIn("--port", text)
        self.assertIn("--mcp-port", text)
        self.assertIn("neuron_ctl.py\" version", text)
        self.assertNotIn("okto-neuron stop\nokto-neuron serve --daemon --no-open\n", text)

    def test_the_installer_checks_the_checksum_and_does_not_use_the_main_branch_installer(self):
        text = read("scripts/install_neuron.sh")
        self.assertIn("sha256", text)
        self.assertIn("UV_TOOL_DIR", text)
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        self.assertNotRegex(code, r"install\.sh")

    def test_scripts_that_could_overwrite_the_pilot_have_no_default_output_path(self):
        scripts = [n for n in os.listdir(os.path.join(helpers.REPO, "scripts")) if n.endswith(".py")]
        for name in scripts:
            self.assertNotRegex(read("scripts/" + name), r"default=[\"']demo-state", name)


class Documents(unittest.TestCase):
    def test_readme_and_verified_agree_about_screenshots_and_status(self):
        readme, verified = read("README.md"), read("docs/VERIFIED.md")
        self.assertNotIn("Real captures", readme)
        self.assertNotIn("Those two are not taken.", verified)
        self.assertNotIn("Draft in progress", verified)
        for image in ("neuron-curation-team.png", "neuron-query-sources.png"):
            self.assertTrue(os.path.isfile(os.path.join(helpers.REPO, "docs", "images", image)))
            self.assertIn(image, verified)

    def test_readme_says_what_the_evidence_does_and_does_not_show(self):
        readme = read("README.md")
        self.assertIn("Hand labels are pending.", readme)
        self.assertIn("This does not show Neuron beating the notes pasted into the prompt.", readme)
        self.assertIn("What This Demo Does Not Establish", readme)
        self.assertIn("A prompt rule only", readme)
        self.assertIn("Enforced by the working directory", readme)
        self.assertIn("Approved", read("scripts/check_readme.py"))

    def test_walkthrough_no_longer_claims_to_hold_no_results_while_stating_one(self):
        text = read("docs/walkthrough.md")
        self.assertNotIn("Nothing here is a result", text)
        self.assertIn("states no expected result", text)
        self.assertNotRegex(text, r"(?i)the reviewer's answer says 30")

    def test_every_neuron_command_in_the_scripts_is_listed_in_the_usage_table(self):
        usage = read("docs/NEURON-USAGE.md")
        for needle in ("watch-folder add", "serve --daemon", "--api-key-env", "OKTO_NEURON_ENDPOINT", "daemon-<rest port>.token",
                       "onboard", "--version", "okto-neuron stop"):
            self.assertIn(needle, usage)
        self.assertIn("undocumented", usage.lower())

    def test_product_observations_keep_reported_and_recounted_apart(self):
        text = read("docs/PRODUCT-OBSERVATIONS.md")
        self.assertIn("not reproduced", text)
        self.assertEqual(len(re.findall(r"^## \d+\. ", text, re.M)), 11)


if __name__ == "__main__":
    unittest.main()
