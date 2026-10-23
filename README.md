# neuron-brownfield-longrun-demo

![Three agents. Two vaults. Every answer shows its source.](docs/images/banner.svg)

Three agents. Two vaults. Every answer shows its source.

Three features added to an existing blogging API over ten steps, by AI agents that remember nothing between sessions, with every rule they follow coming from Okto Neuron.

[About Okto Neuron](#about-okto-neuron) · [The Problem](#the-problem) · [How It Works](#how-it-works) · [Neuron in Action](#neuron-in-action) · [Architecture](#architecture) · [Repository Structure](#repository-structure) · [Workspace & Demo Data](#workspace--demo-data) · [Roles](#roles) · [Tools Used](#tools-used) · [Prerequisites](#prerequisites) · [Quickstart](#quickstart) · [Running the Target App](#running-the-target-app-app) · [The Ten Steps](#the-ten-steps) · [The Recorded Run](#the-recorded-run) · [Where to Find Artifacts](#where-to-find-artifacts) · [Known Limits](#known-limits) · [Contributing & Licensing](#contributing--licensing) · [Conclusion](#conclusion)

> **Status.** One full run of steps 2 to 9 is recorded in `demo-state/`, followed by the close-out. It is a single run with known flaws that came from this repo's own setup, listed in [The Recorded Run](#the-recorded-run). What was verified, on which machine, and the exact commands are in [docs/VERIFIED.md](docs/VERIFIED.md).

## About Okto Neuron

[Okto Neuron](https://github.com/OktoLabsAI/okto-neuron) is local-first memory for AI agents, built as a knowledge graph. You keep notes as Markdown files. Neuron splits them into blocks, uses an LLM you configure to pull out claims (one subject, predicate and object each), and answers questions from that graph through a CLI, an MCP server, a Python SDK and a web UI.

In plain terms: the Markdown vault is the source of truth, the graph is derived from it and can always be rebuilt, and every answer can point back to the exact bytes it came from.

```
Markdown notes → blocks → claims → graph → ask / explore → answer + sources
```

This repo leans on six Neuron features:

| Feature | What it does | Where this repo uses it |
| ------- | ------------ | ----------------------- |
| Sources on every answer | `ask` with `include_sources` returns a block id, a byte range, a content hash and a vault-relative path | Every ask is recorded, and a script re-reads the cited bytes and checks the hash |
| Supersession | When a note is corrected, the old claim is filtered out and the new one points back to it | Steps 4 and 7 |
| Curation view | A review queue for folds, merges and held candidates | Step 7, when an old runbook disagrees with a new rule |
| Several vaults | `ask`, `explore` and `remember` take a vault name per call | A private reviewer vault that must never show up in team answers |
| `synthesis_status` and `explore` | Every answer says whether synthesis worked, and `explore` walks the graph with no model | Step 9, when the model is unreachable |
| Folder watcher and vault pinning | A watched folder keeps a vault in sync, and a `.okto-neuron-vault` file names the project's vault | Setup, and every later note edit |

## The Problem

An agent working in an existing codebase can fail in three quiet ways, and this repo tests Neuron against each one directly:

- **It follows a rule that has since changed.** A team policy gets edited, and the agent keeps building to the old one.
- **It gives an answer nobody can check.** The answer sounds right, but there is no way to see where it came from.
- **Its memory is down and it says nothing useful about that.** Neuron's own guidance for a `provider_error` is never to report "I couldn't find anything", because the model being unreachable does not mean the notes are empty.

Supersession, sources and `synthesis_status` map onto those three. This repo pushes on each of them on a real feature set and reports what actually happened, including where Neuron did not do what the plan hoped.

## How It Works

1. **The Maintainer keeps the rules in notes.** 14 short Markdown notes live in `vault/`: eight read from the app's own code, so each can be checked against a file, and six demo policies that say they are policies. Neuron's folder watcher ingests them into the `team` vault. A second folder, `vault-private/`, feeds the `reviewer-private` vault.
2. **Each role is a fresh session.** Planner, Builder and Reviewer each run as a new `claude -p` session with `--strict-mcp-config`, so a role sees only the MCP configuration `run_demo.py` writes for it.
3. **Scope is enforced at the connection.** The Planner and Builder connect with `?vault=team`. The Reviewer names a vault on every call.
4. **Every ask is recorded from the transcript.** The role's Claude Code transcript already holds the exact tool call and result, so `scripts/neuron_asks.py` reads asks out of it. Each line of `demo-state/asks.jsonl` keeps the answer, its sources, `synthesis_status`, `finish_reason`, whether Neuron reported `vault_override_ignored`, and a hash check on every cited range.
5. **The close-out totals the run.** `scripts/closeout.py` builds `demo-state/closeout-result.json` from those lines and nothing else.

## Neuron in Action

Real captures from the `team` vault after the recorded run.

**Curation**: the review queue after steps 2 to 8: 81 items, all held node candidates. "Predicate folds" and "Entity merges" both say nothing is waiting:

![Curation view of the team vault](docs/images/neuron-curation-team.png)

**Query**: the web UI answering with sources. The answer still says 15 minutes, citing the spec the Planner wrote in step 2 at byte range 239 to 1318, which is an old version of that file (the full explanation is under [The Recorded Run](#the-recorded-run)):

![Query view with sources](docs/images/neuron-query-sources.png)

**A response with sources**, as the MCP `ask` tool returns it. This one is from the setup check on 2026-10-22, trimmed to one source and the fields that matter, and the full response is `tests/fixtures/ask_ok.json`:

```json
{
  "status": "ok",
  "text": "The comment edit window is 15 minutes.",
  "sources": [
    {
      "block_id": "33b965073c7f4062df85169dbccb56c0dc80ff9b8d292661710aee61e1426805",
      "byte_start": 0,
      "byte_end": 177,
      "content_hash": "sha256:5d698c556e6788e55147ce816e5efd51f65bec38024eea6a75b78dc8475a9f0f",
      "path": ".marginalia/sources/14bfef7e474715c5/setup-test.md"
    }
  ],
  "retrieval": { "synthesis_status": "ok", "finish_reason": "stop" }
}
```

Re-reading bytes 0 to 177 of that file and hashing them gives the same `content_hash`. `tests/test_verify_citations.py` checks it.

The same setup check also produced a real `provider_error`: the model hit a rate limit, the response came back `degraded` with empty text, and the sources were still returned (`tests/fixtures/ask_provider_error.json`). That is what an agent must not mistake for "the notes say nothing".

## Architecture

![Architecture](docs/images/architecture.svg)

Three roles talk to one Neuron daemon over MCP. The daemon serves two vaults, each fed by its own watched folder. Nothing the agents do is trusted on its own: the recorder reads their transcripts, and the verifier re-reads the cited bytes.

![The ten steps: setup, three features, two Maintainer edits, the outage and the close-out](docs/images/flow.png)

**Reading the flow**

1. **Setup**: Neuron is onboarded, both vaults are created, and the 14 notes are loaded through the folder watcher.
2. **Feature work**: each feature is planned, built and reviewed by fresh sessions that share nothing except Neuron.
3. **The Maintainer's edits (orange)**: step 4 changes a rule, and step 7 replaces a rule and adds a note that still states the old one. These are what test supersession and the Curation view.
4. **The outage (red)**: in step 9 every ask returns `provider_error`, and the agent has to say so and use `explore`.
5. **Close-out**: the totals come only from recorded asks and recorded ingest times.

## Repository Structure

| Path | Purpose |
| ---- | ------- |
| `README.md` | This document |
| `app/` | Fork of [gothinkster/node-express-realworld-example-app](https://github.com/gothinkster/node-express-realworld-example-app) (Node, Express, Prisma, Postgres), with the three demo features added by the Builder |
| `vault/` | The Maintainer's 14 starting notes for the `team` vault, plus the step 7 runbook and the specs the Planner wrote |
| `vault-private/` | Notes for the `reviewer-private` vault. Git-ignored and not shipped. [An example of its contents](docs/examples/reviewer-private-setup-note.md) |
| `demo-state/` | Recorded asks, explores, transcripts, ingest times, the Curation queue summary and the close-out file from the run |
| `agents/` | One `CLAUDE.md` per role and the shared [Neuron skill](agents/neuron-skill.md) |
| `docs/prompts/` | One prompt per role per step |
| `docs/VERIFIED.md` | What was run, on which machine and date, and what happened |
| `docs/walkthrough.md` | Step-by-step guide from clone to close-out |
| `docs/images/` | The banner, the architecture diagram and the screenshots |
| `scripts/` | The ask recorder, citation verifier, close-out, ingest wait, Maintainer edits and setup |
| `tests/` | Unit tests, with real recorded responses as fixtures |
| `run_demo.py` | Replays any set of steps |
| `docker-compose.yml` | Postgres for the app |
| `.env.example`, `.mcp.json.example`, `.okto-neuron-vault` | Settings template, MCP template, and the vault pin |
| `.github/workflows/validate.yml` | The checks that run on every push |

## Workspace & Demo Data

| Field | Value |
| ----- | ----- |
| Repo / demo name | `neuron-brownfield-longrun-demo` |
| Vaults | `team` (fed by `vault/`) and `reviewer-private` (fed by `vault-private/`) |
| Target application | `app/` (fork of `gothinkster/node-express-realworld-example-app`) |
| Roles | Planner, Builder, Reviewer, and the Maintainer who edits the notes |
| Model used by Neuron and by every role session in the recorded run | `claude-haiku-5-5` |
| Recorded run | One run of steps 2 to 9 plus the close-out, on 2026-10-23, on macOS arm64 |
| Step 1 | Done by hand with the commands in [docs/VERIFIED.md](docs/VERIFIED.md), not through `scripts/setup_vaults.sh` |
| Step 9 outage | Made with an invalid key in the daemon's environment, not a stopped endpoint |

## Roles

Roles are separated by task, by fresh sessions, and by the MCP configuration each one is handed. The tool lists are in `scripts/steps.py`, and the standing rules are in `agents/`.

| Role | Does | Vault access | Can edit | Cannot do |
| ---- | ---- | ------------ | -------- | --------- |
| Planner | Asks for the rules and writes a short spec for each feature | `team`, pinned at the connection | `vault/specs/` | Write application code |
| Builder | Writes the migration, endpoint and tests from the spec and the rules | `team`, pinned at the connection | `app/` | Touch the vaults or the specs |
| Reviewer | Checks each diff against the current rules, cites the source, keeps private findings | `team` and `reviewer-private`, named on each call | `vault-private/` | Fix code, or put private findings anywhere under `vault/` |
| Maintainer (you) | Edits two rules and adds the old runbook | n/a | `vault/` | n/a |

Neuron runs one daemon per project on the machine, with a bearer-authenticated MCP port. `list_vaults` returns names only, so any role can see every vault name on the machine. The agent rules say to use only `team` and `reviewer-private`, and the close-out counts any ask to another vault (zero in the recorded run).

## Tools Used

Neuron's MCP server exposes five tools. These roles use three of them:

| Tool | Used for |
| ---- | -------- |
| `ask` | Planner, Builder and Reviewer ask for rules, with `include_sources` and a vault name |
| `explore` | The Reviewer's fallback in step 9, which walks the graph with no model |
| `list_vaults` | Checking which vaults exist (returns names only) |

Not used on purpose: `remember`, because ingest takes minutes and Claude Code aborts a tool call after 300 seconds, so notes enter through the folder watcher instead. Subgraph answers are also left off, because Neuron keeps source-block synthesis as its default.

## Prerequisites

Everything here was checked on **macOS 26 on Apple silicon (arm64)**. Neuron's own README says its install was rehearsed on Linux and that no published version has passed a Windows PowerShell lifecycle. This repo does not claim either of those.

| Requirement | Notes |
| ----------- | ----- |
| [Okto Neuron](https://github.com/OktoLabsAI/okto-neuron) | Installed with the command in its README |
| A model for Neuron | Neuron's curation makes many model calls per note. Free tiers did not hold up: a free Gemini key allowed 5 requests per minute and a free OpenRouter key hit its daily limit within minutes. Anthropic needed a workspace-scoped key and `--api-base https://api.anthropic.com`. See [docs/VERIFIED.md](docs/VERIFIED.md) |
| `claude` CLI | `run_demo.py` uses `claude -p`, `--strict-mcp-config` and `--mcp-config` |
| Python 3.9+ | The scripts use only the standard library |
| Docker | For the app's Postgres |
| Node and npm | For the app. Its own `auth.service` test suite fails on Node 26 before it loads, and on Node 22 it loads but still fails a few tests, with a count that changed between runs. The demo does not depend on those tests passing |

## Quickstart

```bash
git clone <this repo> && cd neuron-brownfield-longrun-demo
```

1. Install Neuron with the command from its README, then confirm it with `okto-neuron --version`.

2. Start the app's database and prepare the app:

```bash
docker compose up -d
cd app && npm install
DATABASE_URL=postgresql://realworld:realworld@localhost:5433/realworld npx prisma generate
DATABASE_URL=postgresql://realworld:realworld@localhost:5433/realworld npx prisma migrate deploy
cd ..
```

`npm install` under npm 11 skips the install scripts, which is why `prisma generate` is run by hand.

3. Copy `.env.example` to `.env`, fill in the model settings and key, and load it:

```bash
cp .env.example .env
set -a; source .env; set +a
```

4. See every prompt without running anything. This needs no Neuron:

```bash
python3 run_demo.py --dry-run
```

5. Run it:

```bash
python3 run_demo.py                 # all ten steps
python3 run_demo.py --steps 4 7 9   # only some steps
python3 run_demo.py --start 4       # step 4 onward
```

The runner uses `--model claude-haiku-5-5` for every role by default. Pass `--model ''` for Claude Code's own default. Step 1 restarts the Neuron daemon after onboarding, because the daemon read its key file only when it started. With a hosted key, step 9 needs you to break the model yourself, and the runner pauses and asks (pass `--yes` to skip the pause).

OpenRouter users: with `DEMO_LLM_PROVIDER=openrouter`, Neuron's model-call helper failed about half the time in testing, because litellm printed a banner after the JSON for a model name it does not recognise. `DEMO_LLM_PROVIDER=openai` with `DEMO_LLM_API_BASE=https://openrouter.ai/api/v1` avoided it in 6 of 6 hand-run calls.

## Running the Target App (`app/`)

The app is a Node, Express and Prisma API on Postgres. With the database up and the migrations applied (Quickstart step 2):

```bash
cd app
DATABASE_URL=postgresql://realworld:realworld@localhost:5433/realworld npm start
```

The API is then at http://localhost:3000, and its routes are mounted under `/api`. Unit tests run with `npx nx test api`. The database is mocked in those tests, so they do not need Postgres. The three demo features add a comment edit endpoint (`PUT /api/articles/:slug/comments/:id`), a cap on the article list `limit`, and soft delete for comments.

## The Ten Steps

| Step | What happens | Shows |
| ---- | ------------ | ----- |
| 1 | Onboard Neuron, create both vaults, load the 14 notes through the folder watcher | Setup, pinning |
| 2 | Planner asks for the rules for feature 1 (comment editing) and writes the spec | Answers with sources |
| 3 | Builder adds `PUT /api/articles/:slug/comments/:id` and an `editedAt` migration, using a 15 minute window | An agent working from cited rules |
| 4 | Maintainer changes the window to 30 minutes. A fresh Reviewer asks and checks the code | Supersession |
| 5 | A fresh Builder fixes the window. Reviewer approves and logs a private finding | Vaults |
| 6 | Feature 2, a cap on the article list limit, is planned, built and reviewed | Recall across fresh sessions |
| 7 | Maintainer replaces the error response rule and adds `ops-runbook.md`, which still describes the old one | A conflict across files, and the Curation view |
| 8 | Feature 3, soft delete for comments, is built to the new error rule and reviewed against it | The current rule wins, with proof |
| 9 | The model is unreachable. Asks return `provider_error`, and the agents report it and fall back to `explore` | Honest failure |
| 10 | The close-out script totals the run and checks every citation | The scoreboard |

The walkthrough in [docs/walkthrough.md](docs/walkthrough.md) explains each step, and the prompts are in [docs/prompts/](docs/prompts/).

## The Recorded Run

Steps 2 to 9 ran once on 2026-10-23. The numbers below come from `demo-state/closeout-result.json`.

| Measure | Result |
| ------- | ------ |
| Questions asked / returning sources | 36 / 36 |
| `synthesis_status` | `ok` 35, `provider_error` 1, all other values 0 |
| `finish_reason` other than `stop` | 0 |
| Citations that passed the hash check | 638 of 763 at record time, 616 on a recheck at the end |
| Rules replaced by the Maintainer | 2 (edit window, error response) |
| Answers still giving the replaced edit window after the edit | 5 (a text match, so a heuristic; the transcripts are the ground truth) |
| Answers still giving the replaced error rule after step 7 | 0 |
| `provider_error` answers | 1, and the agent did not say nothing was found |
| Asks to a vault other than `team` and `reviewer-private` | 0 |
| Private notes in `team` answers | 0 |
| Ingest of the 14 starting notes | At most 636 seconds, 151 model calls, no failures |

What these numbers hide, in plain terms:

- **The 125 failed citations all trace to notes that changed.** The Planner wrote each spec twice, because its role file said "under 1500 characters" and its first draft was longer. Neuron kept answering with anchors into the first version, and `policy-error-response.md` did the same after the Maintainer edited it. The hash check caught each one. The Planner's role file now says to write once, but the run was not repeated.
- **Supersession did not show up the way the plan expected.** After the Maintainer changed the edit window to 30 minutes, the step 4 Reviewer was still told 15 minutes. Our spec had copied "15" into a second note, which was our design fault, and the Reviewer saw the conflict but passed the code. The step 5 Builder's second ask returned 30 and it fixed the code. Neuron did not name 15 as a replaced value in any answer.
- **The Curation view did not flag the stale runbook.** Its queue held 81 low-confidence items and none was a conflict between `ops-runbook.md` and the new error rule. The step 8 agents caught the conflict themselves: the Planner noted it, and the Reviewer flagged the runbook and an old-shape error in the comment edit code.
- **Some agent commands were denied** (`git -C`, `git status`, `cd app && ...`), so the step 5 Builder reported no test result. The tool allow-list was widened afterwards and not re-run.
- **The step 9 outage was an authentication error,** from an invalid key, not a stopped endpoint.

## Where to Find Artifacts

| What | Where | Status |
| ---- | ----- | ------ |
| Every recorded ask | `demo-state/asks.jsonl` | Recorded, 36 asks |
| Neuron `explore` calls | `demo-state/explores.jsonl` | Recorded, 1 call (step 9) |
| Role transcripts | `demo-state/transcripts/` | Recorded, steps 2 to 9 |
| Ingest times | `demo-state/ingest-times.jsonl` | Recorded |
| Scoreboard | `demo-state/closeout-result.json` | Recorded |
| Curation queue summary | `demo-state/curation-queue-team.json` | Recorded after step 8 |
| Screenshots | `docs/images/` and `demo-state/screenshots/` | Curation view, query with sources, vault list |
| What was verified, where and when | [docs/VERIFIED.md](docs/VERIFIED.md) | Written |
| The code the agents wrote | `app/` | Written by the Builder in the recorded run |

The scoreboard covers: questions asked and how many returned sources, citations that passed the hash check, claims replaced and any stale rule an agent still followed, answers marked `provider_error` and how each agent handled them, private notes that appeared in team answers (the target is zero), and ingest time per note.

## Known Limits

- A 15,882 byte file took 297 seconds to ingest on one LAN server and 1,536 seconds on a local endpoint, according to Neuron's README. Notes here stay short and each step waits for ingest to finish.
- Neuron's document ids hash absolute paths, so the repo ships Markdown notes, recorded answers and screenshots, not a vault snapshot.
- One document over 65,536 characters fails on Neuron's default graph backend. Every note here is far smaller.
- A source's `path` points at Neuron's own copy of the note under `.marginalia/sources/` inside the vault, not at the file in `vault/`. The verifier reads that copy.
- The Gemini and Anthropic presets in Neuron's onboarding both needed a different base URL from the one they offer, and its OpenRouter route printed a banner that broke the model-call helper. All of it is in [docs/VERIFIED.md](docs/VERIFIED.md).
- `scripts/setup_vaults.sh` has not been run end to end. CI runs the unit tests and the dry run only.

## Checks

Every push runs: unit tests for the citation verifier on recorded answers, a check that every recorded ask carries a `synthesis_status`, JSON, link, em dash and secret checks, a compile check, and a dry run of all ten steps. The tests cover all six `synthesis_status` values (`ok`, `no_llm`, `empty`, `provider_error`, `truncated`, `abnormal_stop`) and count any `finish_reason` other than `stop` separately. Run them yourself with `python3 -m unittest discover -s tests`.

## Contributing & Licensing

To reproduce the demo or iterate on it: fork this repo, install Neuron, and follow the Quickstart. A cleaner second run would start from the fixes listed above.

The licence for this repository has not been added yet. The app under `app/` keeps the licence of the upstream project it was forked from.

## Conclusion

The question this repo asks is narrow: when rules change under a team of agents with no shared memory, do they follow the current rule, show where it came from, and say so honestly when the memory cannot answer. In the recorded run the sources and the hash check worked, the model outage was reported honestly, and no private note reached a team answer. Supersession and the Curation view did not do what the plan hoped. The agents reached the current rule through their own reading of the notes, not because Neuron marked the old value as replaced.

Built on Okto Neuron, an Okto Labs product. This repo records what happened, and lists what a cleaner second run should change.
