# Model-labelled drafts

**These are not hand labels.** On 2026-10-30 a model (`claude-sonnet-5-5`, run as a subagent) drafted labels for the same sheets that are empty in `labels/`. Every file here names the labeler as `claude-sonnet-5-5 (omp subagent), model-labelled, not human` and sets `blind` to false (the labeler could see the arm). Yuvi read the summaries and sampled examples of these drafts on 2026-10-30 and found no problems; nobody has read every label.

The metric definition (`docs/METRIC.md`) says no LLM judge is used until it is measured against a hand-labelled sample. That has not happened, so **nothing here feeds the README tables or any published score.** The scorer does not know the difference: `scripts/score_runs.py --labels-dir labels-model` accepts these files because the labeler field is not empty. That is how `draft-scores.json` was made, and it is the only use of these files.

The labeler is a different model from the agents that produced the evidence (`claude-haiku-5-5`) and from Neuron's extractor (`claude-haiku-5-5`), but it is the same vendor family. Shared blind spots are possible.

## What is here

| File | What |
|---|---|
| `<arm>/run-0N.json` | The 15 alignment sheets (9 labelled products per run). Across all 135 labels: 85 are 1, 28 are 0, 22 are null (not produced or not judgeable). Every set label has a quoted reason in `evidence` or `note`. |
| `support-sample-neuron-run-0N.json` | The 50 citation-support answers. 39 scored 1, 9 scored 0.5, 2 scored 0; mean 0.87. Judged against each entry's own `cited_text` only; an entry whose source has no `cited_text` (stale anchor) is scored down. The pilot's 35-entry sample was not labelled. |
| `neuron/run-0N.json`, key `private-leak/...` | Private-fact check. No automatic candidate was flagged in any of the 5 Neuron-arm runs, and the labeler found no reworded private fact in the 170 `team` answers it read (keyword scans plus reading, with truncated answers). So there are no `private-leak/` entries. |
| `REPORT-none.md`, `REPORT-notes.md`, `REPORT-neuron.md`, `REPORT-support.md` | The labeler's own reports: counts, the items it was least sure of, and oddities in the source material. |
| `draft-scores.json` | `score_runs.py` output with these drafts. Not published: see above. |

## What the drafts say (and why not to read much into it)

`alignment_changed` (the rule that changes, executable and labelled products together), mean over 5 runs: no memory 0.300, notes 0.908, Neuron 0.833. `alignment_stable` (article cap): 0.467, 1.000, 1.000. The first ordering says memory of any kind beats none; it does not separate notes from Neuron. This is the same picture as the two executable products alone (README), but the drafts rest on one model's reading of transcripts.

## Where the labeler flagged that a person must choose a reading

- `error-response/builder-step8/code` and `/tests`: the step 8 Builders added no new error path, so the labeler left most of these null. A literal reading of "in the diff" would score the old-shape errors from earlier steps as 0; a person has to pick the reading.
- Step 5 Reviewer verdicts in Neuron-arm runs 1 and 5 said the 30-minute window passes but ended NOT APPROVED over a 403 status; the labeler scored them 0 because the verdict was not given for the window. In run 2 the Reviewer approved code that throws a plain 500 on an expired edit; the labeler scored it 0 because it did not count a 500 as a refusal, and it would be 1 if a 5xx counted (the same issue that decides the executable result in the README).
- Arm `none` reviewers had no rule source at all, so "NOT APPROVED" is scored by outcome (the tree has no window), not by their reasoning.
- `diffs/stepN.diff` are cumulative from the baseline, not per step, so a step 8 diff contains the step 3 code.

## What a person still has to do

Spot-check a random sample of these files, then either label `labels/<arm>/run-0N.json` and `labels/support-sample-*.json` by hand (the format is in `labels/README.md`) or record how often the drafts agree with a person. Only then can the model drafts be used as a judge. The sheets in `labels/` stay empty until a named person fills them.
