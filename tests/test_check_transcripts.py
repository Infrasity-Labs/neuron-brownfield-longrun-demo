import contextlib
import io
import os
import tempfile
import unittest

import helpers
import check_transcripts as ct

CWD = "/tmp/role-work"


def use(tool_id, name, **inp):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tool_id, "name": name, "input": inp}]}}


def result(tool_id, text="ok", error=False):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tool_id, "content": text, "is_error": error}]}}


def denied(tool_id):
    return {"type": "system", "subtype": "permission_denied", "tool_use_id": tool_id, "message": "requires approval"}


def init():
    return {"type": "system", "subtype": "init", "cwd": CWD}


def run_main(argv):
    with contextlib.redirect_stdout(io.StringIO()):
        return ct.main(argv)


def check(events, **kw):
    path = os.path.join(tempfile.mkdtemp(), "t.jsonl")
    helpers.write_jsonl(path, events)
    return ct.check_transcript(path, **kw)


class SyntheticTranscripts(unittest.TestCase):
    # synthetic transcript lines built by hand for each case, not recorded results

    def test_reading_a_note_is_a_violation(self):
        report = check([init(), use("a", "Read", file_path=CWD + "/vault/policy-edit-window.md"), result("a")])
        self.assertEqual(len(report["violations"]), 1)

    def test_reading_app_code_and_writing_the_own_folders_is_fine(self):
        events = [init(), use("a", "Read", file_path=CWD + "/app/src/main.ts"), result("a"),
                  use("b", "Write", file_path="specs/feature.md"), result("b"),
                  use("c", "Write", file_path="private-out/finding.md"), result("c"),
                  use("d", "Read", file_path="app/node_modules/pkg/docs/readme.md"), result("d")]
        report = check(events)
        self.assertEqual((report["violations"], report["blocked"]), ([], []))

    def test_a_directory_named_docs_inside_the_apps_own_tree_is_not_the_maintainers_docs(self):
        # Seen in a live no-memory run: `ls app/docs 2>/dev/null` was reported as reaching docs/.
        report = check([init(), use("a", "Bash", command="ls app; ls app/docs 2>/dev/null"), result("a")])
        self.assertEqual(report["violations"], [])
        report = check([init(), use("a", "Bash", command="ls docs"), result("a")])
        self.assertEqual(len(report["violations"]), 1)
        report = check([init(), use("a", "Bash", command="ls ../docs"), result("a")])
        self.assertEqual(len(report["violations"]), 1)

    def test_a_grep_pattern_that_looks_like_an_absolute_path_reaches_nothing(self):
        # Seen in a live run: `... | grep -v '/node_modules/'` was reported as naming a path outside the working directory.
        report = check([init(), use("a", "Bash", command="find . -type f | grep -v '/node_modules/'"), result("a")])
        self.assertEqual(report["violations"], [])
        report = check([init(), use("a", "Bash", command="ls /Users"), result("a")])
        self.assertEqual(len(report["violations"]), 1)

    def test_cd_into_the_own_working_directory_is_not_a_path_outside_it(self):
        # Seen in live runs: `cd <the session's own cwd>; ls -la` was reported because the token ended in ';'.
        report = check([init(), use("a", "Bash", command="cd %s; ls -la; ls %s/app" % (CWD, CWD)), result("a")])
        self.assertEqual(report["violations"], [])
        report = check([init(), use("a", "Bash", command="cd /etc/other; ls"), result("a")])
        self.assertEqual(len(report["violations"]), 1)

    def test_grep_results_are_relative_to_the_searched_folder(self):
        # Seen in a live run: a Grep of app/src listed tests/services/x.test.ts, a file of the app, not the harness tests/.
        listing = "tests/services/x.test.ts:20:  deletedAt\n"
        report = check([init(), use("a", "Grep", pattern="deletedAt", path=CWD + "/app/src"), result("a", listing)])
        self.assertEqual(report["violations"], [])
        report = check([init(), use("a", "Grep", pattern="deletedAt"), result("a", listing)])
        self.assertEqual(len(report["violations"]), 1)
        report = check([init(), use("a", "Grep", pattern="n", path=CWD + "/app/src"), result("a", "../../vault/policy-edit-window.md\n")])
        self.assertEqual(len(report["violations"]), 1)

    def test_a_path_outside_the_working_directory_is_a_violation(self):
        report = check([init(), use("a", "Read", file_path="/srv/other/repo/PLAN.md"), result("a")])
        self.assertEqual(len(report["violations"]), 1)
        self.assertIn("outside", report["violations"][0]["reasons"][0])

    def test_git_with_dash_c_and_note_paths_in_commands_are_caught(self):
        events = [init(), use("a", "Bash", command="git -C /somewhere diff"), result("a"),
                  use("b", "Bash", command="git show HEAD:vault/policy-edit-window.md"), result("b"),
                  use("c", "Bash", command="ls vault"), result("c"),
                  use("d", "Bash", command="git diff --stat"), result("d")]
        report = check(events)
        self.assertEqual(len(report["violations"]), 3)

    def test_a_denied_attempt_is_blocked_not_a_violation_unless_strict(self):
        events = [init(), use("a", "Bash", command="git -C /x diff"), denied("a"), result("a", "requires approval", error=True)]
        report = check(events)
        self.assertEqual((len(report["violations"]), len(report["blocked"])), (0, 1))
        path = os.path.join(tempfile.mkdtemp(), "t.jsonl")
        helpers.write_jsonl(path, events)
        self.assertEqual(run_main([path]), 0)
        self.assertEqual(run_main([path, "--strict"]), 1)

    def test_a_grep_whose_result_lists_the_plan_is_a_violation(self):
        listing = "app/src/a.ts:3:x\nPLAN.md:64:Maintainer changes the edit window\ndocs/walkthrough.md:21:y"
        report = check([init(), use("a", "Grep", pattern="edit window"), result("a", listing)])
        self.assertEqual(len(report["violations"]), 1)
        self.assertIn("PLAN.md", report["violations"][0]["reasons"][0])
        self.assertIn("docs/walkthrough.md", report["violations"][0]["reasons"][0])

    def test_neuron_tool_calls_are_ignored(self):
        report = check([init(), use("a", "mcp__okto-neuron__ask", question="q", vault="team"), result("a")])
        self.assertEqual(report["tool_calls"], 1)
        self.assertEqual(report["violations"], [])

    def test_a_glob_that_names_the_vault_is_caught(self):
        report = check([init(), use("a", "Glob", pattern="**/vault/*.md"), result("a", "")])
        self.assertEqual(len(report["violations"]), 1)


