import json
import os
import tempfile
import unittest

import helpers  # noqa: F401
import metric
import study_summary as ss


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        json.dump(data, handle)


def make_run(runs, arm, run_id, edit_ok, cap_ok, cost=0.1, violations=0, spec_hits=0):
    """A synthetic run with constants. Nothing here is a recorded result."""
    run_dir = os.path.join(runs, arm, run_id)
    write(os.path.join(run_dir, "run-manifest.json"), {
        "metric": {"sha256": metric.metric_fingerprint()}, "started_at": "2026-11-01T10:00:00.000Z",
        "finished_at": "2026-11-01T10:10:00.000Z", "claude_flags": {"partial_run": False},
        "sessions": [{"total_cost_usd": cost, "duration_ms": 1000}] * 2,
        "checks": {"hard_failures": [], "isolation": {"transcripts": 2, "violations": violations, "blocked_attempts": 1},
                   "spec_rule_values": [{"rule": "edited-marker-name"}] * spec_hits}})
    cwd = "/tmp/role-work"
    clean = [{"type": "system", "subtype": "init", "cwd": cwd},
             {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "a", "name": "Read", "input": {"file_path": cwd + "/app/x.ts"}}]}},
             {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "a", "content": "ok"}]}}]
    dirty = [clean[0], {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "b", "name": "Read", "input": {"file_path": cwd + "/vault/n.md"}}]}},
             {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "b", "content": "ok"}]}}]
    os.makedirs(os.path.join(run_dir, "transcripts"), exist_ok=True)
    helpers.write_jsonl(os.path.join(run_dir, "transcripts", "step02-planner.jsonl"), clean)
    helpers.write_jsonl(os.path.join(run_dir, "transcripts", "step03-builder.jsonl"), dirty if violations else clean)
    write(os.path.join(run_dir, "code-outcome", "step5.json"), {"outcomes": {
        "edit-window/accepts-inside": "pass" if edit_ok else "fail", "edit-window/refuses-outside": "pass" if edit_ok else "fail"}})
    write(os.path.join(run_dir, "code-outcome", "step6.json"), {"outcomes": {
        "article-limit/caps-above": "pass" if cap_ok else "fail", "article-limit/keeps-below": "pass", "article-limit/keeps-default": "pass"}})


class Summary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.runs, self.labels = os.path.join(self.tmp, "runs"), os.path.join(self.tmp, "labels")
        make_run(self.runs, "none", "run-01", False, True)
        make_run(self.runs, "none", "run-02", True, True, cost=0.3, violations=1, spec_hits=1)
        make_run(self.runs, "notes", "run-01", True, True)

    def test_alignment_counts_only_the_executable_products_when_no_labels_exist(self):
        blocks = ss.render(ss.summarize(self.runs, self.labels))
        row = [line for line in blocks["study-alignment"].splitlines() if line.startswith("| A,")][0]
        self.assertIn("n=2, mean 0.500, sd 0.707, min 0.000, max 1.000", row)  # edit window product: 0 and 1
        self.assertIn("2 of 11", row)
        self.assertIn("0 of 2 runs labeled", row)
        empty = [line for line in blocks["study-alignment"].splitlines() if line.startswith("| C,")][0]
        self.assertIn("| none | none | none |", empty)

    def test_conduct_row_sums_isolation_and_spec_hits_and_reports_cost_spread(self):
        row = [l for l in ss.render(ss.summarize(self.runs, self.labels))["study-conduct"].splitlines() if l.startswith("| A,")][0]
        cells = [c.strip() for c in row.strip("|").split("|")]
        self.assertEqual(cells[1:7], ["2", "4", "1", "0", "1 of 2", "0"])  # recomputed from the transcripts: one session reached vault/
        self.assertIn("mean 0.400", cells[7])  # runs cost 0.2 and 0.6
        self.assertIn("min 0.200, max 0.600", cells[7])

    def test_a_block_in_a_document_is_checked_and_rewritten(self):
        summary = ss.summarize(self.runs, self.labels)
        name = "study-alignment"
        text = "intro\n%s\nstale\n%s\noutro\n" % (ss.marker(name, True), ss.marker(name, False))
        self.assertEqual(len(ss.check_text(text, summary)), 1)
        fixed = ss.replace_block(text, name, ss.render(summary)[name])
        self.assertEqual(ss.check_text(fixed, summary), [])
        self.assertTrue(fixed.startswith("intro\n") and fixed.endswith("outro\n"))

    def test_a_document_without_blocks_is_not_an_error(self):
        self.assertEqual(ss.check_text("no blocks here", ss.summarize(self.runs, self.labels)), [])


class DaemonUsage(unittest.TestCase):
    def test_usage_and_failed_calls_are_counted_from_log_lines(self):
        import daemon_usage
        path = os.path.join(tempfile.mkdtemp(), "serve.log")
        lines = [{"ts": "t1", "level": "info", "msg": "litellm usage model=anthropic/m prompt_tokens=10 completion_tokens=2 cached_tokens=0 step=curator"},
                 {"ts": "t2", "level": "info", "msg": "litellm usage model=anthropic/m prompt_tokens=5 completion_tokens=1 cached_tokens=0 step=extract"},
                 {"ts": "t3", "level": "warning", "msg": "litellm completion failed for anthropic/m: litellm.AuthenticationError: invalid"}]
        with open(path, "w") as handle:
            handle.write("\n".join(json.dumps(l) for l in lines) + "\nnot json\n")
        result = daemon_usage.summarize(path)
        self.assertEqual((result["successful_model_calls"], result["prompt_tokens"], result["completion_tokens"]), (2, 15, 3))
        self.assertEqual(result["failed_by_exception"], {"AuthenticationError": 1})
        self.assertEqual(result["calls_by_step"], {"curator": 1, "extract": 1})


if __name__ == "__main__":
    unittest.main()
