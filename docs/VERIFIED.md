# VERIFIED

Only things that actually happened on the author's machine are recorded here. The sections are dated history, in the order things happened: setup (2026-10-19 to 2026-10-22), provider attempts, the pilot run (2026-10-23), and the live study of 2026-10-29 ("Live study" below, which is the first time the isolated design, the arms, the metric and the checkers were run). Between the pilot and the live study the repository was changed (isolation, arms, metric, checkers) and checked only offline. Where a later check found that an earlier statement was wrong, the correction is stated in the section it concerns.

## Environment

| Item | Value |
|---|---|
| Date | 2026-10-19 |
| OS | macOS 26.3 (build 25D125), arm64 (the plan says Linux only, so this run is off-plan) |
| git | 2.53.0 |
| Docker | 29.7.2 (daemon was stopped, started with `open -a Docker`) |
| Node / npm | v26.8.1 / 11.19.0 |
| Python | 3.9.6 (system) |
| claude CLI | 2.1.303 on 2026-10-19 (the setup check). The pilot's own session init events report 2.1.308 (2 sessions) and 2.1.309 (10 sessions), so the pilot did not run on 2.1.303 |
| Neuron | okto-neuron 0.3.1 (`okto-neuron --version`) |

## Commands run

1. `git clone` of `gothinkster/node-express-realworld-example-app` into `app/` (upstream commit 30b68e1e881462b2f4164ea09ab4c4f5699c7b0b, 2024-01-04), then `.git` removed so `app/` is tracked by this repo.
2. `docker compose up -d` (Postgres 15 on host port 5433). Container reached `healthy`.
3. `cd app && npm install`: 731 packages added. 51 audit findings reported, not fixed. npm 11 skipped install scripts (prisma, swc, esbuild, nx), so `npx prisma generate` was run by hand.
4. `DATABASE_URL=postgresql://realworld:realworld@localhost:5433/realworld npx prisma migrate deploy`: all 4 migrations applied.
5. `npx nx test api --skip-nx-cache`: **1 suite failed, 4 passed. 14 tests passed, 1 todo.**
   - Failing suite: `src/tests/services/auth.service.test.ts`.
   - Error: `TypeError: Cannot read properties of undefined (reading 'prototype')` at `node_modules/buffer-equal-constant-time/index.js:37:35`, reached through `jsonwebtoken`.
   - Not fixed. See the Node 22 rerun below.
6. `OKTO_NEURON_NO_OPEN=1 curl -fsSL https://raw.githubusercontent.com/OktoLabsAI/okto-neuron/main/install.sh | bash -s -- --no-onboard` (README Install command, with the two documented options). Took about 1m44s. Result: okto-neuron 0.3.1, daemon started (UI :7777, MCP :8201), `okto-neuron` MCP server registered with Claude Code at user scope.

## Node 22 rerun (app tests)

- Installed nvm v0.40.3 with `PROFILE=/dev/null` (no shell profile edits). `nvm install 22` gave v22.23.3 (npm 10.9.9). Node 26.8.1 is still the default.
- Under Node 22: `rm -rf node_modules && npm ci && npx prisma generate`, then `npx nx test api --skip-nx-cache`.
- The Node 26 load error (`buffer-equal-constant-time`) is gone, so the auth suite now runs. It still fails, so no `.nvmrc` was added.
- Results, all with `DATABASE_URL` set to the compose Postgres: first run 4 failed, 22 passed, 1 todo; two later runs 5 failed, 21 passed, 1 todo. With `DATABASE_URL` unset: 7 failed, 19 passed, 1 todo. The count changed between runs and was not explained.
- Failing tests are all in `src/tests/services/auth.service.test.ts` (createUser, login, getCurrentUser, updateUser). One failure shows `[Error: [object Object]]` rejected from `createUser`; earlier runs showed `PrismaClientInitializationError: Validation Error Count: 1`. Cause not found. In that test file `auth.service` is imported before `prisma-mock`, which may matter, but this was not confirmed.
- The other 4 suites pass.

## Tooling checks

- `claude --help` (2.1.303) lists `--mcp-config <configs...>` and `--strict-mcp-config` ("Only use MCP servers from --mcp-config"). Each role run can use these so it does not see the user-scope `okto-neuron` entry the installer added.
- Python: macOS system Python is 3.9.6. Scripts are written for 3.9.

## Gemini onboarding (2026-10-22)

