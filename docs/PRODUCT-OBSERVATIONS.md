# Okto Neuron product observations

Points about Okto Neuron 0.3.1 that came out of the demo. They are kept apart from the demo's own faults (prompt and
allow-list problems), which are in README.md and `docs/VERIFIED.md`.

**What "evidence" means here.** Items 1 and 2 were reported by the repository's author after hand experiments recorded in
`docs/VERIFIED.md`. They were **not reproduced** by the review of this repository, and not reproduced again for this file.
Items 3 to 5 were first computed from the recorded pilot files in `demo-state/` (recounts of recorded data). Items 3, 4 and 8
were then re-measured live on 2026-10-29 in the 5 Neuron-arm runs under `runs/neuron/` (each item says what was measured and
how many runs). Items 6 and 7 were checked against the public sources of okto-neuron 0.3.1 on 2026-10-30, and the paths and flags
they describe were used successfully in the live runs. Items 9 to 11 were observed in the live runs. None of this has been
reported to Okto Labs yet; the evidence below is what a report would attach.

Every item is a product observation. The demo does not work around any of them silently.

## 1. The `gemini` and `anthropic` presets used a base URL that failed verification

- Reported: with provider `gemini`, onboarding failed with `litellm.NotFoundError: GeminiException`; a base of
  `https://generativelanguage.googleapis.com/v1beta` worked. With provider `anthropic`, the preset base
  `https://api.anthropic.com/v1` failed with `NotFound` ("litellm adds `/v1/messages` itself"); `--api-base https://api.anthropic.com`
  fixed it.
- Evidence: `docs/VERIFIED.md`, sections "Gemini onboarding" and "Anthropic setup and the recorded run".
- Status: reported by the repository, not reproduced. The live runs used the documented workaround (`--api-base https://api.anthropic.com`, `DEMO_LLM_API_BASE`) in all 5 Neuron-arm runs and the negative test, and onboarding verified; the failing default (no `--api-base`) was not run again.

## 2. The `openrouter` route wrote a litellm banner to stdout

- Reported: about half of the daemon's model calls failed with `cancellable LiteLLM helper returned invalid protocol output`,
  which Neuron marks non-retryable. The author reproduced the cause by running the helper by hand: valid JSON followed by
  litellm's `Provider List` banner on stdout. The same call with provider `openai` and the OpenRouter base URL returned clean JSON
  in 6 of 6 hand-run calls.
- Evidence: `docs/VERIFIED.md`, section "OpenRouter attempt".
- Status: reported by the repository, not reproduced.

## 3. After a note changed, `ask` returned anchors into an earlier version of the note

- Recorded: 125 of 763 citations failed the record-time hash check, every one with "byte range is past the end of the file" or
  "hash mismatch". No other kind of citation failure occurred. By note: `specs/feature-1-comment-editing.md` 104,
  `policy-error-response.md` 16, `specs/feature-2-article-limit.md` 5. This confirms the sums in `docs/VERIFIED.md` (104 + 5 + 16).
- Evidence: `demo-state/closeout-result.json` keys `stale_anchor_failures`, `stale_anchor_failures_by_note`,
  `stale_anchor_asks` (the asks by their number in `demo-state/asks.jsonl`), recomputed by `scripts/closeout.py --amend`.
- Two readings, kept separate. Demo fault: the pilot's Planner wrote each spec twice, so the specs changed. Product behaviour:
  after a note changed, answers still pointed into the old bytes. `policy-error-response.md` changed once, by the Maintainer's
  edit at step 7, with no Planner involved: its 16 stale anchors are the product reading on its own. `policy-edit-window.md`
  also changed at step 4 and has no stale anchor at all.
- **Re-measured live (5 runs, 2026-10-29):** 151 of 3,479 citations failed the record-time hash check (4.3%), every one a stale anchor ("byte range is past the end of the file" or "hash mismatch"); 0 failed in any other way. By note: `policy-error-response.md` 87 (all 5 runs: 10, 8, 34, 16, 19) and `policy-edit-window.md` 64 (2 runs only: 41 in run-03, 23 in run-04). No Planner spec was in the watched folder this time, so the demo fault of the pilot is gone and these are the product reading on its own: the two notes the Maintainer edited kept being cited by their old byte ranges. Evidence: `runs/neuron/run-0N/closeout-result.json` keys `stale_anchor_failures_by_note` and `stale_anchor_asks`. The two runs with stale edit-window anchors are the two whose `explore` right after the edit still returned the replaced value (item 4).
- Status: recounted from recorded pilot asks (one run) and re-measured in 5 live runs; not yet reported to Okto Labs.

