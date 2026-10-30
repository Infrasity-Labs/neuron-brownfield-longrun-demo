# runs

New runs are recorded here, one folder per run: `runs/<arm>/<run-id>/`, with `<arm>` one of `none` (A), `notes` (B), `neuron` (C).

**Recorded here (2026-10-29, UTC):** `none/run-01` to `run-05`, `notes/run-01` to `run-05`, `neuron/run-01` to `run-05`, and
`negative/neg-01` (the negative boundary test). Every run used `claude-haiku-5-5`; the manifests hold the versions. The five
`neuron` runs were made side by side, each on its own isolated daemon; `none` and `notes` were two series of five run one after the
other. The tables over these runs are in the README ("The Comparison") and in `docs/METRIC.md` ("Results"). The pilot in
`demo-state/` is not comparable (see `demo-state/README.md`).

`harness-changes-after-launch.diff` is the difference between the scripts the 15 runs were launched with and the scripts of this
repository now: checker corrections made while looking at the runs (`docs/VERIFIED.md`, "Live study"), the scoring and summary
scripts, and one fix to the order in which the manifest is made. The manifests' `repo.harness.sha256` identifies the launch state.
Runs 2 to 5 of arms A and B show another hash than run 1 only because the fingerprint was taken before the notes were reset
(re-computed on the launch copies after a reset, all give the hash of run 1); the runner now resets first.

A run folder, written by `python3 run_demo.py --arm <arm> --run-id <id>`:

| Path | What |
|---|---|
| `run-manifest.json` | Neuron, claude CLI, model, Node, Python, OS, repository commit, metric fingerprint, per-session facts, check results |
| `events.jsonl` | One UTC timeline: edits, ingest complete, state probes, asks, role start and end, outage start and end |
| `transcripts/` | One stream-json transcript per role session |
| `workdir-manifests/` | The files each role could see, with sizes and SHA-256 |
| `asks.jsonl`, `explores.jsonl`, `ingest-times.jsonl`, `closeout-result.json` | Arm neuron only |
| `probes/` | Raw ask and explore results right after each edit, with the derived summary (arm neuron) |
| `diffs/` | Diff of the code after each Builder step |
| `code-outcome/` | `baseline.json` (the check on the untouched app, run before the first model call), `stepN.json` (live results, the ones that are scored) and `rescore-stepN.json` (the same check re-run from `diffs/stepN.diff` by `scripts/rescore_outcomes.py`, with `failure_details`) |
| `daemon-usage.json` | Arm neuron only: the isolated daemon's own count of model calls and tokens, from its log (`scripts/daemon_usage.py`) |

Score the runs with `python3 scripts/score_runs.py` (hand labels, when `labels/<arm>/<run-id>.json` hold some, `labels/README.md`;
without labels only the two executable products are scored), and summarise them with `python3 scripts/study_summary.py`.
A run is committed with its transcripts, so scan it first: `python3 scripts/scan_personal.py`.
