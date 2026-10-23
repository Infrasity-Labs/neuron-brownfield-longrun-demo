# VERIFIED

Only things that actually happened on this machine are recorded here. Draft in progress (setup steps 1 to 5).

## Environment

| Item | Value |
|---|---|
| Date | 2026-10-19 |
| OS | macOS 26.3 (build 25D125), arm64 (the plan says Linux only, so this run is off-plan) |
| git | 2.53.0 |
| Docker | 29.7.2 (daemon was stopped, started with `open -a Docker`) |
| Node / npm | v26.8.1 / 11.19.0 |
| Python | 3.9.6 (system) |
| claude CLI | 2.1.303 |
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
- A vault named `mynotes` already existed before this run and was not touched.

## Watched folders, ingest and ask (2026-10-22, times in UTC)

Commands (the two `add` commands were run by the Maintainer in this session, because Claude Code's permission check denied them when the assistant tried):

1. `okto-neuron watch-folder add /Users/apple/Infrasity/neu/vault --vault /Users/apple/.okto-neuron/vaults/team` (output: `1 file(s) queued, 1 non-text skipped`; the skipped file is `.gitkeep`)
2. `okto-neuron watch-folder add /Users/apple/Infrasity/neu/vault-private --vault /Users/apple/.okto-neuron/vaults/reviewer-private` (output: `1 file(s) queued`)

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
- `python3 -m unittest discover -s tests`: 29 tests ran, all passed, 1 skipped (`test_recorded_asks`, because `demo-state/asks.jsonl` does not exist yet).
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

**Screenshots.** Only `demo-state/screenshots/vault-list.png` (the vault list in the web UI) was taken. The UI selects a vault inside the page, so a headless screenshot could not reach the Curation view or a source line. Those two are not taken.

**Other.**
- An ask result's `sources[].path` points to Neuron's own copy under `.marginalia/sources/<id>/`, not at `vault/`.
- `mynotes`, the Maintainer's personal vault, is visible in `list_vaults` to any role. The agent rules say not to use it, and the close-out counts any ask to another vault (0 here).
- The app's own test suite is unchanged by the demo and its `auth.service` tests were not re-run after the builders' edits.

## Not yet verified

- `scripts/setup_vaults.sh` end to end
- A clean run after the Planner, spec and tool allow-list fixes
- The Curation view and a source line in screenshots
- `vault_override_ignored` pointing at a different vault (never happened)
- Behavior with a stopped local endpoint (an invalid key was used instead)
