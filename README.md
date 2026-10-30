# neuron-brownfield-longrun-demo

![Neuron Brownfield Longrun Demo: three agents, two vaults, every answer shows its source](docs/images/banner-flat.png)

Three agents. Two vaults. Every answer shows its source.

Three features added to an existing blogging API over ten steps by AI agents that remember nothing between sessions. Two team rules change in the middle. The question is whether Okto Neuron keeps the agents on the rule that is current, compared with agents that have no memory and with agents that are handed the current notes in their prompt.

[Status](#status) · [About Okto Neuron](#about-okto-neuron) · [The Problem](#the-problem) · [What This Demo Does Not Establish](#what-this-demo-does-not-establish) · [How It Works](#how-it-works) · [Channels and Inputs](#channels-and-inputs) · [Neuron in Action](#neuron-in-action) · [Architecture](#architecture) · [Repository Structure](#repository-structure) · [Workspace & Demo Data](#workspace--demo-data) · [Roles](#roles) · [Tools Used](#tools-used) · [Prerequisites](#prerequisites) · [Quickstart](#quickstart) · [Running the Target App](#running-the-target-app-app) · [The Ten Steps](#the-ten-steps) · [The Pilot Run](#the-pilot-run) · [The Comparison](#the-comparison) · [Where to Find Artifacts](#where-to-find-artifacts) · [Known Limits](#known-limits) · [Checks](#checks) · [Contributing & Licensing](#contributing--licensing) · [Conclusion](#conclusion)

## Status

- **One live comparison is recorded: 5 runs in each of the three arms, 15 runs in all**, made on 2026-10-29 (UTC) on macOS arm64 with Okto Neuron 0.3.1, Claude Code 2.1.312 and `claude-haiku-5-5` for every role and for Neuron. Every run went through all its steps. The folders are `runs/<arm>/run-01` to `run-05`; [The Comparison](#the-comparison) has the tables. Only 2 of the 11 work products per run can be scored without a person (the edit endpoint after the edit-window change, and the article list cap), so the scores are over those two.
- **Result on those two products** (each run scores 0 or 1 on each product): no memory 0.0 and 0.0; notes in the prompt 0.4 (min 0, max 1) and 1.0; Neuron 0.8 (min 0, max 1) and 1.0; n=5 per arm. **This does not show Neuron beating the notes pasted into the prompt.** All 10 runs of those two arms put a 30 minute window into the code. The 4 of 5 against 2 of 5 comes from one detail of the check: an edit refused outside the window answered with a 4xx (counted) or with an unhandled-error 500 (not counted). Five runs per arm cannot separate that from chance. Both arms beat no memory on the edit window, which is what any rule source would be expected to do.
- **Hand labels are pending. Nobody has labeled anything by hand.** The other 9 products per run (tests, specs, Reviewer verdicts, the error shape) need a person: 15 empty label sheets are in `labels/`, and 50 of the Neuron arm's answers are sampled for a citation-support label (`labels/support-sample-neuron-run-0N.json`). No full-metric score exists. A model (`claude-sonnet-5-5`, same vendor family as the agents) drafted the same labels in `labels-model/`; they are marked as model-labelled and are not used for any number here. Yuvi read their summaries and sampled examples and found no problems; nobody has read every label, and they need a fuller human check before they could serve as a judge (see `labels-model/README.md`).
- **What the Neuron arm showed about Neuron itself:** after each of the two edits, Neuron's answer to a neutral question gave the new value in 10 of 10 probes and the replaced value in 0 of 10, but no probe contained the word "supersed", and an `explore` still returned the replaced edit window in 2 of 5 runs. 151 of 3,479 citations were stale anchors (4.3%) and none failed any other way. The scripted step 9 outage came back as `provider_error` in 5 of 5 runs and no agent claimed the notes were empty. Details and the raw files: [docs/PRODUCT-OBSERVATIONS.md](docs/PRODUCT-OBSERVATIONS.md).
- **One pilot run** stays recorded in `demo-state/` (steps 2 to 9 plus the close-out, 2026-10-23, one model, one run). It is a labeled pilot. Its roles were not isolated from the notes, the plan or each other, so it cannot support a claim that Neuron caused alignment. See [The Pilot Run](#the-pilot-run) and `demo-state/README.md`.
- **What the pilot supports:** Neuron returned cited sources whose bytes can be hashed again, and it reported `provider_error` honestly when its model was unreachable. The live runs repeat both.
- What was verified, on which machine and with which commands, including what broke and was fixed on the way: [docs/VERIFIED.md](docs/VERIFIED.md). Neuron findings: [docs/PRODUCT-OBSERVATIONS.md](docs/PRODUCT-OBSERVATIONS.md).

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
| Supersession | When a note is corrected, the old claim is filtered out and the new one points back to it | Steps 4 and 7. In the live runs the new value won every probe, but no supersede marker was ever visible ([The Comparison](#the-comparison)) |
| Curation view | A review queue for folds, merges and held candidates | Step 7: the pilot's queue held no conflict item for the stale runbook |
| Several vaults | `ask`, `explore` and `remember` take a vault name per call | A private reviewer vault that must never show up in team answers |
| `synthesis_status` and `explore` | Every answer says whether synthesis worked, and `explore` walks the graph with no model | Step 9, when the model is unreachable |
| Folder watcher and vault pinning | A watched folder keeps a vault in sync, and a `.okto-neuron-vault` file names the project's vault | Setup, and every later note edit |

## The Problem

An agent working in an existing codebase can fail in three quiet ways, and this repo tests Neuron against each one directly:

- **It follows a rule that has since changed.** A team policy gets edited, and the agent keeps building to the old one.
- **It gives an answer nobody can check.** The answer sounds right, but there is no way to see where it came from.
- **Its memory is down and it says nothing useful about that.** Neuron's own guidance for a `provider_error` is never to report "I couldn't find anything", because the model being unreachable does not mean the notes are empty.

Supersession, sources and `synthesis_status` map onto those three. This repo pushes on each of them on a real feature set and reports what actually happened, including where the results differed from the plan. A scenario in one page: [docs/business-scenario.md](docs/business-scenario.md).

## What This Demo Does Not Establish

- It does not show that Neuron causes alignment. The recorded comparison is 5 runs per arm on two executable products. It found no reliable difference between Neuron and the notes pasted into the prompt, and the hand labels for the other nine products are not done.
- It does not show that the result holds for any model other than the one pinned in `pins.json`, or for any other app.
- It does not show Linux or Windows support. Everything recorded was done on macOS on Apple silicon (arm64). Neuron's own README says its install was rehearsed on Linux and that no published version has passed a Windows PowerShell lifecycle. The opt-in integration workflow runs on Linux and has not been started yet.
- It is five runs per arm of one model. Model output is not deterministic, and `claude -p` offers no seed or temperature setting, so any single run is one sample. Five is the smallest number the metric accepts, not a sample that could call a small difference real. The spread over the runs is what the tables report.
- It does not test `remember` (notes enter through the folder watcher) or Neuron's subgraph answers.

## How It Works

1. **The Maintainer keeps the rules in notes.** 13 starting notes live in `vault/`: seven summaries the author wrote from the app's own code, and six team rules that are synthetic. [scenarios/README.md](scenarios/README.md) labels each one. Neuron's folder watcher ingests them into the `team` vault. A second folder, `vault-private/`, feeds the `reviewer-private` vault from three synthetic private notes.
2. **Each role is a fresh session in a clean directory.** Planner, Builder and Reviewer each run as a new `claude -p` session. The session's working directory is a temporary folder that holds only what that role needs ([scripts/build_workdir.py](scripts/build_workdir.py)). The notes, the plan and the docs are not in it.
3. **Three arms, same everything else.** Arm A has no notes and no Neuron. Arm B has the current notes pasted into each prompt. Arm C has Neuron. The task prompts, the fixed questions, the model, the turn limit and the tool limits are identical ([docs/METRIC.md](docs/METRIC.md)).
4. **The rule change is a file copy with a timestamp.** At step 4 and step 7 the Maintainer script copies the post-change notes in and writes a UTC event. In arm C the runner waits for ingest, writes another event, and asks Neuron a neutral question before any role runs (`scripts/state_probe.py`).
5. **Every ask is recorded from the transcript**, with its UTC time, and every cited range is hashed again. After each session the isolation checker reads the transcript.
6. **The close-out totals the run** and checks the README's numbers against the recorded files.

## Channels and Inputs

**What the roles share, exactly.** Roles share no memory, no notes folder and no repository. Three channels cross between sessions, and nothing else:

| Channel | From to | What crosses |
| ------- | ------- | ------------ |
| The `app/` tree | Builder to Reviewer, and to the next Builder | The code and tests the Builder wrote, as a working tree with a git baseline of the unmodified app |
| Spec files | Planner to Builder | One Markdown spec per feature, written to `specs/`. A spec names rules and where they came from and carries no rule value; the runner scans each spec for rule values |
| The Reviewer's private folder | Reviewer to the Reviewer's later sessions | Markdown findings the runner copies into `vault-private/`, where Neuron ingests them into `reviewer-private` (arms B and C) |

The rule text reaches a role only through its arm's rule source: Neuron's MCP tools (C), the notes in the prompt (B), or nothing (A). `scripts/check_transcripts.py` fails when a transcript shows a role reaching a note, a plan document or a path outside its working directory. Wherever the pilot reached them: [The Pilot Run](#the-pilot-run).

**Everything each role can see.** Enforced by the working directory, not by a prompt.

| Role | Task prompt | Standing rules | Working directory holds | Built-in tools | Rule source by arm |
| ---- | ----------- | -------------- | ----------------------- | -------------- | ------------------ |
| Planner | `docs/prompts/NN-planner.md` | `agents/planner/CLAUDE.md`, `agents/common.md` | `app/` (read), `specs/` (writes the spec) | Read, Grep, Glob, Write | A: none. B: notes in the prompt. C: Neuron, pinned to `team` |
| Builder | `docs/prompts/NN-builder.md` | `agents/builder/CLAUDE.md`, `agents/common.md` | `app/`, `specs/`, a git repository whose history holds only the app baseline | Read, Grep, Glob, Edit, Write, Bash (`git diff`, `git status` only) | same |
| Reviewer | `docs/prompts/NN-reviewer.md` | `agents/reviewer/CLAUDE.md`, `agents/common.md` | `app/` with the Builder's edits, the same git repository, `private-out/` (writes findings) | Read, Grep, Glob, Write, Bash (`git diff`, `status`, `log`, `show` only) | same, with the vault named on each call in C |

Arm C adds `agents/<role>/neuron.md` and `agents/neuron-skill.md` to the system prompt and the Neuron MCP tools to the allow-list. Every prompt ends with the same fixed questions from `docs/questions.json`, asked verbatim in every arm. The standing rules and prompts contain no rule value and no sentence about what a rule change should lead to: `python3 scripts/scan_rule_values.py` fails when they do, and the same scanner checks every recorded question and every spec.

## Neuron in Action

The two web UI screenshots are captures of the `team` vault of the **pilot** run. They first appear in this repository in the commit of 2026-10-23 that also holds `docs/VERIFIED.md`; the exact capture time and how they were taken are not recorded. The harness's own headless screenshot attempt could not reach these views (`docs/VERIFIED.md`), so they were taken by hand in the web UI. The author's home folder and a personal vault name that were visible in them have been covered with placeholders.

**Curation:** the review queue after steps 2 to 8 holds 81 items ("Predicate folds" and "Entity merges" both say nothing is waiting). The UI lists all 81 under "Node candidates"; the saved summary (`demo-state/curation-queue-team.json`) classifies 69 as node candidates and 12 as relation items.

![Curation view of the team vault](docs/images/neuron-curation-team.png)

**Query:** the web UI answering with sources. The answer says 15 minutes after the edit, citing the spec the Planner wrote in step 2 at byte range 239 to 1318, which is the first draft of that file (see [The Pilot Run](#the-pilot-run)):

![Query view with sources](docs/images/neuron-query-sources.png)

**A response with sources**, as the MCP `ask` tool returns it. This is the setup-check fixture from 2026-10-22, a test of the recorder, and it is not part of the ten steps: its source, `setup-test.md`, is a note that was removed before the pilot. It is trimmed to one source and the fields that matter. The full response is `tests/fixtures/ask_ok.json`:

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

![Architecture: the Maintainer's notes feed the Neuron daemon, three role sessions ask it over MCP, and the recorder and verifier check what they did](docs/images/architecture.png)

Three roles talk to one isolated Neuron daemon over MCP. The daemon serves two vaults, each fed by its own watched folder. Nothing the agents do is trusted on its own: the recorder reads their transcripts, the verifier re-reads the cited bytes, and the isolation checker reads every tool call. (The picture shows arm C only, because the other two arms have no daemon. Its "13 team notes" label was redrawn from the pilot's "14" to match the starting set; nothing else in the image changed. The picture of the ten steps that used to sit below it said the sessions "share nothing except Neuron", which the pilot disproved, so it was removed.)

The same architecture as a diagram you can edit in place:

```mermaid
flowchart TD
    M(["Maintainer"]) -->|"1 edits notes"| N["Notes on disk<br/>vault/ and vault-private/"]
    N -->|"2 folder watcher ingests"| D["Okto Neuron daemon<br/>claims, graph, MCP server"]
    D <-->|"3 claims and answers"| L["Your LLM"]
    R["Planner, Builder, Reviewer<br/>fresh sessions, clean directories"] <-->|"4 ask, 5 answer with sources"| D
    R -->|"6 transcripts"| REC["Recorder"]
    REC --> A[("asks.jsonl")]
    A --> V["Verifier"]
    D -.->|"7 cited bytes re-read"| V
    V -->|"8 totals"| X["Close-out"]

    classDef person fill:#334155,stroke:#1e293b,color:#ffffff
    classDef svc fill:#4f46e5,stroke:#312e81,color:#ffffff
    classDef data fill:#0d9488,stroke:#134e4a,color:#ffffff
    classDef check fill:#16a34a,stroke:#14532d,color:#ffffff
    class M person
    class D,R,L svc
    class N,A data
    class REC,V,X check
```

**The flow**

1. **Setup**: the pinned Neuron is checked, an isolated daemon starts, both vaults are created, and the 13 starting notes are loaded through the folder watcher.
2. **Feature work**: each feature is planned, built and reviewed by fresh sessions in clean directories.
3. **The Maintainer's edits (orange)**: step 4 changes a rule, and step 7 replaces a rule and adds a note that still states the old one.
4. **The outage (red)**: in step 9 the script restarts the isolated daemon with an invalid key, runs the Reviewer, and restores the daemon in a `finally` block.
5. **Close-out**: the totals come only from recorded asks and recorded ingest times.

## Repository Structure

| Path | Purpose |
| ---- | ------- |
| `README.md` | This document |
| `app/` | Fork of [gothinkster/node-express-realworld-example-app](https://github.com/gothinkster/node-express-realworld-example-app) (Node, Express, Prisma, Postgres) at its starting state. The code the pilot's Builders wrote is `demo-state/pilot-builder-edits.patch` |
| `vault/` | The Maintainer's 13 starting notes for the `team` vault, the folder Neuron watches |
| `vault-private/` | Created at setup from `scenarios/private-notes/` (synthetic), plus whatever the Reviewer writes. Git-ignored |
| `scenarios/` | Post-change notes per step, the synthetic private and decoy notes, rule values, work products, the executable outcome check. [README](scenarios/README.md) |
| `agents/` | `common.md` (all roles, all arms), one `CLAUDE.md` per role, one `neuron.md` per role and `neuron-skill.md` (arm C only) |
| `docs/prompts/` | One task prompt per role per step, and `negative/` for the boundary tests |
| `docs/questions.json` | The fixed questions, asked verbatim in every arm |
| `docs/METRIC.md` | The written metric, defined before any comparison run |
| `docs/NEURON-USAGE.md` | Every Neuron command and path used, with its documentation pointer or "undocumented" |
| `docs/PRODUCT-OBSERVATIONS.md` | What the demo found about Okto Neuron itself, with evidence |
| `docs/VERIFIED.md` | What was run, on which machine and date, and what happened (vendor workflow detail lives here) |
| `docs/business-scenario.md`, `docs/walkthrough.md` | The scenario in one page, and a step-by-step guide |
| `demo-state/` | The pilot run's record. [README](demo-state/README.md) |
| `runs/` | Where runs are recorded: 15 runs (5 per arm) and one negative test. [README](runs/README.md) |
| `labels/` | Label formats, 15 empty label sheets, 5 unlabeled citation-support samples of the new runs and the pilot's sample. Nothing labeled yet |
| `labels-model/` | Model-labelled drafts of the 15 sheets and the 5 citation-support samples (`claude-sonnet-5-5`), their reports and `draft-scores.json`. Not human labels, not scored in this README |
| `scripts/` | Runner pieces, recorder, verifier, close-out, checkers, scorers, setup. `scripts/check_all.py` runs the offline checkers |
| `tests/` | Unit tests; recorded responses and one recorded transcript event serve as fixtures |
| `run_demo.py` | Replays any set of steps in any arm |
| `pins.json` | The pinned Neuron release (URL, SHA-256), claude CLI version and model |
| `docker-compose.yml` | Postgres for the app |
| `.env.example`, `.mcp.json.example`, `.okto-neuron-vault` | Settings template, MCP template, and the vault pin |
| `.github/workflows/validate.yml` | The fast static checks. It never starts Neuron |
| `.github/workflows/integration.yml` | The opt-in live run on a pinned Neuron |
| `LICENSE` | MIT, copyright OktoLabs AI, for the demo code only |
| `THIRD_PARTY_NOTICES.md` | Where `app/` comes from, and the licence question for `app/` that is still open |

## Workspace & Demo Data

| Field | Value |
| ----- | ----- |
| Repo / demo name | `neuron-brownfield-longrun-demo` |
| Vaults | `team` (fed by `vault/`) and `reviewer-private` (fed by `vault-private/`); `decoy` only for the negative test |
| Target application | `app/` (fork of `gothinkster/node-express-realworld-example-app`) |
| Roles | Planner, Builder, Reviewer, and the Maintainer who edits the notes |
| Pinned Neuron | 0.3.1, installed from its release wheel with the SHA-256 in `pins.json` |
| Model used by Neuron and by every role session in the pilot | `claude-haiku-5-5` |
| Pilot | One run of steps 2 to 9 plus the close-out, on 2026-10-23, on macOS arm64 |
| Comparison | 5 runs each of arms A, B and C on 2026-10-29 (UTC), macOS arm64, `claude-haiku-5-5`, Claude Code 2.1.312, Node 22.23.4. The five Neuron-arm runs ran side by side, each on its own isolated daemon (REST ports 17911 to 17915, MCP ports 18511 to 18515) |
| Step 1 | Run by `scripts/setup_vaults.sh` in each Neuron-arm run and in the negative test. In the pilot it was done by hand |
| Step 9 outage in the pilot | An invalid key in the daemon's environment, set by hand. The script now does it and restores the daemon |

## Roles

The tool lists are in `scripts/steps.py`, the standing rules in `agents/`.

| Role | Does | Vault access | Writes | Cannot do |
| ---- | ---- | ------------ | ------ | --------- |
| Planner | Gathers the rules and writes a short spec for each feature | `team`, pinned at the connection | `specs/` | Write application code |
| Builder | Writes the migration, endpoint and tests from the spec and the rules | `team`, pinned at the connection | `app/` | Run the app or its tests |
| Reviewer | Checks each diff against the current rules, keeps private findings | `team` and `reviewer-private`, named on each call | `private-out/` | Fix code |
| Maintainer (you) | Edits two rules and adds the old runbook | n/a | `vault/` | n/a |

**Which boundaries are enforced and which are a prompt.**

| Boundary | Strength | How |
| -------- | -------- | --- |
| A role cannot read notes, the plan or the docs | Enforced by the working directory | They are not in it. The checker reads the transcript to prove it, and tool scoping (`Read(./**)`, `Edit(<own folder>/**)`) backs it up |
| Planner and Builder cannot read `reviewer-private` | Enforced at the connection | They connect with `?vault=team`. A per-call vault is discarded and reported as `vault_override_ignored` (Neuron README, "MCP tools") |
| The Reviewer should use only `team` and `reviewer-private` | **A prompt rule only** | The Reviewer connects with no `?vault=` and names the vault on each call. `list_vaults` returns every vault name on the daemon. Nothing but its instructions stops it from naming another vault |

The demo runs on its own isolated daemon, so `list_vaults` shows only the demo's vaults (in the pilot a personal vault on the shared daemon was visible to every role). `python3 run_demo.py --negative` tells a pinned role to ask `reviewer-private`, and the Reviewer to ask a `decoy` vault, and records what happens (`scripts/negative_test.py`). **It was run once on 2026-10-29** (`runs/negative/neg-01/`): the Planner and the Builder declined without making a single call, so `vault_override_ignored` was never exercised; the Reviewer declined to ask `decoy`, asked `team` instead, and no decoy or private text came back. That is one session per role of one model. It shows that `claude-haiku-5-5` followed the prompt rule in that sample. It does not show that nothing stops a role from naming another vault, and the connection-level enforcement was not tested by it.

## Tools Used

Neuron's MCP server exposes five tools. These roles use three of them:

| Tool | Used for |
| ---- | -------- |
| `ask` | The fixed questions, with `include_sources` and a vault name |
| `explore` | The Reviewer's fallback in step 9, which walks the graph with no model |
| `list_vaults` | Checking which vaults exist (returns names only) |

`remember` is not used. In the pilot environment Claude Code aborted a tool call after 300 seconds and Neuron's README measures ingests that take minutes, so notes enter through the folder watcher. That is a limit of this setup, not a statement about Neuron. Subgraph answers are left off because Neuron keeps source-block synthesis as its default.

## Prerequisites

Everything recorded was checked on **macOS 26 on Apple silicon (arm64)**.

| Requirement | Notes |
| ----------- | ----- |
| `uv`, `curl`, Python 3.9+ | `scripts/install_neuron.sh` uses `uv` to install the pinned release. The scripts use only the Python standard library |
| [Okto Neuron](https://github.com/OktoLabsAI/okto-neuron) 0.3.1 | Installed by `scripts/install_neuron.sh` into the demo's own folder, checked against the SHA-256 in `pins.json`. Every run checks `okto-neuron --version` and stops if it differs |
| A model for Neuron | Neuron's curation makes many model calls per note, so a free tier is likely too small. Provider details and the pilot's experience: [docs/VERIFIED.md](docs/VERIFIED.md) |
| `claude` CLI | `run_demo.py` uses `claude -p`. The pin is in `pins.json`; the version of every run is in its manifest |
| Docker, Node and npm | **Node 22** and `npm ci` in `app/` for the executable outcome check. On Node 25 or later the app's dependencies fail to load (`SlowBuffer`, removed in Node 25, used by `buffer-equal-constant-time` through `jsonwebtoken`): every outcome is then "error". `scripts/code_outcome.py` keeps jest's message, and `run_demo.py` runs the check on the untouched app before the first model call and stops if it cannot run. Docker is needed only to run the app by hand: the outcome check mocks the database. The app's own test suite is flaky (`docs/VERIFIED.md`) and the demo does not use it as a signal; the prompts do not ask the Builder to run it |

## Quickstart

```bash
git clone <this repo> && cd neuron-brownfield-longrun-demo
```

1. See every prompt without running anything. This needs no Neuron, no model and no network:

```bash
python3 run_demo.py --dry-run                # arm C, the Neuron arm
python3 run_demo.py --dry-run --arm notes    # the same prompts with the notes pasted in
python3 run_demo.py --dry-run --arm none     # the same prompts with no rule source
```

2. Run the offline checks and tests:

```bash
python3 -m unittest discover -s tests
python3 scripts/check_all.py
```

3. For a live run, install the pinned Neuron into the demo's own folder and prepare the app's dependencies:

```bash
bash scripts/install_neuron.sh        # downloads the pinned wheel, checks its SHA-256, runs `uv tool install`
cd app && npm ci && cd ..             # only for the executable outcome check
```

4. Copy `.env.example` to `.env`, fill in the model settings and key, and load it:

```bash
cp .env.example .env
set -a; source .env; set +a
```

5. Run it. A recorded run is never overwritten; pick a new `--run-id`:

```bash
python3 run_demo.py --arm neuron --run-id run-01     # one full run of arm C, steps 1 to 10
python3 run_demo.py --arm notes  --runs 5            # five runs of arm B: run-01 to run-05
python3 run_demo.py --arm none   --runs 5
python3 run_demo.py --reset                          # put the notes and the private folder back to the starting state
```

Step 1 runs `scripts/setup_vaults.sh`: it resets the notes, checks the pinned version, starts an **isolated** daemon (separate `HOME`, REST port 17777, MCP port 18201 by default; override with `DEMO_NEURON_HOME`, `DEMO_NEURON_REST_PORT` and `DEMO_NEURON_MCP_PORT`), onboards both vaults and registers the watched folders. It never touches a daemon or vaults of your own, and the model key is passed to Neuron through an environment variable, not on a command line. Every Neuron-arm run starts from an empty daemon home (`neuron_ctl.reset_state`), so a run never inherits the previous run's graph. Step 9 restarts that isolated daemon with an invalid key and always restores it. Onboarding saves the key in the isolated home (`<home>/.okto-neuron/env`): delete that folder after a run.

**Model output is not deterministic.** `claude -p` takes no seed or temperature, so two runs with the same manifest differ. Each run records its versions in `run-manifest.json`, and the metric reports the spread over repeated runs. Scoring and labels: [docs/METRIC.md](docs/METRIC.md), [labels/README.md](labels/README.md), `python3 scripts/score_runs.py`.

Every command above was run live on 2026-10-29. The study itself ran `--arm none --runs 5 --keep-going`, `--arm notes --runs 5 --keep-going` and five `--arm neuron --run-id run-0N` processes in parallel, each with its own `DEMO_NEURON_*` settings, its own copy of the repository, `HOME` and `CLAUDE_CONFIG_DIR` set to temporary folders, `DEMO_LLM_PROVIDER=anthropic`, `DEMO_LLM_API_BASE=https://api.anthropic.com` and the key in the environment only (`--keep-going` lets a series continue after a run records a hard failure). What broke on the way and what was changed: [docs/VERIFIED.md](docs/VERIFIED.md), section "Live study".

## Running the Target App (`app/`)

The app is a Node, Express and Prisma API on Postgres. With the database up and the migrations applied:

```bash
docker compose up -d
cd app
npm install
DATABASE_URL=postgresql://realworld:realworld@localhost:5433/realworld npx prisma generate
DATABASE_URL=postgresql://realworld:realworld@localhost:5433/realworld npx prisma migrate deploy
DATABASE_URL=postgresql://realworld:realworld@localhost:5433/realworld npm start
```

`npm install` under npm 11 skips the install scripts, which is why `prisma generate` is run by hand. The API is then at http://localhost:3000, and its routes are mounted under `/api`. The demo features (a comment edit endpoint `PUT /api/articles/:slug/comments/:id`, a cap on the article list `limit`, soft delete for comments) are built by the Builder sessions, in a copy of `app/`; `app/` itself holds the starting state. The Postgres password `realworld` in `docker-compose.yml` and `.env.example` is a local demo credential, not a secret.

## The Ten Steps

| Step | What happens | What it exercises |
| ---- | ------------ | ----------------- |
| 1 | Check the pinned Neuron, start an isolated daemon, create both vaults, load the 13 starting notes | Setup, pinning |
| 2 | Planner gathers the rules for feature 1 (comment editing) and writes the spec | Answers with sources |
| 3 | Builder adds `PUT /api/articles/:slug/comments/:id` and the edit marker migration | An agent working from its rule source |
| 4 | Maintainer changes the edit window. A fresh Reviewer checks the code | A rule change, and what the memory does with it |
| 5 | A fresh Builder checks the change against the rules as they now stand. A Reviewer reviews it and logs a private finding | The current rule, and the private vault |
| 6 | Feature 2, a cap on the article list limit, is planned, built and reviewed | A rule that never changes, and a rule that lives partly in code |
| 7 | Maintainer replaces the error response rule and adds `ops-runbook.md`, which still describes the old one | A conflict across files, and the Curation view |
| 8 | Feature 3, soft delete for comments, is planned, built and reviewed | The rule that was replaced at step 7 |
| 9 | The script breaks the model key of the isolated daemon. The Reviewer asks and has to report the outage | Honest failure (arm C only) |
| 10 | The close-out totals the run, verifies every citation, and runs the isolation and outcome checks | The scoreboard |

The walkthrough in [docs/walkthrough.md](docs/walkthrough.md) explains each step, and the prompts are in [docs/prompts/](docs/prompts/).

## The Pilot Run

Steps 2 to 9 ran once on 2026-10-23, before the isolation work. The numbers below come from `demo-state/closeout-result.json` and `demo-state/curation-queue-team.json`; `python3 scripts/check_readme.py` fails if a row differs from them.

| Measure | Result |
| ------- | ------ |
| Questions asked | 36 |
| Questions that returned sources and a non-empty answer | 35 of 36 |
| Questions that returned a source list, with or without an answer | 36 of 36 |
| `synthesis_status` values | `ok` 35, `provider_error` 1, all other values 0 |
| `finish_reason` other than `stop` | 0 |
| Asks with no `finish_reason` at all | 1 |
| Citations that passed the hash check | 638 of 763 at record time, 616 on a recheck at the end |
| Failed citations that are stale anchors | 125 (policy-error-response.md 16, specs/feature-1-comment-editing.md 104, specs/feature-2-article-limit.md 5) |
| Failed citations of any other kind | 0 |
| Rules replaced by the Maintainer | 2 (edit-window, error-response) |
| Answers still giving the replaced edit window after the edit | 5 (text match, a heuristic) |
| Answers still giving the replaced error rule after step 7 | 0 (text match, a heuristic) |
| `provider_error` answers | 1; the agent claimed nothing was found: no |
| `vault_override_ignored` naming the vault the connection was already pinned to | 22 |
| Asks to a vault other than `team` and `reviewer-private` | 0 |
| Private notes in `team` answers | 0 (checked against the author's private notes, which are not shipped) |
| Ingest of the starting notes | at most 636 s, 151 model calls, 0 failed |
| Curation review queue after step 8 | 81 (69 node candidates, 8 relation items `queue_predicate`, 4 relation items `queue_grounding`) |

"Returned sources" means a source list **and** a non-empty answer: the one `provider_error` ask carries 20 sources and no text, and is not counted as a success. A stale anchor is a cited byte range that no longer matches the note (`byte range is past the end of the file` or `hash mismatch`): Neuron answered with an anchor into an earlier version of a note. That is reported as a Neuron behavior with the exact asks in `closeout-result.json`, and separately from the demo fault that caused most of the notes to change (below). The hash check proves that the cited bytes exist. It does not prove that the cited bytes support the answer: [labels/support-sample-pilot.json](labels/support-sample-pilot.json) is a sample prepared for a person to label, and **it has not been labeled**, so the support rate is unknown.

### Pilot outcomes by step

What the recorded transcripts say, not what the plan expected:

| Role and step | Recorded verdict | What the final report said |
| ------------- | ---------------- | -------------------------- |
| 4 Reviewer | No approval verdict | PASS on the edit window against Neuron's answer (15 minutes), while the working-tree note said 30; it noticed the conflict and did not flag the code. `git` was blocked, so it read files directly |
| 5 Reviewer | Not approved | FLAG on the edit window: the spec said 15, the cited note said 30, no replacement was recorded, and it asked the Maintainer to decide |
| 6 Reviewer | No approval verdict | No rule broken in the code; it flagged the cap as a conflict between the policy and the code summary, for the Maintainer |
| 8 Reviewer | No approval verdict | Soft delete passed; new delete error paths broke the current error rule, and the runbook still described the replaced one |

- **The pilot's agents reached the changed rule outside Neuron.** The step 5 Builder's first Neuron answer said 15; it read `vault/policy-edit-window.md` from disk, and its second ask (a leading question that named both values) came back with both. The Reviewer at step 4 saw the changed file in the working tree. Neuron did not name 15 as a replaced value in any recorded answer for the edit window. The five answers that still said 15 are in `closeout-result.json`.
- **125 failed citations trace to notes that changed.** The Planner wrote each spec twice (its role file said "under 1500 characters" and the first draft was longer), so Neuron kept answering with anchors into the first version of those specs. `policy-error-response.md` changed once, at step 7, with no Planner involved, and has 16 of the failures. The same sums are in `docs/VERIFIED.md`.
- **Supersession surfaced differently than the plan expected.** The Planner's spec had copied the value 15 into a second note, so a stale value was served from the spec. The new harness has the Planner name rules and sources without values, and scans each spec for them.
- **The Curation view did not surface the stale runbook.** None of the 81 items is a conflict between `ops-runbook.md` and the new rule. The step 8 agents caught the conflict themselves.
- **Some agent commands were blocked by the tool allow-list** (`git -C`, `git status`, `cd app && ...`), so the step 5 Builder reported no test result. The new tool lists give each role plain `git diff` and no `-C`, and take the app tests out of the prompts.
- **The step 9 outage was simulated with an invalid key,** set by hand in the daemon's environment, not a stopped endpoint, so it exercised the `provider_error` path through an authentication failure.
- **The roles were not isolated.** They read the notes, the spec and `git diff` output from disk, and one `Grep` returned the plan document. Checker output and counts: `demo-state/README.md`.

## The Comparison

Three arms (A no memory, B notes in the prompt, C Neuron) ran the same ten steps on the same app, five times each, on 2026-10-29 (UTC). The runs are `runs/<arm>/run-01` to `run-05`. Each has its manifest, its timeline (`events.jsonl`), its transcripts, the diff of the code after each Builder step and the executable outcome results; the Neuron arm also has its asks, state probes, ingest times, close-out and the daemon's model-call count. The metric was written before the runs ([docs/METRIC.md](docs/METRIC.md)), and `scripts/score_runs.py` refuses a run recorded under another definition. The tables below are generated from the run folders by `scripts/study_summary.py`; `scripts/check_readme.py` fails when they differ from the recorded files.

Every run used `claude-haiku-5-5` for all roles, Claude Code 2.1.312 (the pin says 2.1.309; the manifests record the real one), Node v22.23.4 and, in arm C, Okto Neuron 0.3.1 from the pinned wheel. All 15 runs went through every step they have (arm C has step 9, arms A and B skip it).

### Alignment, the written metric

<!-- BEGIN study-alignment -->
| Arm | Runs recorded | Alignment, rules that change (n, spread) | Alignment, rule that does not change (n, spread) | Products scored per run | Hand labels |
| --- | ------------- | ----------------------------------------- | ------------------------------------------------ | ----------------------- | ----------- |
| A, no memory | 5 | n=5, mean 0.000, sd 0.000, min 0.000, max 0.000 | n=5, mean 0.000, sd 0.000, min 0.000, max 0.000 | 2 of 11 | 0 of 5 runs labeled |
| B, notes in the prompt | 5 | n=5, mean 0.400, sd 0.548, min 0.000, max 1.000 | n=5, mean 1.000, sd 0.000, min 1.000, max 1.000 | 2 of 11 | 0 of 5 runs labeled |
| C, Neuron | 5 | n=5, mean 0.800, sd 0.447, min 0.000, max 1.000 | n=5, mean 1.000, sd 0.000, min 1.000, max 1.000 | 2 of 11 | 0 of 5 runs labeled |
<!-- END study-alignment -->

Three limits on that table. **Only two of the eleven products are scored.** `edit-window/builder-step5/code` is the only product of the two rules that change that has an executable check, and `article-limit/builder-step6/code` is the only one of the rule that does not change. Each is 0 or 1 in a run, so a mean is the share of runs that passed. **The other nine products need a person and have no labels**, so no run has its full score. And n=5 per arm is the minimum the metric accepts.

### The executable checks one by one

<!-- BEGIN study-outcomes -->
| Arm | Runs | step 3 accepts-inside | step 3 refuses-outside | step 5 accepts-inside | step 5 refuses-outside | step 6 caps-above | step 6 keeps-below | step 6 keeps-default |
| --- | ---- | --- | --- | --- | --- | --- | --- | --- |
| A, no memory | 5 | 5 of 5 | 0 of 5 | 5 of 5 | 0 of 5 | 0 of 5 | 5 of 5 | 5 of 5 |
| B, notes in the prompt | 5 | 5 of 5 | 1 of 5 | 5 of 5 | 2 of 5 | 5 of 5 | 5 of 5 | 5 of 5 |
| C, Neuron | 5 | 5 of 5 | 4 of 5 | 5 of 5 | 4 of 5 | 5 of 5 | 5 of 5 | 5 of 5 |
<!-- END study-outcomes -->

The edit window is 15 minutes at step 3 and 30 at step 5. "Accepts" is an edit made 1 minute inside the window, "refuses" one made 1 minute outside it (a 4xx counts, as written in `scenarios/checks/outcome.check.ts` before the runs). "Caps above" is `GET /api/articles?limit=51` reading at most 50 rows. Arm A never put a window or a cap into the code, as expected without a rule source. The last three columns are identical in B and C.

### How the 30 minute window was refused

<!-- BEGIN study-refusal -->
| Arm | Runs | Step 5 code accepts minute 29 | Edit at minute 31: refused with a 4xx (counts as aligned) | refused with a 5xx (an unhandled error; does not count) | not refused, the edit went through | other |
| --- | ---- | ----------------------------- | ---------------------------------------------------------- | -------------------------------------------------------- | ---------------------------------- | ----- |
| A, no memory | 5 | 5 of 5 | 0 | 0 | 5 | 0 |
| B, notes in the prompt | 5 | 5 of 5 | 2 | 3 | 0 | 0 |
| C, Neuron | 5 | 5 of 5 | 4 | 1 | 0 | 0 |
<!-- END study-refusal -->

This is a diagnostic, not a score, from the same check re-run on each run's recorded code (`scripts/rescore_outcomes.py`, which reproduced all 60 live results). Counting a 5xx as a refusal would give B and C 5 of 5 each. A 5xx here means the Builder let an `Error` reach Express's default handler. One B run wrote in its code that no rule sets the status code for a refused edit and chose a plain error. The check's own comment says a 500 is a crash, not a rule; that was decided before any run and was not changed after seeing the results.

### Conduct of the runs

<!-- BEGIN study-conduct -->
| Arm | Runs | Role sessions | Sessions that reached a note, plan or outside path | Blocked attempts | Runs whose specs carry a rule value | Hard failures | Cost in USD per run | Wall time per run (s) |
| --- | ---- | ------------- | -------------------------------------------------- | ---------------- | ----------------------------------- | ------------- | ------------------- | -------------------- |
| A, no memory | 5 | 55 | 0 | 7 | 2 of 5 | 2 | mean 0.099, sd 0.006, min 0.090, max 0.105 | mean 537, sd 28, min 494, max 563 |
| B, notes in the prompt | 5 | 55 | 0 | 3 | 5 of 5 | 1 | mean 0.079, sd 0.005, min 0.071, max 0.086 | mean 451, sd 20, min 420, max 467 |
| C, Neuron | 5 | 60 | 0 | 6 | 1 of 5 | 0 | mean 0.122, sd 0.011, min 0.106, max 0.135 | mean 1811, sd 107, min 1711, max 1964 |
<!-- END study-conduct -->

Isolation is recomputed from the recorded transcripts by `scripts/check_transcripts.py` as it is now. At run time that checker flagged 3 runs (A run-04, A run-05, B run-03) for a role reaching "a forbidden path"; all 3 were false positives of the checker (a `cd` into the session's own folder, a grep pattern, a `Grep` of `app/src` that listed the app's own `tests/` folder), corrected afterwards with tests, and `docs/VERIFIED.md` lists each. The manifests keep what was recorded at run time, so those 3 manifests still list a hard failure. The blocked attempts are tool calls the allow-list refused (mostly `git -C <path>`). "Runs whose specs carry a rule value" counts runs where the Planner wrote a rule value (`editedAt`, `deletedAt`, or "15-minute") into a spec, which is the channel from Planner to Builder; it is a measurement and not a failure. The cost is what Claude Code reported for the role sessions (`total_cost_usd`); Neuron's own model calls are in each Neuron run's `daemon-usage.json` as tokens (about 0.93 to 1.07 million prompt and 0.088 to 0.102 million completion tokens per run) and are not converted to dollars. Arm C's wall time includes 640 to 720 seconds of ingest of the starting notes.

### Neuron's own state right after each edit (arm C)

<!-- BEGIN study-probes -->
| Neuron's own state right after the edit was ingested | Runs probed | Answer gives the new value | Answer gives the replaced value | `explore` result has the new value | `explore` result has the replaced value | Word "supersed" in either result |
| ---------------------------------------------------- | ----------- | -------------------------- | ------------------------------- | ---------------------------------- | ---------------------------------------- | -------------------------------- |
| edit window, after step 4 | 5 | 5 of 5 | 0 of 5 | 0 of 5 | 2 of 5 | 0 of 5 |
| error response, after step 7 | 5 | 5 of 5 | 0 of 5 | 0 of 5 | 0 of 5 | 0 of 5 |
<!-- END study-probes -->

Raw results are in `runs/neuron/run-0N/probes/`. After each edit the runner waits until the daemon has queued the changed file and its queue is idle, then asks the fixed neutral question and calls `explore` on the topic, before any role runs. The derived columns are text matches on the raw results, kept next to them. The two runs whose `explore` still returned the replaced edit window (run-03 and run-04) are the two runs whose later answers carried stale anchors into `policy-edit-window.md`.

### Citations (arm C)

<!-- BEGIN study-citations -->
| Neuron arm | Questions | Sources and a non-empty answer | Citations passing the hash check (record time) | Stale anchors | Other citation failures | Answers still giving a replaced value after its edit | `provider_error` answers (step 9) | of which the agent claimed nothing was found |
| ---------- | --------- | ------------------------------ | ---------------------------------------------- | ------------- | ----------------------- | ----------------------------------------------------- | --------------------------------- | ------------------------------------------- |
| run-01 | 31 | 30 | 603 of 613 | 10 | 0 | 0 | 1 | 0 |
| run-02 | 31 | 30 | 611 of 619 | 8 | 0 | 0 | 1 | 0 |
| run-03 | 38 | 37 | 681 of 756 | 75 | 0 | 0 | 1 | 0 |
| run-04 | 34 | 33 | 632 of 671 | 39 | 0 | 0 | 1 | 0 |
| run-05 | 41 | 40 | 801 of 820 | 19 | 0 | 0 | 1 | 0 |
| all 5 runs | 175 | 170 | 3328 of 3479 | 151 | 0 | 0 | 5 | 0 |
<!-- END study-citations -->

A stale anchor is a cited byte range that no longer matches the note (Neuron answered with an anchor into an earlier version). By note: `policy-error-response.md` 87 and `policy-edit-window.md` 64 across the five runs. All other cited bytes hashed to their `content_hash`, so no other kind of citation failure occurred. The close-out's recheck at the end of each run passes fewer citations than the record-time check (580 of 613 against 603 in run-01); the recheck was not broken down by cause. The hash check proves that cited bytes exist; whether they support the answer is the citation-support sample, which has no labels. The private-fact check found no candidate in any team answer in any run; a person has not reviewed that list because it is empty.

### What the runs say, and what they do not

- **Say:** with no rule source (A) the Builders wrote an edit endpoint that accepts every edit and a list endpoint with no cap of 50; with either notes in the prompt (B) or Neuron (C) every Builder put the 30 minute window and the 50 row cap into the code. A person is not needed for that: the executable check shows it.
- **Say:** on the edit window after the change, C passed the check in 4 of 5 runs and B in 2 of 5. The difference is the status code of a refused edit (a 4xx or a 5xx), not whether the window was enforced.
- **Say:** Neuron's answer to the neutral question gave the new value after each edit in every probe, with no supersede marker and without ever giving the replaced value in an `ask`. Whether it did so through supersession or through ranking the newer note first cannot be told from these results.
- **Do not say:** that Neuron keeps agents on the current rule better than notes in the prompt. The two arms differ on one product by 2 runs of 5, nine products are unlabeled, and the runs use one model and one app.
- **Not shown:** whether the Neuron arm would beat notes when the notes are too many to paste into a prompt (here there are 13 short notes), any effect on the Reviewer verdicts, tests and specs (they need labels), or anything on Linux.

Definition: [docs/METRIC.md](docs/METRIC.md). Label format: [labels/README.md](labels/README.md). Scorer: `python3 scripts/score_runs.py`. Tables: `python3 scripts/study_summary.py`.

## Where to Find Artifacts

| What | Where | Status |
| ---- | ----- | ------ |
| Every recorded ask | `demo-state/asks.jsonl` | Pilot, 36 asks |
| Neuron `explore` calls | `demo-state/explores.jsonl` | Pilot, 9 calls |
| Role transcripts | `demo-state/transcripts/` | Pilot, steps 2 to 9, redacted |
| Ingest times | `demo-state/ingest-times.jsonl` | Pilot |
| Scoreboard | `demo-state/closeout-result.json` | Pilot |
| Curation queue summary | `demo-state/curation-queue-team.json` | Pilot, after step 8 |
| Screenshots | `docs/images/` and `demo-state/screenshots/` | Pilot: Curation view, query with sources, vault list |
| The code the pilot's Builders wrote | `demo-state/pilot-builder-edits.patch` | Pilot |
| New runs (any arm) | `runs/<arm>/<run-id>/` | 15 runs, 5 per arm, 2026-10-29 |
| Hand labels | `labels/<arm>/<run-id>.json` | 15 empty sheets, none filled (model-labelled drafts are in `labels-model/`) |
| Negative boundary test | `runs/negative/neg-01/negative-result.json` | Run once, 2026-10-29 |
| What was verified, where and when | [docs/VERIFIED.md](docs/VERIFIED.md) | Written |
| Findings about Neuron | [docs/PRODUCT-OBSERVATIONS.md](docs/PRODUCT-OBSERVATIONS.md) | Written |

## Known Limits

- A 15,882 byte file took 297 seconds to ingest on one LAN server and 1,536 seconds on a local endpoint, according to Neuron's README. Notes here stay short and each step waits for ingest to finish.
- Neuron's document ids hash absolute paths, so the repo ships Markdown notes, recorded answers and screenshots, not a vault snapshot.
- One document over 65,536 characters fails on Neuron's default graph backend. Every note here is far smaller.
- A source's `path` points at Neuron's own copy of the note under `.marginalia/sources/` inside the vault, not at the file in `vault/`. The verifier reads that copy.
- The pilot's Gemini and Anthropic onboarding needed a different base URL from the one the presets offer, and its OpenRouter route printed a banner that broke the model-call helper. Those are findings reported by the author, not reproduced: [docs/PRODUCT-OBSERVATIONS.md](docs/PRODUCT-OBSERVATIONS.md), details in [docs/VERIFIED.md](docs/VERIFIED.md).
- The executable outcome check, the state probe, the isolated daemon scripts, the pinned installer, the scripted step 9 and the negative test were each run live on 2026-10-29 (`docs/VERIFIED.md`, "Live study"). Not run live: the integration workflow on GitHub, and anything on Linux or Windows.

## Checks

The fast workflow (`.github/workflows/validate.yml`, job "static checks and recorded-file validation") runs on every push: a compile check, the unit tests, `scripts/check_all.py` (personal-data scan, rule-value scan, README against the recorded files, starting state of the notes) and a dry run of all ten steps in all three arms. **It never starts Neuron, never runs a role and never calls a model. A green check there does not mean the demo ran.**

| Claim | Live test | Recorded artifact only |
| ----- | --------- | ---------------------- |
| Prompts, questions and agent files carry no rule value | Yes: `scripts/scan_rule_values.py` on every push | |
| README numbers match the recorded files | Yes: `scripts/check_readme.py` on every push | |
| No home path, working folder name or personal vault name in committed files | Yes: `scripts/scan_personal.py` on every push | |
| Roles reach no note or plan document | Checker is tested on synthetic and on pilot transcripts on every push | The 15 recorded runs (170 sessions) pass; a new run's transcripts are only checked when a run is made |
| The recorder survives the event shape that crashed it in the pilot | Yes: a real event is replayed in `tests/test_neuron_asks.py` | |
| Cited bytes hash to their `content_hash` | Yes, on a recorded fixture | The pilot's 638 and 616 |
| Neuron returns cited sources, reports `provider_error`, serves the current rule | | The pilot (one run) and the 5 Neuron-arm runs of 2026-10-29 |
| Steps 1 to 10 work on a pinned Neuron | **The opt-in `integration.yml` is written; it has never been started on GitHub** | Run by hand on macOS, 5 times, 2026-10-29 |

The workflows pin every GitHub Action to a full commit SHA, with the release in a trailing comment (`actions/checkout`, `setup-python`, `setup-node`, `upload-artifact`, `astral-sh/setup-uv`). On 2026-10-30 each SHA was resolved with `git ls-remote https://github.com/<owner>/<repo> refs/tags/<tag>` (peeled `^{}` commit where the tag is annotated), taking the newest release inside the major version previously used, and cross-checked against the moving major tag or a second tag ref pointing at the same commit. Update them deliberately; the major tags are not followed.

Run the unit tests yourself with `python3 -m unittest discover -s tests`. The tests cover all six `synthesis_status` values (`ok`, `no_llm`, `empty`, `provider_error`, `truncated`, `abnormal_stop`).

## Contributing & Licensing

To reproduce the demo or iterate on it: fork this repo, follow the Quickstart, and read [docs/METRIC.md](docs/METRIC.md) before you change anything the metric depends on.

**This repository's own code is MIT licensed, copyright OktoLabs AI** ([LICENSE](LICENSE)). The holder was decided by the owners; MIT was chosen to match the two sibling demo repositories, and the owners have not confirmed the licence type. It does not cover `app/` or Okto Neuron. The app under `app/` declares `"license": "MIT"` upstream, but the upstream repository publishes no `LICENSE` file or copyright line at the commit used, so no upstream notice could be copied here. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) says what is known and what is open.

### Okto Neuron licence

From 0.3.0, [Okto Neuron](https://github.com/OktoLabsAI/okto-neuron) is licensed under the Elastic License 2.0 with the Okto Labs SaaS, Competing Service, Internal Use, and Branding addendum. The addendum asks that the "Okto Neuron by Okto Labs" attribution stays visible in the UI and CLI; see `TRADEMARKS.md` in the Neuron repository. Releases up to and including 0.2.0 were published as `marginalia` under Apache 2.0, and that grant still applies to those releases. Third-party material is listed in `THIRD_PARTY_NOTICES.md` in the same repository.

## Conclusion

The question this repo asks is narrow: when rules change under a team of agents with no shared memory, do they follow the current rule, show where it came from, and say so honestly when the memory cannot answer. The pilot showed that the sources and the hash check worked and that the model outage was reported honestly, and on the rule changes it showed the opposite of what the plan hoped for, without being able to say why. The comparison now exists: five isolated runs per arm. On the two products that need no person, a rule source made every Builder use the current window and cap, and Neuron did not do better than the same notes pasted into the prompt by more than one check's status code and five runs can show. Neuron's answers gave the new value after each edit, carried no supersede marker, and 4.3% of their citations were stale anchors; its outage reporting was honest 5 times in 5. Whether Neuron helps with the products that need hand labels, or with more notes than fit in a prompt, is not known yet.

Built on Okto Neuron, an Okto Labs product. This repo records what happened and what a cleaner run should change.
