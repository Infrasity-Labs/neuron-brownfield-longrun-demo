import os
import subprocess
import tempfile
import unittest

import helpers  # noqa: F401
import build_workdir as bw

FORBIDDEN_TOP = ("vault", "vault-private", "docs", "demo-state", "scenarios", "agents", "labels", "runs", "scripts", "tests")


def tree_files(root):
    found = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        found += [os.path.relpath(os.path.join(base, f), root) for f in files]
    return sorted(found)


class RoleDirectories(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.canonical = os.path.join(cls.tmp, "canonical")
        bw.init_canonical(cls.canonical)

    def test_canonical_holds_only_app_specs_and_a_git_baseline(self):
        self.assertEqual(sorted(os.listdir(self.canonical)), [".git", ".gitignore", "app", "specs"])
        log = subprocess.run(["git", "-C", self.canonical, "log", "--format=%s"], capture_output=True, text=True).stdout
        self.assertEqual(log.strip(), "app baseline")
        self.assertFalse(os.path.exists(os.path.join(self.canonical, "app", "node_modules")))

    def test_no_role_can_see_a_note_the_plan_or_the_docs(self):
        for role in ("planner", "builder", "reviewer"):
            info = bw.build_role_dir(role, self.canonical, os.path.join(self.tmp, role))
            for entry in info["files"]:
                first = entry["path"].split(os.sep)[0]
                self.assertNotIn(first, FORBIDDEN_TOP, "%s sees %s" % (role, entry["path"]))
                self.assertNotEqual(entry["path"], "PLAN.md")
                self.assertNotEqual(entry["path"], "README.md")
            self.assertTrue(set(os.listdir(os.path.join(self.tmp, role))) <= bw.ALLOWED_TOP[role])

    def test_roles_get_different_views(self):
        planner = bw.build_role_dir("planner", self.canonical, os.path.join(self.tmp, "p"))["dest"]
        reviewer = bw.build_role_dir("reviewer", self.canonical, os.path.join(self.tmp, "r"))["dest"]
        self.assertTrue(os.path.isdir(os.path.join(planner, "specs")))
        self.assertFalse(os.path.exists(os.path.join(planner, ".git")))
        self.assertTrue(os.path.isdir(os.path.join(reviewer, "private-out")))
        self.assertFalse(os.path.exists(os.path.join(reviewer, "specs")))

    def test_verify_rejects_an_extra_top_level_entry(self):
        dest = bw.build_role_dir("planner", self.canonical, os.path.join(self.tmp, "v"))["dest"]
        os.makedirs(os.path.join(dest, "vault"))
        with self.assertRaises(RuntimeError):
            bw.verify("planner", dest)


class CarryingOutputBack(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.canonical = os.path.join(self.tmp, "canonical")
        bw.init_canonical(self.canonical)

    def test_builder_edits_reach_the_canonical_tree_and_show_in_git_diff(self):
        info = bw.build_role_dir("builder", self.canonical, os.path.join(self.tmp, "b"))
        work = info["dest"]
        target = os.path.join(work, "app", "src", "main.ts")
        with open(target, "a") as handle:
            handle.write("\n// edited by the builder\n")
        new_file = os.path.join(work, "app", "src", "tests", "services", "new.test.ts")
        with open(new_file, "w") as handle:
            handle.write("test('x', () => {});\n")
        result = bw.collect("builder", work, self.canonical)
        self.assertTrue(result["app_changed"])
        reviewer = bw.build_role_dir("reviewer", self.canonical, os.path.join(self.tmp, "r"))["dest"]
        diff = subprocess.run(["git", "-C", reviewer, "diff"], capture_output=True, text=True).stdout
        self.assertIn("edited by the builder", diff)
        self.assertIn("new.test.ts", diff, "a new file must be visible to `git diff` (intent-to-add)")

    def test_a_symlink_is_never_followed_or_copied(self):
        info = bw.build_role_dir("builder", self.canonical, os.path.join(self.tmp, "b"))
        secret = os.path.join(self.tmp, "secret.md")
        with open(secret, "w") as handle:
            handle.write("a note the role must not smuggle in")
        os.symlink(secret, os.path.join(info["dest"], "app", "linked.md"))
        result = bw.collect("builder", info["dest"], self.canonical)
        self.assertEqual(result["symlinks_skipped"], ["linked.md"])
        self.assertFalse(os.path.exists(os.path.join(self.canonical, "app", "linked.md")))

    def test_planner_specs_are_copied_only_when_markdown_and_small(self):
        info = bw.build_role_dir("planner", self.canonical, os.path.join(self.tmp, "p"))
        specs = os.path.join(info["dest"], "specs")
        with open(os.path.join(specs, "feature.md"), "w") as handle:
            handle.write("# spec\n")
        with open(os.path.join(specs, "notes.txt"), "w") as handle:
            handle.write("not markdown\n")
        with open(os.path.join(specs, "huge.md"), "w") as handle:
            handle.write("x" * (bw.MAX_SPEC_BYTES + 1))
        result = bw.collect("planner", info["dest"], self.canonical)
        self.assertEqual(result["specs"], ["feature.md"])
        self.assertEqual(os.listdir(os.path.join(self.canonical, "specs")), ["feature.md"])
        builder = bw.build_role_dir("builder", self.canonical, os.path.join(self.tmp, "b"))["dest"]
        self.assertEqual(os.listdir(os.path.join(builder, "specs")), ["feature.md"])

    def test_reviewer_findings_go_to_the_watched_private_folder(self):
        info = bw.build_role_dir("reviewer", self.canonical, os.path.join(self.tmp, "r"))
        with open(os.path.join(info["dest"], "private-out", "finding.md"), "w") as handle:
            handle.write("# finding\n")
        private = os.path.join(self.tmp, "vault-private")
        result = bw.collect("reviewer", info["dest"], self.canonical, private)
        self.assertEqual(result["private"], ["finding.md"])
        self.assertEqual(os.listdir(private), ["finding.md"])


if __name__ == "__main__":
    unittest.main()
