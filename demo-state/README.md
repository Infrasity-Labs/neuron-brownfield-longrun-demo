# demo-state: the pilot run

Everything in this folder (except this file) is the record of **one pilot run**, steps 2 to 9 plus the close-out, made on
2026-10-23 before the isolation, arms and metric work existed. It is kept as a labeled pilot. It is **not** reference evidence
for a comparison and nothing here may be read as "Neuron keeps agents aligned". New runs are recorded under `runs/<arm>/<run-id>/`
(15 runs, 5 per arm, made on 2026-10-29 in the isolated design), and the pilot's numbers are never edited.

**What the new runs say about the pilot's two main observations** (details: `README.md`, "The Comparison", and
`docs/PRODUCT-OBSERVATIONS.md`). The pilot's 5 answers that still gave the replaced edit window after the edit did not recur: in
the 5 isolated Neuron-arm runs, 0 answers gave a replaced value after its edit and Neuron's neutral probe after each edit gave
the new value in 10 of 10. That fits the reading that the pilot's stale answers came from the confounds the pilot had (a spec that
copied the value, roles that read notes from disk), but 5 runs do not prove it. The pilot's stale anchors did recur at a lower
rate: 151 of 3,479 citations in the new runs (4.3%) against 125 of 763 (16%) in the pilot, with no spec in the watched folder.
The pilot's absence of any supersession signal also recurred: no new probe contained the word "supersed".

Edits made to these files after the pilot, listed so the record stays honest:

- Absolute paths, the working folder name and a personal vault name were replaced with placeholders (`<HOME>`, `<REPO>`,
  `<other-vault>`) by `scripts/scan_personal.py --redact`. No number, answer or timestamp changed.
- The three screenshots showed the author's home folder and a personal vault name in their pixels. Those few text regions were
  covered and redrawn with the placeholders `<HOME>` and `<vault>`; nothing else in the images changed.
- `docs/images/architecture.png`: the label under `vault/` said "14 team notes" (the pilot's count) and was redrawn as "13 team notes", the
  size of the starting set; nothing else in the image changed. `docs/images/banner-flat.png` was viewed and shows no path, user name or vault name.
- `closeout-result.json` gained five derived keys (`questions_with_sources_and_answer`, `stale_anchor_failures`,
  `other_citation_failures`, `stale_anchor_failures_by_note`, `stale_anchor_asks`) from `scripts/closeout.py --amend`. Every
  other key is byte for byte as recorded; `tests/test_closeout.py` recomputes the derived keys from `asks.jsonl` and checks both.
- `pilot-builder-edits.patch` and `pilot-specs/` were added: the code the pilot's Builders wrote and the specs its Planners wrote.
  They used to sit in `app/` and `vault/specs/`, which are now the starting state.

## Pilot findings (what the pilot cannot support)

These come from the checkers added later, run on the committed pilot files. They are findings about the pilot, not failures to fix.

1. **The roles were not isolated.** `python3 scripts/check_transcripts.py demo-state/transcripts/*.jsonl` exits 1: 10 of 12 transcripts
   reached note, plan or harness paths with a tool call that succeeded, 37 calls in all (22 `Read`, 8 `Write`, 5 `Glob`, 2 `Grep`; the
   Writes are the Planner's specs and the Reviewer's private findings, which were shared channels). A further 13 attempts were blocked
   by the tool allow-list, most of them `git -C ... diff` and `git show HEAD:vault/policy-edit-window.md`. Examples: the step 2 Planner
   read nine note files; the step 5 Builder read `vault/policy-edit-window.md`, and one `Grep` it ran returned `PLAN.md`,
   `docs/walkthrough.md` and `docs/VERIFIED.md` among its hits.
2. **Questions carried rule values.** `python3 scripts/scan_rule_values.py --asks demo-state/asks.jsonl` finds 7 recorded questions that
   contain a rule value, among them line 15 ("Which value is current, 15 or 30 minutes?").
3. **No control arm, one run, no hand labels.** See `docs/METRIC.md`.
4. **The session versions differ from what the docs said.** The init events of the 12 transcripts report Claude Code 2.1.308 (2 sessions)
   and 2.1.309 (10 sessions); `docs/VERIFIED.md` records 2.1.303 from the setup check on 2026-10-19. The sessions also loaded the
   author's user-level hooks (every transcript has `hook_started` events), which the new runner switches off with `--setting-sources project`.
5. **The first attempt of step 2 crashed in the recorder** (`run.log` lines 4 to 17, `AttributeError: 'str' object has no attribute 'get'`).
   The event that caused it is a `system` / `permission_denied` event whose `message` is a plain string. `tests/test_neuron_asks.py` now
   replays a real one (`tests/fixtures/permission_denied_event.json`).

## Files

| File | What |
|---|---|
| `asks.jsonl` | Every recorded Neuron ask (36), one per line; `asks.jsonl:N` means line N |
| `explores.jsonl` | Every recorded `explore` call (9: step 2 once, step 4 once, step 5 once, step 8 five times, step 9 once) |
| `transcripts/` | The 12 role session transcripts (stream-json), redacted |
| `ingest-times.jsonl` | Ingest waits |
| `closeout-result.json` | The scoreboard |
| `curation-queue-team.json` | Summary of the Curation review queue after step 8 |
| `screenshots/vault-list.png` | The vault list in the web UI |
| `run.log` | The runner's output, including the step 2 crash |
| `pilot-builder-edits.patch` | Builder edits, `patch -p1` from the repository root onto `app/` |
| `pilot-specs/` | The three specs the Planner wrote |
