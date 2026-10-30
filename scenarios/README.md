# scenarios

The inputs of the experiment that are not code: the start and post-change notes, the synthetic private notes, the rule
values that must never appear in an instruction, the work products the metric scores, and the executable outcome check.

## Starting state and the two rule changes

`vault/` holds the starting state and is the folder Neuron watches for the `team` vault. A fresh clone starts before any change:
the edit window note says 15 minutes, and the error response note describes the errors-by-field body.

| Step | Maintainer action | Starting note | Post-change note |
|---|---|---|---|
| 4 | edit window changes | `step04/before/policy-edit-window.md` (15 minutes, identical to `vault/policy-edit-window.md`) | `step04/after/policy-edit-window.md` (30 minutes) |
| 7 | error rule replaced, runbook added | `step07/before/policy-error-response.md` (identical to `vault/`) | `step07/after/policy-error-response.md`, `step07/after/ops-runbook.md` (new note, still describes the replaced rule) |

`python3 scripts/maintainer_edit.py step4` (or `step7`) copies the `after/` files into `vault/` and records a `maintainer_edit` event.
`python3 scripts/reset.py` (also `python3 run_demo.py --reset`) restores the `before/` files, deletes the added note, removes
`vault/specs/`, and reseeds `vault-private/` from `private-notes/`. `python3 scripts/reset.py --check` reports any drift.

The starting texts of the two notes that change were recovered from the Read tool results recorded in the pilot's step 2 Planner
transcript, so the 15-minute and errors-by-field versions are the ones the pilot actually used, apart from the rewrite below.
The post-change error note says "This replaces the older errors-by-field body": that sentence is part of the rule text, is seen
by every arm that sees notes, and may be what Neuron's `replaces` claim comes from (`docs/PRODUCT-OBSERVATIONS.md`, item 4).

## What each note is

`notes.json` labels every note. Summary:

- **Derived from code (7).** `vault/code-*.md`: a summary the demo author wrote from the file named on its first line. They are
  descriptions of the app, and a summary can steer a Builder as much as the code does. Each can be checked against its source.
- **Synthetic (6 start notes, 3 post-change notes, 3 private notes, 1 decoy note).** `vault/policy-*.md` and the files under
  `step04/`, `step07/`, `private-notes/`, `decoy-notes/`: rules invented for this demo. Nothing in the app enforces them. They are
  written the way a team would write them: they no longer say "demo policy" or "not behaviour of the app" (the pilot's notes did, on
  every policy, which told the agent that the rule was artificial and fed the extractor). The notes were rewritten, so the pilot's
  recorded byte ranges do not apply to them.
- **A rule that exists only in code.** The pilot had a note summarising how `GET /api/articles` reads `limit` and `offset`
  (`code-article-paging.md`). It was removed: the default limit and offset behaviour is now stated in no note, so a Builder that has to
  cap the limit must read `getArticles` and connect it with the cap in `policy-article-list-limit.md`.

The pilot started with 14 notes; the next runs start with 13.

## Private notes and the leak check

`private-notes/` holds three synthetic Reviewer findings, loaded into the `reviewer-private` vault at step 1. They exist so that the
private-leak check can be rerun by anyone: `scripts/closeout.py` takes their sentences as leak markers, and
`private-facts.json` lists each fact with keyword groups so that a paraphrase is a leak candidate. A candidate needs a human verdict
(`labels/README.md`). The pilot's real private notes were not shipped, so the pilot's "0 private notes in team answers" cannot be rerun.

## Other files

| File | What |
|---|---|
| `rule_values.json` | Patterns for every rule value; `scripts/scan_rule_values.py` fails on a hit in a prompt, a fixed question, an agent file, a recorded question or a spec |
| `work_products.json` | The 11 work products of the metric (`docs/METRIC.md`) |
| `checks/outcome.check.ts` | The executable outcome check (`scripts/code_outcome.py`) |
| `decoy-notes/` | A note for the `decoy` vault, used only by `scripts/negative_test.py` |