## 4. After a rule change, `ask` answers gave no supersession signal for the edit window

- Recorded: five answers after the Maintainer's edit still said 15 minutes (step 4 Reviewer twice, step 5 Builder once, step 5
  Reviewer twice), by text match. No answer named 15 minutes as replaced.
- Evidence: `demo-state/closeout-result.json` key `stale_rule_answers_after_replacement`; `demo-state/asks.jsonl` lines 10, 12, 14, 16 and 17 (the five answers); line 15 is the Builder's leading follow-up question ("Which value is current, 15 or 30 minutes?"), which got an answer that listed both values and said that no Maintainer change was recorded.
- Not the whole story, from the same files: Neuron's `explore` results from step 8 on contain a claim with the predicate
  `replaces` for the error response rule (`demo-state/explores.jsonl`, lines 4, 5, 6, 8 and 9), and the explores for the edit
  window (lines 2 and 3) do not. The note text itself says "This replaces the older errors-by-field body", so that claim may come
  from the sentence and not from an automatic supersession edge. The repository cannot tell.
- The pilot's cause is confounded: the Planner's spec had copied the value 15, and that spec was cited. The new harness removes the
  copy (specs carry no values) and probes Neuron's state right after each edit (`scripts/state_probe.py`), so the next run can
  separate the two.
- **Re-measured live (5 runs, 2026-10-29), by `scripts/state_probe.py`:** right after each edit was ingested (the runner waits until the daemon has queued the file and its queue is idle), a neutral `ask` gave the new value in 10 of 10 probes (5 edit window, 5 error response) and the replaced value in 0 of 10. The word "supersed" appeared in none of the 10 `ask` results and 10 `explore` results. The `explore` result still contained the replaced edit window in 2 of 5 runs (run-03, run-04) and the replaced error shape in 0 of 5. Raw results: `runs/neuron/run-0N/probes/`. So the pilot's stale answers did not recur once the roles were isolated and specs carried no values; whether the new value won through supersession or through ranking cannot be told, because no result names a supersession.
- Status: recounted from recorded pilot files (one run) and re-measured in 5 live runs. The probe's matches are text matches on the raw results, kept next to them.

## 5. The Curation queue held no conflict item for the stale runbook

- Recorded: after step 8 the queue held 81 items: 69 node candidates (`low_confidence`), 8 relation items (`queue_predicate`) and 4
  relation items (`queue_grounding`). The one item sourced from `ops-runbook.md` is a node candidate titled "Ops runbook". None is a
  conflict between the runbook and the new rule. The web UI screenshot (`docs/images/neuron-curation-team.png`) shows the same 81 under
  "Node candidates" and "nothing waiting" for predicate folds and entity merges; the saved summary classifies 12 of the 81 as relation items.
- Evidence: `demo-state/curation-queue-team.json`, `docs/images/neuron-curation-team.png`.
- Status: recorded once in the pilot. Not re-measured: the live runs did not save the Curation queue.

## 6. The daemon's token path is not in the public README

- Checked: the README says only that MCP "requires the daemon bearer credential". The path is defined in the public source and in
  the installer: `server/runtime.py` (`auth_token_path` returns `app_home() / f"daemon-{rest_port}.token"`) and `install.sh`
  (`DAEMON_TOKEN_FILE="${HOME_ROOT}/daemon-7777.token"`). So the path the demo uses is correct for 0.3.1, and undocumented in the README.
- Status: checked against public sources on 2026-10-30. The path `<home>/.okto-neuron/daemon-<rest port>.token` was present and accepted by the MCP endpoint in all 5 live runs and the negative test (6 daemons on ports 17911 to 17915 and 17921).

## 7. The `--api-key` flag of `onboard` is not in the public README

- Checked: `onboard` has `--api-key` (help: "API key to save into ~/.okto-neuron/env. Prefer the interactive prompt.") and
  `--api-key-env`; with `--non-interactive` and no `--api-key` it reads the variable named by `--api-key-env`. Neither flag is in the README.
  The demo now uses the environment variable path (`scripts/setup_vaults.sh`).
- Status: checked against public sources on 2026-10-30. `onboard --non-interactive --reconfigure --vault <name> --provider anthropic --model claude-haiku-5-5 --api-base https://api.anthropic.com --api-key-env OKTO_NEURON_ANTHROPIC_API_KEY --allow-remote-llm --yes` worked live in `scripts/setup_vaults.sh` with the key only in the environment. `onboard` then saves the key in plain text in `<home>/.okto-neuron/env` of the isolated home (its output prints that path), which is why a run's home must be deleted afterwards.