- First attempts failed with `litellm.NotFoundError: GeminiException`. The error label `.../v1beta/v1/chat/completions` is built by Neuron's verify message code (`resolve_openai_base`) and is not the URL litellm requests. For provider `gemini`, litellm posts to `{api_base}/models/<model>:generateContent`.
- Local probe (fake key, loopback listener only): base `.../v1beta/openai/` gave `POST /v1beta/openai//models/<model>:generateContent`; base `.../v1beta` gave `POST /v1beta/models/<model>:generateContent`; provider `openai` with the `.../openai` base gave `POST /v1beta/openai/v1/chat/completions`.
- Direct calls to Google with the Maintainer's key, 2026-10-22: `gemini-3.5-flash` returned 200 on both the native endpoint (`x-goog-api-key` header) and the OpenAI-compatible endpoint. `gemini-2.5-flash` returned 404 ("no longer available to new users"). `gemini-3.8-flash` timed out after 25 s on one call and returned 503 on an earlier native call; `gemini-flash-latest` returned 503 ("high demand"). Native calls with a Bearer header returned 401.
- Working onboarding command, run non-interactively: `okto-neuron onboard --non-interactive --vault <name> --provider gemini --api-base https://generativelanguage.googleapis.com/v1beta --model gemini-3.5-flash --api-key-env OKTO_NEURON_GEMINI_API_KEY --allow-remote-llm --yes` (the key was given once with `--api-key` and is stored by Neuron in `~/.okto-neuron/env`). Run for vaults `team` and `reviewer-private`; both reported "onboarding complete", created: yes.
- The verify step printed `litellm completion TRUNCATED (finish_reason=length) ... max_tokens=16` for both vaults. The verify still passed. Whether the model's thinking tokens truncate extraction output is not yet known.
- A vault named `<other-vault>` already existed before this run and was not touched.

## Watched folders, ingest and ask (2026-10-22, times in UTC)