class PilotTranscripts(unittest.TestCase):
    """The committed pilot transcripts fail the checker. That is a labeled pilot finding, not something to weaken."""

    @classmethod
    def setUpClass(cls):
        folder = os.path.join(helpers.REPO, "demo-state", "transcripts")
        cls.reports = {n: ct.check_transcript(os.path.join(folder, n)) for n in sorted(os.listdir(folder))}

    def test_the_checker_fails_on_the_pilot(self):
        folder = os.path.join(helpers.REPO, "demo-state", "transcripts")
        paths = [os.path.join(folder, n) for n in sorted(os.listdir(folder))]
        self.assertEqual(run_main(paths), 1)

    def test_planner_read_the_notes_directly_at_step_2(self):
        reads = [v for v in self.reports["step02-planner.jsonl"]["violations"] if v["tool"] == "Read"]
        self.assertGreaterEqual(len(reads), 9)

    def test_builder_read_the_replaced_note_and_a_grep_returned_the_plan_at_step_5(self):
        violations = self.reports["step05-builder.jsonl"]["violations"]
        self.assertTrue(any(v["tool"] == "Read" and "policy-edit-window.md" in v["reasons"][0] for v in violations))
        self.assertTrue(any(v["tool"] == "Grep" and "PLAN.md" in v["reasons"][0] for v in violations))

    def test_git_attempts_on_vault_files_were_blocked_not_executed(self):
        blocked = " ".join(r for b in self.reports["step04-reviewer.jsonl"]["blocked"] for r in b["reasons"])
        self.assertIn("git run outside the working directory", blocked)

    def test_the_step_9_reviewer_is_clean(self):
        self.assertEqual(self.reports["step09-reviewer.jsonl"]["violations"], [])


if __name__ == "__main__":
    unittest.main()
