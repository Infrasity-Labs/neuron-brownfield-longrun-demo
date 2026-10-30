# Alignment metric (version 1)

This file defines the metric. It was written before any comparison run was recorded, and the runs under `runs/` were made
under it. Changing the definition after a run has been recorded invalidates that run: `run_demo.py` stores the SHA-256 of
the definition (this file up to the `END definition` line, not the results after it) and of `scenarios/work_products.json`
in every `run-manifest.json`, and `scripts/score_runs.py` refuses to mix runs recorded under a different definition.
`scenarios/metric-equivalents.json` lists earlier texts of this same definition, with the reason: the 15 runs of
2026-10-29 were recorded while the status paragraph of this file still said that no run existed, and that paragraph was
then moved out of the definition.

Status and results: see "Results" at the end of this file. The only run outside it is the pilot (`demo-state/README.md`),
which is scored by nothing here.

## What is measured

"Aligned" means: the work product uses the rule that is current when the product is made.

Two rules change during a run (the edit window at step 4, the error response shape at step 7). One rule never
changes (the article list cap) and serves as a control for the rule-change effect.

A **work product** is one of: the code a Builder wrote, the tests a Builder wrote, the spec a Planner wrote, the
verdict a Reviewer gave. The list is in `scenarios/work_products.json` (11 products per run).

Each product scores:

| Score | Meaning |
|---|---|
| 1 | It uses the current rule. For a Reviewer verdict: the verdict is correct for the code in the tree under the current rule (FLAG or NOT APPROVED when the code breaks the rule, PASS or APPROVED when it keeps it). |
| 0 | It does not. |
| left out | The product was not produced, or cannot be judged (for example the Builder wrote no tests). It is counted in the report, not in the fraction. |

## Per run

- `alignment_changed` = products scored 1 / products scored, over the products of the two rules that change.
- `alignment_stable` = the same fraction over the article cap products.
- Per role: the same fraction over the products of one role.
- `scored` = how many of the 11 products could be scored.

## Per arm

Reported for each arm (A no memory, B notes pasted into the prompt, C Neuron): the number of runs `n`, the mean, the
sample standard deviation, the minimum and the maximum of `alignment_changed`, and the same for `alignment_stable`.
A run with fewer than 11 scored products is listed with its count. **At least 5 runs per arm** are needed before
the README may state a comparison; with fewer, the README must say that no comparison is supported.

## Who scores what

- `exec` products are scored by `scripts/code_outcome.py`, which runs `scenarios/checks/outcome.check.ts` on the
  code in the run's own copy of `app/`:
  - the edit endpoint accepts an edit 1 minute inside the window and refuses one 1 minute outside it (with the
    30 minute window: accepts minute 29, refuses minute 31);
  - `GET /api/articles?limit=51` reads at most 50 rows, `limit=20` reads 20, no limit reads 10.
  A product is 1 only when every check listed for it passes.
- `label` products are scored by a named human in `labels/<arm>/<run-id>.json`, see `labels/README.md`. The labeler
  writes the evidence (transcript line or diff hunk) for each score. Labeling without looking at which arm the run
  belongs to is recommended and recorded in the file (`blind`).
- No LLM judge is used. If one is added later it must use a model different from the agents and from Neuron's
  extractor, and it must be measured against a hand-labeled sample before its scores are used.

## What this metric does not measure

- Whether the answers Neuron gives are true to the notes (that is the citation work in the close-out).
- Cost, speed, or how many questions the roles asked.
- Anything about models other than the one pinned in `pins.json`.

## Controls held equal across arms

The task prompts (`docs/prompts/`), the fixed questions (`docs/questions.json`), the shared standing rules
(`agents/common.md`), the role files, the model, `--max-turns`, and the tool limits are identical. The arms differ
only in the "Where the rules come from" section of the prompt, in Neuron's tool list and skill file (arm C only), and
in step 9, which needs a Neuron daemon and is skipped in arms A and B.

<!-- END definition -->

## Results (not part of the definition)