## 8. A `provider_error` ask returned empty text and 20 sources, and no `finish_reason`: this is documented behaviour, not a defect

- Recorded: `demo-state/asks.jsonl` line 36 (status `degraded`, `synthesis_status` `provider_error`, `text` empty, 20 sources, no
  `finish_reason`).
- The README says `provider_error` means `text: ""` "was unreachable, not that the graph has no answer", that the citations are the
  retrieval hits, and that `finish_reason` is "surfaced as-is" from the provider. An answer with no provider reply has none. So this is
  the documented contract. The demo's own change is in how it counts: a source list with no answer is no longer counted as "returned
  sources" (`questions_with_sources_and_answer`), and the missing `finish_reason` is reported on its own row.
- **Re-measured live (5 runs, 2026-10-29):** the scripted step 9 outage (daemon restarted with an invalid key, restored afterwards) produced exactly one `ask` per run with `status: degraded`, `synthesis_status: provider_error`, empty text, 20 sources and no `finish_reason`, in 5 of 5 runs. No Reviewer claimed the notes were empty; each said the model was unreachable and went on to `explore` (which makes no model call). The daemon's own log for each run shows 2 failed model calls, both `AuthenticationError`, and no other failure in 300 to 338 successful calls.
- Status: recorded in the pilot and re-measured in 5 live runs.

## 9. A freshly edited note is not visible to `okto-neuron status` for tens of seconds

- Observed: right after a note in a watched folder was changed, `okto-neuron status` still printed `Ingest: idle (22/22 terminal, 0 processing, 0 queued)`. The folder watcher polls on an interval and queues a file once it has been quiet for a few seconds: the daemon log shows `folder-watch: queuing policy-error-response.md (settled after 5.1s quiet ...)` about 9 seconds after the copy, while the first `idle` was seen 8.4 seconds after it. A script that waits for `idle` therefore moves on before the edit is ingested: in the first live smoke run the state probe after step 7 ran before the edit was ingested and reported the replaced error shape as current.
- What the demo does about it: `scripts/wait_ingest.py --after-total N --min-new K` reads the ingest total (`(terminal/total terminal)`) before the edit and does not accept `idle` until the total has grown by the number of changed files, then needs two idle samples in a row. With that, the step 4 edit took 75 to 87 s to ingest and the step 7 edit 136 to 170 s in the 5 runs (upper bounds, polled every 5 s).
- Whether a documented "ingest finished" signal exists that would make this unnecessary was not found in the README; `status` is what the demo could read.
- Status: observed live on 6 daemons.

## 10. Ingest of the 16 starting notes took 640 to 720 seconds and about 310 model calls per run

- Recorded: `ingest-times.jsonl` of each Neuron-arm run: initial notes 712.7, 639.1, 721.2, 690.7 and 664.4 s with five daemons ingesting side by side (one earlier single-daemon smoke run: 512.6 s). Each run's daemon made 300 to 338 successful model calls with 0.93 to 1.07 million prompt tokens and 0.088 to 0.102 million completion tokens on `claude-haiku-5-5`, counted from the daemon's own log (`daemon-usage.json`, `scripts/daemon_usage.py`). The whole Neuron-arm run took 1,711 to 1,964 s against 420 to 563 s for the arms without Neuron.
- Status: recorded in 5 runs.

## 11. Isolated daemons with separate homes and ports worked side by side

- Observed: 6 daemons (separate `HOME`, `--port`, `--mcp-port`) ran at the same time on one machine without interfering, were restarted by the script for the step 9 outage, and were stopped with `okto-neuron stop`. Not a defect; recorded because the isolated-daemon design (`docs/NEURON-USAGE.md`) had not been run before.
- Status: observed live.

## Found while checking the install path

- The installer at the `v0.3.1` tag still bakes the 0.3.0 wheel and version as its defaults (`DEFAULT_WHEEL_URL`, `EXPECTED_VERSION`),
  so `.../v0.3.1/install.sh` is not by itself a pin to 0.3.1. The README's `main` one-liner moves. The demo installs the release wheel
  and checks its SHA-256 (`scripts/install_neuron.sh`, `pins.json`).
- The README lists a PyPI install "(0.3.0 and later)". The 0.3.1 release notes say "Not on PyPI yet". The demo does not rely on PyPI.