Commands (the two `add` commands were run by the Maintainer in this session, because Claude Code's permission check denied them when the assistant tried):

1. `okto-neuron watch-folder add <REPO>/vault --vault <HOME>/.okto-neuron/vaults/team` (output: `1 file(s) queued, 1 non-text skipped`; the skipped file is `.gitkeep`)
2. `okto-neuron watch-folder add <REPO>/vault-private --vault <HOME>/.okto-neuron/vaults/reviewer-private` (output: `1 file(s) queued`)

**Can a watched folder be tied to a specific vault? Yes.** `watch-folder add` takes `--vault PATH` (a vault path, not a name). `watch-folder list --vault <path>` showed only that vault's own root for each of the two vaults. No other way to load the private note was needed.

**First ingest failed.** The daemon had been started before `~/.okto-neuron/env` existed, so it logged `Missing Gemini API key. Set the GEMINI_API_KEY or GOOGLE_API_KEY environment variable.` for both notes and `status` showed `queue_errors: 4`. After `okto-neuron stop` and `okto-neuron serve --daemon --no-open` the daemon read the key. The failed items were not retried by themselves, so each note got one extra line appended (which the folder watcher treats as an edit).

**Second ingest, after the restart:**

| Note | Vault | Enqueued | Extract, embed, commit done | Status `idle` seen by |
|---|---|---|---|---|
| setup-test.md | team | 11:37:59.8 | about 19 s after enqueue (commit stage logged at 11:38:19.3) | 11:38:54 |
| setup-test-private.md | reviewer-private | 11:37:59.8 | about 19 s after enqueue (commit stage logged at 11:38:18.7) | 11:38:54 |

- Both notes were ingested at the same time, so the times overlap and are not separate per-note costs.
- The log has no explicit "ingest finished" line. The 11:38:54 figure is when a poll first saw the queue idle, so true completion is somewhere between about 11:38:20 and 11:38:54. Treat it as an upper bound of roughly 55 s.
- After the commit stage, the curator and relation curator ran into Gemini `429 RESOURCE_EXHAUSTED` errors (message: `generate_content_free_tier_requests, limit: 5`, retry in about 39 s) from 11:38:21 onward. `status` still showed `queue_errors: 4` after the second ingest, the same 4 as the first failed round, so the 2 new items were not added to the error count. Both notes then answered correctly. Whether curation fully completed despite the 429s was not checked.
- **The Gemini key in use is on a free tier with a limit of 5 requests per minute.** The README measured 163 to 177 completion calls for one 3-block note, so a 14-note run on this key will be rate limited. This needs a paid-tier key or another endpoint before Phase A.

**Asks, all against `gemini-3.5-flash`:**

- `okto-neuron ask "How long is the comment edit window?" --vault .../team --format json`: `status: ok`, `synthesis_status: ok`, `finish_reason: stop`, text `The comment edit window is 15 minutes.`
- Citation check by hand: the cited source is a copy Neuron keeps at `<vault>/.marginalia/sources/14bfef7e474715c5/setup-test.md` (177 bytes, the same size as `vault/setup-test.md`). `sha256(raw[0:177])` equals the reported `content_hash` `sha256:5d698c55...a9f0f`. The hash check passes.
- `ask` against `reviewer-private` for the retry helper finding returned the private note's content (`status: ok`).
- The same question against `team` returned `there is no information about a retry helper`, and its hits were only `setup-test.md`. The private note did not appear in the team vault.
- `include_sources` is an MCP `ask` parameter. The CLI `ask` has no such option and the REST `/api/v1/ask` handler does not read it. It was called through `claude -p ... --allowedTools mcp__okto-neuron__ask` with `{"question": "How long is the comment edit window?", "vault": "team", "include_sources": true}`.
  - First call, 11:39:49: `status: degraded`, `synthesis_status: provider_error`, `text: ""`, `retrieval.synthesis_retries[0].category: rate_limited`, and the `sources` list was still returned. This is a real provider_error response caused by the free-tier limit, not a stopped endpoint.
  - Second call, 11:40:21: `status: ok`, `synthesis_status: ok`, `finish_reason: stop`, text `The comment edit window is 15 minutes.`, two sources, both with `byte_start 0`, `byte_end 177`, the content hash above and `path: .marginalia/sources/14bfef7e474715c5/setup-test.md`. No `vault_override_ignored` field was present.
- The `sources[].path` is vault-relative, but it points to Neuron's internal copy under `.marginalia/sources/`, not to `vault/setup-test.md`. The citation verifier must read that copy from `~/.okto-neuron/vaults/<name>/`, or compare against the repo file after checking the sizes match. One source had an empty `block_id` (a Document node).

## Repo build checks (2026-10-22)

- Python used: 3.9.6 (macOS system Python). `python3 -m compileall -q scripts run_demo.py tests` passes.
- `python3 -m unittest discover -s tests`: 29 tests ran on 2026-10-22, all passed, 1 skipped (`test_recorded_asks`, because `demo-state/asks.jsonl` did not exist yet). The suite has grown since; run the command for the current count.
- `python3 run_demo.py --dry-run` prints all ten steps without Neuron and without reading the token file. `--steps 4 7 9` and `--start 9` select the right steps.
- The tests found one real bug in `scripts/closeout.py` while it was being written: the private note's heading ran into its first sentence, so no leak marker would ever have matched. Fixed, and covered by `test_private_note_in_team_answer_is_a_leak`.
- Not run end to end: the `claude -p` role runs, `scripts/setup_vaults.sh`, `scripts/wait_ingest.py` and `scripts/maintainer_edit.py` against a live Neuron. Only the dry run and the unit tests have been executed.
- `claude -p` with `--allowedTools mcp__okto-neuron__ask` did return the raw MCP `ask` result in stream-json (used on 2026-10-22 for the `include_sources` check), which is what `scripts/neuron_asks.py` reads. The `Edit(path/**)` permission patterns in `scripts/steps.py` have not been tried.

## Unplanned ingest of the 14 notes on the free-tier key (2026-10-22)

The folder watcher registered during the setup check was still active, so writing the 14 notes into `vault/` queued them for ingest on the rate-limited key.

- Log window starting 12:11:04Z: 57 `RateLimitError` (429) warnings, 13 `LLM extraction failed` warnings, and only 1 `remember stage=committing` line.
- At 12:17:48Z `okto-neuron status` showed `Ingest: idle (20/20 terminal, 0 processing, 0 queued)` and `queue_errors: 17`.
- So most of the 14 notes did not extract cleanly. The `team` vault is not in a usable state for the demo. It also still holds the earlier setup test note, which was since removed from `vault/`.
- This needs a re-ingest on a key or endpoint without a 5 requests per minute limit. The Neuron README documents `okto-neuron init ./vault --wipe` for resetting a vault. It was not run.

## OpenRouter attempt (2026-10-23, times in UTC)

- Direct call to OpenRouter with the Maintainer's key and `nvidia/nemotron-3-ultra-550b-a55b:free`: HTTP 200 in about 3 s, `finish_reason: stop`. The model is a reasoning model (the response carries a `reasoning` field and `reasoning_tokens`).
- Onboarded both vaults with `okto-neuron onboard --non-interactive --reconfigure --vault <name> --provider openrouter --model nvidia/nemotron-3-ultra-550b-a55b:free --api-key-env OKTO_NEURON_OPENROUTER_API_KEY --api-key <key> --allow-remote-llm --yes`. Both reported "onboarding complete". Key stored in `~/.okto-neuron/env`.
- Stopped the daemon (`okto-neuron stop` printed `PID identity mismatch for 61808; refusing to signal an unrelated or unverifiable process`), wiped both vaults with `okto-neuron init ~/.okto-neuron/vaults/<name> --wipe` (printed `wiped vault at ...` for each), and started a new daemon with `okto-neuron serve --daemon --no-open` (pid 66968). The saved `folder_watch.roots` survived the wipe, and the daemon started ingesting `vault/` on its own at 04:48:53.
- Removed the old `vault-private/setup-test-private.md` so the private vault starts empty.
- A question to the `team` vault through the daemon at about 04:59 returned `status: ok`, `synthesis_status: ok`, `finish_reason: stop`. The answer said the excerpts did not cover the edit window, which is expected because that note had not been ingested yet.
- **Ingest speed:** about 3 of 16 queue items finished in the first 11 minutes, roughly 4 minutes per note.
- **Bug found: `invalid protocol output`.** About half of the daemon's LLM calls (19 failed against 16 succeeded in the first 11 minutes) failed with `cancellable LiteLLM helper returned invalid protocol output`, which Neuron marks non-retryable, so the work is lost. Cause, reproduced by running `python -m okto_neuron.llm._litellm_worker` by hand: the model call succeeds and the worker prints valid JSON (`"ok":true`), then litellm prints its red `Provider List: https://docs.litellm.ai/docs/providers` banner to stdout after it, so the parent cannot parse the output. litellm prints that banner when it cannot work out the provider for the model name (`litellm/litellm_core_utils/get_llm_provider_logic.py`). 5 of 6 hand-run calls with provider `openrouter` were invalid.
- **Workaround that worked:** the same call with model `openai/nvidia/nemotron-3-ultra-550b-a55b:free` and `api_base https://openrouter.ai/api/v1` (the Neuron README says custom OpenAI-compatible endpoints use `provider=openai`) returned clean JSON in 6 of 6 hand-run calls. The daemon config has not been switched to this yet.
- **Blocker:** during those 6 hand-run calls OpenRouter started answering `Rate limit exceeded: free-models-per-day. Add 10 credits to unlock 1000 free model requests per day` (4 of 6). So a free-tier OpenRouter key allows only a small number of free-model requests per day, far fewer than a 14-note ingest needs (the Neuron README measured 163 to 177 calls for one 3-block note). Ingest and every ask now fail with 429 until the daily limit resets or credits are added.
- The state of the `team` vault after this is partial. Re-ingest is needed once calls work again.

## Anthropic setup and the recorded run (2026-10-23, times in UTC)

Machine: macOS 26.3 on Apple silicon (arm64), Python 3.9.6, Neuron `okto-neuron --version` 0.3.1 (recorded here only), claude CLI 2.1.303.

**Model setup that worked.**
- An Anthropic user-level key (`sk-ant-usr-...`) that is not scoped to a workspace is rejected with a 400 asking for an `anthropic-workspace-id` header, and Neuron's docs list `extra_headers` among parameters it refuses to let users set. A key created scoped to a workspace worked with no header.
- `okto-neuron onboard --non-interactive --reconfigure --vault <name> --provider anthropic --model claude-haiku-5-5 --api-key-env OKTO_NEURON_ANTHROPIC_API_KEY --api-key <key> --allow-remote-llm --yes` failed verify with `NotFound` on the preset base `https://api.anthropic.com/v1` (litellm adds `/v1/messages` itself). Adding `--api-base https://api.anthropic.com` fixed it. Same kind of base URL fault as the Gemini preset.
- Both vaults were then wiped (`okto-neuron init <vault path> --wipe`, daemon stopped first) and the daemon restarted with `okto-neuron serve --daemon --no-open`.
- **Step 1 (setup) was done by hand with these commands.** `scripts/setup_vaults.sh` has not been run. It needs `DEMO_LLM_API_BASE=https://api.anthropic.com` for Anthropic.
- Ingest of the 14 notes: daemon start 05:13:25, status first seen `idle (14/14 terminal)` at 05:24:01. Upper bound 636 s. 151 successful model calls, 0 failed, no `queue_errors` warning.
- The OpenRouter route was tried first and abandoned. See the OpenRouter section above for the stdout banner bug and the free-models-per-day limit.

**The run.** `python3 run_demo.py --steps 2 3 4 5 6 7 8 --yes`, then `--steps 9 --yes`, then `python3 scripts/closeout.py --recheck`. Every role session ran as `claude -p` with `--model claude-haiku-5-5`, `--strict-mcp-config` and a per-role MCP config. The planner and builder connected with `?vault=team`. Total wall time for steps 2 to 8 was about 30 minutes. This is a single run, not a repeat.

Closeout numbers, from `demo-state/closeout-result.json` (all computed from `demo-state/asks.jsonl`):

| Measure | Value |
|---|---|
| Asks recorded | 36, all 36 returned sources |
| `synthesis_status` | ok 35, provider_error 1, all other values 0 |
| `finish_reason` other than `stop` | 0 (1 ask had none: the provider_error) |
| `vault_override_ignored` pointing at a different vault | 0 |
| `vault_override_ignored` naming the vault the connection was already pinned to | 22 (planner and builder passed `vault: "team"` on a `?vault=team` connection) |
| Asks to any vault other than `team` and `reviewer-private` | 0 |
| Private notes in `team` answers | 0 |
| Citations checked / passed at record time | 763 / 638 |
| Citations passed on recheck at close-out | 616 |
| Answers stating the replaced edit window (15 minutes) after the Maintainer's edit, text match only | 5 (step 4 reviewer twice, step 5 builder once, step 5 reviewer twice) |
| Answers stating the replaced error rule after step 7 | 0 |

**Failed citations (125 of 763 at record time), all one cause.** Each fails with "byte range is past the end of the file" or "hash mismatch" against a note that was written or edited more than once: `specs/feature-1-comment-editing.md` 104 of 168 checks, `specs/feature-2-article-limit.md` 5 of 7, `policy-error-response.md` 16 of 48. Neuron kept answering with anchors into an earlier version of the note after the file changed. The Planner wrote each spec twice (1912 then 1581 characters for feature 1, 1584 then 1060 for feature 2), because the role file said "under 1500 characters" and its first draft was longer. That was our prompt fault, fixed afterwards in `agents/planner/CLAUDE.md` (write once, under 1300 characters) but not re-run, by decision of the Maintainer.

**What Neuron did with the edits (what actually happened).**
- Step 4: after the edit window note was changed to 30 minutes, the fresh Reviewer was told 15 minutes (the spec still said 15, and a stale copy was cited), its `explore` found no replaced value, and it passed the code while noting a conflict. The step 5 Builder's second ask returned 30, and it changed the code to 30. In its words, Neuron did not record the Maintainer's change or name the replaced value. So in this run, supersession did not show up as a "15 marked replaced" answer.
- Our spec copied the rule value (15) into a second note. That is our design fault, fixed in the role file and the prompts after the run (specs now name the rule and its source and do not copy the value).
- Step 7: after the error rule was replaced and `ops-runbook.md` added, the Curation review queue for `team` held 81 items (69 low-confidence node candidates, 8 `queue_predicate` and 4 `queue_grounding` relations). None was a conflict between the runbook and the new rule. Saved summary: `demo-state/curation-queue-team.json`. The step 8 Planner and Reviewer still caught it: the Planner noted that `policy-error-response.md` says new errors use `{"error":{...}}` and `ops-runbook.md` says the older shape, and the Reviewer flagged the stale runbook and an old-shape 422 in `editComment`.
- Step 9: with the model made unreachable (see below), the Reviewer's ask returned `status: degraded`, `synthesis_status: provider_error`, empty text, and 20 sources. The agent said it would run `explore`, and one explore call was recorded. Its follow-up did not claim nothing was found.

**How step 9's outage was made.** Not by stopping an endpoint. The daemon was restarted with `OKTO_NEURON_ANTHROPIC_API_KEY=sk-ant-invalid-demo-outage` in its environment, which overrode the stored key, so the provider returned an authentication error. The daemon was then restarted again with no override, and an ask returned `ok`.

**Agent tool blocks.** Role sessions were denied some commands they tried: `git -C <path> diff`, `git status`, `git log`, `git show`, `ls`, `wc`, and `cd app && ...` compounds. The Step 5 Builder reported its test runs were blocked, so no test result was reported for the step 5 fix. Builders in steps 3, 6 and 8 did run `npx nx test api`. The allow-list in `scripts/steps.py` was widened afterwards, and was not re-run. Plain `git diff` and `npx nx test api` with the runner's exact command line were confirmed to run in a separate test.

**Screenshots.** Only `demo-state/screenshots/vault-list.png` (the vault list in the web UI) was taken. The UI selects a vault inside the page, so a headless screenshot could not reach the Curation view or a source line. That was the state when this paragraph was written. Afterwards `docs/images/neuron-curation-team.png` and `docs/images/neuron-query-sources.png` were captured by hand in the web UI from the pilot's `team` vault (the Curation view with 81 items, and a query answered with a source); they first appear in this repository in the same commit as this file, 2026-10-23 06:36 UTC (`a316a71`). The exact capture time is not recorded, so no date is claimed for them. Each of the three screenshots had the author's home folder in its pixels (and `vault-list.png` a personal vault name); those text regions were redrawn with placeholders.

**Other.**
- An ask result's `sources[].path` points to Neuron's own copy under `.marginalia/sources/<id>/`, not at `vault/`.
- `<other-vault>`, the Maintainer's personal vault, is visible in `list_vaults` to any role. The agent rules say not to use it, and the close-out counts any ask to another vault (0 here).
- The app's own test suite is unchanged by the demo and its `auth.service` tests were not re-run after the builders' edits.

## Live study (2026-10-29, times in UTC)

Machine: macOS 26.3 on Apple silicon (Darwin 25.3.0 arm64), Python 3.9.6 (system), `uv` 0.12.7, Claude Code 2.1.312 (the pin in `pins.json` says 2.1.309; the manifests record 2.1.312), Okto Neuron 0.3.1, model `claude-haiku-5-5` over the Anthropic API for every role and for Neuron. The default Node on this machine is v26.8.1, which cannot run the outcome check (below); the study used Node v22.23.4 (the npm package `node@22` installed into a temporary folder), npm 11.19.0. Everything ran in temporary folders: a separate `HOME` and `CLAUDE_CONFIG_DIR` for each process, its own copy of the repository, its own isolated Neuron home and ports. The user's own Neuron install, daemon (ports 7777 and 8201) and `~/.claude` were not used. The key was read from the environment only, never written to a file of this repository, and the isolated Neuron homes (which Neuron fills with the key at onboarding) were deleted after the runs.

**What ran, in order.**

1. `DEMO_NEURON_HOME=<tmp>/install bash scripts/install_neuron.sh`: 7.2 s, the SHA-256 of the pinned wheel matched, `okto-neuron 0.3.1`, installed under the temporary folder. First attempt, nothing to fix.
2. `cd app && npm ci` (network): 731 packages in 5 s. npm 11 skipped the install scripts (prisma); `prisma generate` was not run and the outcome check does not need it (the database is mocked).
3. `scripts/setup_vaults.sh` ran end to end on its first attempt in every Neuron-arm run with `DEMO_LLM_PROVIDER=anthropic`, `DEMO_LLM_API_BASE=https://api.anthropic.com`: version check, onboarding of `team` and `reviewer-private`, daemon start, both watched folders, ingest of the starting notes (512.6 s in the single-daemon smoke run, 639 to 721 s with five daemons side by side).
4. Smoke runs, one per arm (`docs/evidence/smoke-2026-10-29/`, manifests, timelines, probes and outcome files only): the Neuron arm 20:32 to 20:53, the notes and none arms about 5 minutes each. Role sessions of all smoke runs cost $0.49 by Claude Code's own `total_cost_usd` (56 sessions, from transcripts that are not kept). Two more smoke runs (notes and none) were made after the first fixes.
5. The study: `--arm none --runs 5 --keep-going`, `--arm notes --runs 5 --keep-going` and five `--arm neuron --run-id run-0N` processes side by side (REST ports 17911 to 17915, MCP ports 18511 to 18515), 20:56:31 to 21:41:17. 15 runs, 170 role sessions, all steps completed in every run; three runs recorded an isolation hard failure at run time (item 5 below) and their series went on because of `--keep-going`. Claude Code's own cost for the role sessions of the 15 runs: $1.498 in total (A 0.493, B 0.394, C 0.611, sums of the manifests). Neuron's own model calls are in tokens (`runs/neuron/run-0N/daemon-usage.json`): 4.87 million prompt and 0.468 million completion tokens in the five runs, 1,571 successful calls; dollars were not computed.
6. The negative test, `DEMO_WITH_DECOY=1 bash scripts/setup_vaults.sh` and `python3 run_demo.py --negative` on its own daemon (port 17921): `runs/negative/neg-01/`, $0.005. Result in the README ("Roles").
7. `scripts/rescore_outcomes.py` over all 15 runs: 60 trees rebuilt from the recorded diffs, 0 differ from the live result.
8. `scripts/make_label_sheet.py` for the 15 runs and `scripts/support_sample.py make` for the 5 Neuron-arm runs (10 answers each): all empty. Not filled in by anyone.
9. Checkers over the new files: `scripts/scan_rule_values.py` on prompts, agent files and fixed questions: 0 hits; on the recorded questions of each of the 5 Neuron-arm runs: 0 hits. `scripts/check_transcripts.py` on all 170 new transcripts, with the checker as it is now: 0 violations (12, 3 and 6 blocked attempts in arms A, B and C). `scripts/scan_personal.py`: clean.

**What broke, and what was changed (every iteration).**

1. *The spec rule-value scan stopped series and flagged the wrong thing.* In the first smoke runs a hard failure ended the `--runs` loop, and the scan flagged `deletedAt` in the no-memory arm (where the Planner invents the name, so it cannot have come from a rule source) and `editedAt` in arm B. Changed: `--keep-going` continues a series; the scan is now a measurement kept in `checks.spec_rule_values` of each manifest (once per spec), not a hard failure. In the study: A 2 of 5 runs, B 5 of 5, C 1 of 5 had a rule value in a spec (one B spec contained "15-minute", the replaced edit window).
2. *Every outcome was "error" on Node 26.* The outcome suite failed to load: `TypeError: Cannot read properties of undefined (reading 'prototype')` at `buffer-equal-constant-time` (`SlowBuffer`, removed in Node 25), the same error as the app's own auth test on 2026-10-19. Changed: Node 22 is required (README, `pins.json` already named it for CI); `scripts/code_outcome.py` keeps jest's message as `suite_failure`; `run_demo.py` runs the check on the untouched app before the first model call and stops the run if any outcome is "error" (baseline: accepts-inside and caps-above fail, the others pass, recorded as `code-outcome/baseline.json`).
3. *Every outcome was "error" for any Builder that added a column.* ts-jest type-checked the Builder's code against the Prisma client generated from the untouched schema (`'editedAt' does not exist in type ...`), so the suite did not run (`docs/evidence/smoke-2026-10-29/notes-smoke-02/code-outcome/step3.json`). Changed: the outcome check runs with ts-jest diagnostics off (`jest.outcome.config.js`, written into the temporary copy only). The metric scores behaviour, with the database mocked, not type correctness; a Builder whose code does not type-check is therefore not penalised.
4. *The state probe ran before the edit was ingested.* In the first smoke run `wait_ingest.py` saw `idle` 8.4 s after the step 7 edit; the folder watcher queued the files at about 9 s, so the probe asked the old graph and reported the replaced error shape as current (`docs/evidence/smoke-2026-10-29/neuron-smoke-01/probes/step7.summary.json`, `ingest-times.jsonl`). Changed: the runner reads the daemon's ingest total before each edit and `wait_ingest.py` does not accept `idle` until it has grown by the number of changed files, then needs two idle samples in a row (unit-tested; live: the step 4 edit then took 75 to 87 s, the step 7 edit 136 to 170 s). The same race existed for the wait after a Reviewer writes a private finding, and is fixed by the same change.
5. *The isolation checker produced four kinds of false positive on live transcripts.* None of them was a role reaching a note, the plan or the docs. (a) `ls app/docs` was reported as naming `docs`: a folder name now counts only where it starts a path (word start, `./`, `../`). (b) `grep -v '/node_modules/'` was reported as an absolute path outside the working directory: an absolute path whose first component is not a top-level folder of the machine reaches nothing. (c) `cd <the session's own folder>; ls` was reported because the token ended in `;`: trailing `; & | )` are stripped. (d) A `Grep` of `app/src` listed `tests/services/x.test.ts`, which looked like the harness's `tests/`: Grep and Glob result lines are resolved against the searched folder. (a) and (b) were fixed before the study and (c) and (d) after it, so the manifests of A run-04, A run-05 and B run-03 still record an isolation hard failure; the checker as it is now finds 0 violations in all 170 sessions. Each change has a test, and the pilot's transcripts still give 10 of 12 sessions with violations and 37 in all.
6. *A run would have started on the previous run's graph.* Neuron's home outlives a run. Changed: `neuron_ctl.reset_state()` stops the daemon and deletes the isolated home before each Neuron-arm setup (it refuses the real home).
7. *The manifest fingerprint of the harness differed between runs of a series.* It was taken before `reset.py` restored the notes, so runs 2 to 5 of arms A and B fingerprinted the notes the previous run had edited. Re-computing it on the launch copies after a reset gave the same hash for all of them. Changed: the runner resets first. The recorded manifests are as they were.
8. *Scoring would have rejected all 15 runs after the results were written into `docs/METRIC.md`,* because the metric fingerprint covered the whole file. Changed: the fingerprint covers the definition only (up to an `END definition` line) and `scenarios/metric-equivalents.json` lists the fingerprint under which the 15 runs were recorded, with the reason; the sections that define the metric and `scenarios/work_products.json` are byte for byte what they were (checked against the launch copy).
9. *The offline run test depended on whether `app/node_modules` existed.* It now patches the outcome check.

**The launch state.** The 15 runs ran the repository as it was on 2026-10-29 at 20:56 (commit `6b29e7f` plus uncommitted changes; `repo.dirty` is true in every manifest and `repo.harness.sha256` identifies the scripts, prompts, agent files, scenarios, starting notes, app and pins). `runs/harness-changes-after-launch.diff` is the difference to the scripts now.

**What the runs changed in what this repository claimed.** (1) The README and scripts said the outcome check, the state probe, the isolated daemon, the installer, the scripted step 9 and the negative test had not been run; they have now, and each needed the fixes above (the outcome check, the probe wait and the isolation checker would have given wrong results without them). (2) The pilot's explanation of its stale answers (the spec copy, files read from disk) fits the live runs, where no replaced value was given after an edit, but the live runs do not prove it. (3) The pilot's 16% stale anchors were 4.3% in the live runs, still not zero and still only on notes the Maintainer edited. (4) The negative test did not exercise the connection-level boundary: the Planner and the Builder declined before making a call.

**Not done.** Nobody labeled anything, so 9 of 11 products per run, the citation-support rate and the private-fact review have no human result. The integration workflow was not started on GitHub, and nothing ran on Linux or Windows. `--bare` was not used.

## Provider notes for readers who want to repeat this

Detail that used to sit in the README, kept here because it describes the author's accounts and the vendors' limits on 2026-10-22 and 2026-10-23, not this demo. Product-level readings of the first two points are in [PRODUCT-OBSERVATIONS.md](PRODUCT-OBSERVATIONS.md), items 1 and 2.

- **Free tiers were too small.** A free Gemini key allowed 5 requests per minute and a free OpenRouter key reached its daily limit within minutes, while Neuron's curation makes many model calls per note (sections "Watched folders, ingest and ask", "Unplanned ingest" and "OpenRouter attempt" above).
- **Anthropic.** A workspace-scoped key was needed, and `--api-base https://api.anthropic.com` fixed the preset's base URL (section "Anthropic setup and the recorded run").
- **OpenRouter.** With `DEMO_LLM_PROVIDER=openrouter`, litellm printed a banner after the JSON for a model name it does not recognise and broke Neuron's helper. `DEMO_LLM_PROVIDER=openai` with `DEMO_LLM_API_BASE=https://openrouter.ai/api/v1` worked in 6 of 6 hand-run calls (section "OpenRouter attempt").
- **Gemini.** A different base URL from the preset worked (section "Gemini onboarding").
- The pilot passed the key with `onboard --api-key` on the command line, which puts it in the process list. `scripts/setup_vaults.sh` now passes it through an environment variable and `--api-key-env`.

## Not yet verified

- The integration workflow `.github/workflows/integration.yml` on GitHub (never started)
- Anything on Linux or Windows
- Hand labels for the 15 runs, the citation-support samples and the private-fact review (all empty, see the "Live study" section)
- `vault_override_ignored` pointing at a different vault (never happened: the negative test's Planner and Builder declined without a call)
- Behavior with a stopped local endpoint (an invalid key was used instead)
- Claude Code `--bare` (the runner has the flag; no run used it). `--tools` and `--setting-sources project` ran in all 15 runs
- The Curation queue after the live runs (not saved)