Recorded under this definition: 15 runs, 5 per arm, on 2026-10-29 (UTC), every role and Neuron on `claude-haiku-5-5`,
Okto Neuron 0.3.1, Claude Code 2.1.312 (`runs/<arm>/run-01` to `run-05`). **Hand labels: none.** Nine of the eleven
products per run are `label` products, so they are left out of every fraction and counted in "Products scored per run".
The two `exec` products were scored by `scripts/code_outcome.py` live during each run, and re-scored from the recorded diffs by
`scripts/rescore_outcomes.py` (all 60 re-scored trees gave the live result). The tables are generated from the run folders by
`scripts/study_summary.py`; `scripts/check_readme.py` fails when they differ from the runs.

<!-- BEGIN study-alignment -->
| Arm | Runs recorded | Alignment, rules that change (n, spread) | Alignment, rule that does not change (n, spread) | Products scored per run | Hand labels |
| --- | ------------- | ----------------------------------------- | ------------------------------------------------ | ----------------------- | ----------- |
| A, no memory | 5 | n=5, mean 0.000, sd 0.000, min 0.000, max 0.000 | n=5, mean 0.000, sd 0.000, min 0.000, max 0.000 | 2 of 11 | 0 of 5 runs labeled |
| B, notes in the prompt | 5 | n=5, mean 0.400, sd 0.548, min 0.000, max 1.000 | n=5, mean 1.000, sd 0.000, min 1.000, max 1.000 | 2 of 11 | 0 of 5 runs labeled |
| C, Neuron | 5 | n=5, mean 0.800, sd 0.447, min 0.000, max 1.000 | n=5, mean 1.000, sd 0.000, min 1.000, max 1.000 | 2 of 11 | 0 of 5 runs labeled |
<!-- END study-alignment -->

Each arm has the 5 scored runs the metric asks for, but only on the two executable products, one of which belongs to the rules
that change and one to the rule that does not. A run's fraction is therefore 0 or 1, the mean is the share of runs that
passed, and the standard deviation is the sample standard deviation of those 0s and 1s. The metric is not complete until the
other nine products are labeled; until then a difference between arms is a difference on one executable check.

<!-- BEGIN study-outcomes -->
| Arm | Runs | step 3 accepts-inside | step 3 refuses-outside | step 5 accepts-inside | step 5 refuses-outside | step 6 caps-above | step 6 keeps-below | step 6 keeps-default |
| --- | ---- | --- | --- | --- | --- | --- | --- | --- |
| A, no memory | 5 | 5 of 5 | 0 of 5 | 5 of 5 | 0 of 5 | 0 of 5 | 5 of 5 | 5 of 5 |
| B, notes in the prompt | 5 | 5 of 5 | 1 of 5 | 5 of 5 | 2 of 5 | 5 of 5 | 5 of 5 | 5 of 5 |
| C, Neuron | 5 | 5 of 5 | 4 of 5 | 5 of 5 | 4 of 5 | 5 of 5 | 5 of 5 | 5 of 5 |
<!-- END study-outcomes -->

<!-- BEGIN study-refusal -->
| Arm | Runs | Step 5 code accepts minute 29 | Edit at minute 31: refused with a 4xx (counts as aligned) | refused with a 5xx (an unhandled error; does not count) | not refused, the edit went through | other |
| --- | ---- | ----------------------------- | ---------------------------------------------------------- | -------------------------------------------------------- | ---------------------------------- | ----- |
| A, no memory | 5 | 5 of 5 | 0 | 0 | 5 | 0 |
| B, notes in the prompt | 5 | 5 of 5 | 2 | 3 | 0 | 0 |
| C, Neuron | 5 | 5 of 5 | 4 | 1 | 0 | 0 |
<!-- END study-refusal -->

The check demands that an edit one minute outside the window is refused with a 4xx; a 500 does not count (the check's own
comment says a 500 is a crash, not a rule, written before the runs). The last table shows how much of arm B's and arm C's
score depends on that: counting a 5xx as a refusal gives both arms 5 of 5. That reading was not adopted, because the
check (`scenarios/checks/outcome.check.ts`) was fixed before the runs; the definition above says only "refuses".
