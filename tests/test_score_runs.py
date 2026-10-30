import json
import os
import tempfile
import unittest

import helpers  # noqa: F401
import make_label_sheet as mls
import metric
import score_runs as sr


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        json.dump(data, handle)


def make_run(runs, labels_dir, arm, run_id, exec_pass, label_value, labeler="A Person", fingerprint=None):
    """A synthetic run: executable results and labels set to constants. Nothing here is a recorded result."""
    run_dir = os.path.join(runs, arm, run_id)
    write(os.path.join(run_dir, "run-manifest.json"), {"metric": {"sha256": fingerprint or metric.metric_fingerprint()}})
    spec = metric.load_products()
    for product_id, check in spec["exec_checks"].items():
        write(os.path.join(run_dir, "code-outcome", check["label"] + ".json"),
              {"outcomes": {o: "pass" if exec_pass else "fail" for o in check["outcomes"]}})
    labels = {pid: {"value": label_value, "evidence": "x"} for pid in metric.product_ids("label")}
    write(os.path.join(labels_dir, arm, run_id + ".json"),
          {"schema": "neuron-demo-labels/1", "arm": arm, "run_id": run_id, "labeler": labeler,
           "labeled_at": "2026-11-01T10:00:00Z", "blind": True, "labels": labels})


class Scoring(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.runs, self.labels = os.path.join(self.tmp, "runs"), os.path.join(self.tmp, "labels")

    def test_no_runs_is_reported_plainly(self):
        summary = sr.collect(self.runs, self.labels)
        self.assertEqual(sr.render(summary), "no recorded runs to score")

    def test_mean_spread_and_n_per_arm(self):
        make_run(self.runs, self.labels, "neuron", "run-01", True, 1)
        make_run(self.runs, self.labels, "neuron", "run-02", False, 0)
        make_run(self.runs, self.labels, "none", "run-01", False, 0)
        summary = sr.collect(self.runs, self.labels)
        neuron = summary["arms"]["neuron"]["alignment_changed"]
        self.assertEqual((neuron["n"], neuron["mean"], neuron["min"], neuron["max"]), (2, 0.5, 0.0, 1.0))
        self.assertAlmostEqual(neuron["stdev"], 0.7071, places=3)
        self.assertEqual(summary["arms"]["none"]["alignment_changed"]["n"], 1)
        self.assertIsNone(summary["arms"]["none"]["alignment_changed"]["stdev"])
        self.assertIn("no comparison is supported", sr.render(summary))

    def test_a_run_without_labels_scores_only_what_the_executable_check_gives(self):
        make_run(self.runs, self.labels, "neuron", "run-01", True, 1)
        os.remove(os.path.join(self.labels, "neuron", "run-01.json"))
        run = sr.collect(self.runs, self.labels)["arms"]["neuron"]["runs"][0]
        self.assertFalse(run["labeled"])
        self.assertEqual(run["scored"], 2)  # the two executable products only
        self.assertEqual(run["products"]["edit-window/builder-step5/tests"], None)

    def test_labels_without_a_named_labeler_are_rejected(self):
        make_run(self.runs, self.labels, "neuron", "run-01", True, 1, labeler="")
        summary = sr.collect(self.runs, self.labels)
        self.assertTrue(any("labeler is empty" in s["reason"] for s in summary["skipped"]))
        self.assertFalse(summary["arms"]["neuron"]["runs"][0]["labeled"])

    def test_a_run_recorded_under_another_metric_definition_is_left_out(self):
        make_run(self.runs, self.labels, "neuron", "run-01", True, 1, fingerprint="0" * 64)
        summary = sr.collect(self.runs, self.labels)
        self.assertEqual(summary["arms"], {})
        self.assertIn("different metric definition", summary["skipped"][0]["reason"])

    def test_results_after_the_definition_end_marker_do_not_change_the_fingerprint(self):
        import shutil
        repo = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(repo, "docs"))
        os.makedirs(os.path.join(repo, "scenarios"))
        shutil.copy(os.path.join(helpers.REPO, "scenarios", "work_products.json"), os.path.join(repo, "scenarios"))
        path = os.path.join(repo, "docs", "METRIC.md")
        with open(path, "w") as handle:
            handle.write("definition\n" + metric.DEFINITION_END + "\nresults one\n")
        first = metric.metric_fingerprint(repo)
        with open(path, "w") as handle:
            handle.write("definition\n" + metric.DEFINITION_END + "\nresults two, longer\n")
        self.assertEqual(metric.metric_fingerprint(repo), first)
        with open(path, "w") as handle:
            handle.write("definition changed\n" + metric.DEFINITION_END + "\nresults one\n")
        self.assertNotEqual(metric.metric_fingerprint(repo), first)

    def test_a_listed_equivalent_fingerprint_is_accepted_and_an_unlisted_one_is_not(self):
        listed = metric.accepted_fingerprints()
        self.assertEqual(listed[0], metric.metric_fingerprint())
        self.assertGreater(len(listed), 1)  # the fingerprint the 2026-10-29 runs were recorded under
        make_run(self.runs, self.labels, "neuron", "run-01", True, 1, fingerprint=listed[1])
        make_run(self.runs, self.labels, "neuron", "run-02", True, 1, fingerprint="f" * 64)
        summary = sr.collect(self.runs, self.labels)
        self.assertEqual([r["run_id"] for r in summary["arms"]["neuron"]["runs"]], ["run-01"])
        self.assertEqual([s["run_id"] for s in summary["skipped"]], ["run-02"])

    def test_an_executable_error_leaves_the_product_out(self):
        make_run(self.runs, self.labels, "neuron", "run-01", True, 1)
        write(os.path.join(self.runs, "neuron", "run-01", "code-outcome", "step5.json"),
              {"outcomes": {"edit-window/accepts-inside": "error", "edit-window/refuses-outside": "pass"}})
        run = sr.collect(self.runs, self.labels)["arms"]["neuron"]["runs"][0]
        self.assertIsNone(run["products"]["edit-window/builder-step5/code"])


