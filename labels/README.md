# Labels

Hand labels for the alignment metric (`docs/METRIC.md`) and for the citation-support sample. **Nobody has labeled
anything yet.** What is here for the 15 runs of 2026-10-29 is the material for a person to label, all empty: 15 alignment
sheets (`labels/<arm>/run-0N.json`, `labeler` empty, every `value` null) and 5 citation-support samples
(`labels/support-sample-neuron-run-0N.json`, 10 answers each with the cited text, every `supported` null). Nothing in this
folder is a result. Files here are filled in by a named person after a run exists. For a blind label, read the transcripts
and diffs without looking at which arm the folder name belongs to (the sheets are per arm; a person can be handed copies
renamed by someone else, and the key kept apart).

## Alignment labels: `labels/<arm>/<run-id>.json`

Create the empty sheet for a recorded run with

    python3 scripts/make_label_sheet.py runs/<arm>/<run-id>

It writes every label product with `"value": null` and tells you which transcript and diff to read. Fill it in:

```json
{
  "schema": "neuron-demo-labels/1",
  "arm": "neuron",
  "run_id": "run-01",
  "labeler": "full name of the person who labeled",
  "labeled_at": "2026-11-02T10:00:00Z",
  "blind": true,
  "labels": {
    "edit-window/builder-step5/tests": {"value": 1, "evidence": "transcripts/step05-builder.jsonl line 31", "note": ""}
  }
}
```

- `value`: `1` the product uses the current rule, `0` it does not, `null` not produced or not judgeable.
- `labeler` must be a real name and `labeled_at` a UTC time. A sheet without them is rejected by the scorer.
- `blind`: `true` when the labeler did not know the arm while labeling.
- `exec` products (code scored by the outcome check) are not labeled; the scorer reads `code-outcome/`.

## Citation-support sample: `labels/support-sample-*.json`

A hash check shows that cited bytes exist. It does not show that the answer is supported by them. Create a sample with

    python3 scripts/support_sample.py make --asks demo-state/asks.jsonl --n 50 --seed 1 --out labels/support-sample-pilot.json

Each entry holds the question, the answer text, the cited byte ranges and `"supported": null`. A person reads the cited
text and sets `supported` to `1` (every claim in the answer is in the cited text), `0.5` (some are) or `0` (none are),
fills `labeler` and `labeled_at`, and `python3 scripts/support_sample.py report FILE` prints the rate. An unlabeled
sheet reports "not labeled". The samples of the new runs were made with

    python3 scripts/support_sample.py make --asks runs/neuron/run-0N/asks.jsonl --n 10 --seed 1 --vault-root team=<home>/.okto-neuron/vaults/team --vault-root reviewer-private=<home>/.okto-neuron/vaults/reviewer-private --out labels/support-sample-neuron-run-0N.json

while the run's isolated daemon home still existed, which is why `cited_text` is present for most sources: the cited bytes
were read from the vault and checked against the recorded hash at that time. A source whose anchor was already stale has no
`cited_text`, and the person labels it as unsupported or not judgeable.

## Private-fact check: `scenarios/private-facts.json`

`closeout.py` lists team answers that match a private fact (see `scenarios/private-facts.json`) as leak candidates.
A person decides each candidate and records the verdict in the run's labels file under `private-leak/<fact id>`.