class LabelSheets(unittest.TestCase):
    def test_the_sheet_is_empty_and_never_overwritten(self):
        tmp = tempfile.mkdtemp()
        run_dir = os.path.join(tmp, "runs", "neuron", "run-01")
        os.makedirs(run_dir)
        target = mls.make_sheet(run_dir, os.path.join(tmp, "labels"))
        with open(target) as handle:
            sheet = json.load(handle)
        self.assertEqual((sheet["arm"], sheet["run_id"], sheet["labeler"], sheet["labeled_at"]), ("neuron", "run-01", "", ""))
        self.assertEqual(sorted(sheet["labels"]), sorted(metric.product_ids("label")))
        self.assertTrue(all(entry["value"] is None for entry in sheet["labels"].values()))
        with self.assertRaises(FileExistsError):
            mls.make_sheet(run_dir, os.path.join(tmp, "labels"))

    def test_no_label_has_been_filled_in(self):
        # Empty sheets made by scripts/make_label_sheet.py are committed; a person's labels are not here yet. When a person
        # labels a sheet this test is to be changed with that commit, not worked around.
        labels = os.path.join(helpers.REPO, "labels")
        found = [os.path.join(b, f) for b, _d, fs in os.walk(labels) for f in fs if f.endswith(".json")]
        for path in found:
            with open(path) as handle:
                data = json.load(handle)
            if data.get("schema") == "neuron-demo-support-sample/1":
                self.assertTrue(all(e["supported"] is None for e in data["entries"]), path)
            elif data.get("schema") == "neuron-demo-labels/1":
                self.assertEqual((data["labeler"], data["labeled_at"]), ("", ""), path)
                self.assertTrue(all(e["value"] is None for e in data["labels"].values()), path)
            else:
                self.fail("unexpected label file %s" % path)


class MetricDefinition(unittest.TestCase):
    def test_exec_checks_refer_to_exec_products_and_known_outcomes(self):
        import code_outcome
        spec = metric.load_products()
        self.assertEqual(sorted(spec["exec_checks"]), sorted(metric.product_ids("exec")))
        for check in spec["exec_checks"].values():
            for outcome in check["outcomes"]:
                self.assertIn(outcome, code_outcome.OUTCOME_IDS)

    def test_the_metric_document_names_every_product_count(self):
        with open(os.path.join(helpers.REPO, "docs", "METRIC.md")) as handle:
            text = handle.read()
        self.assertIn("%d products per run" % len(metric.load_products()["products"]), text)


if __name__ == "__main__":
    unittest.main()
