# Okto Neuron Use Case Repo: Fleet Plan

> **Read this first.** This is the original planning document, written before the pilot run. It states expected outcomes in several places (for example steps 4 and 5 in section 6: "gets 30, sees 15 marked replaced"). Those are plans, not results. What happened is in README.md and `demo-state/`, and where they disagree with this file they win. Roles no longer run in a directory that contains this file (the pilot's did, and one Grep result returned it). Superseded decisions are marked in section 11. The experiment design that replaced this plan's single arm is `docs/METRIC.md`.

Repo name: neuron-brownfield-longrun-demo. Tagline: "Three agents. Two vaults. Every answer shows its source."

## 1. What Okto Neuron is

Neuron is local-first memory for AI agents, built as a knowledge graph. You keep notes as Markdown files, Neuron chunks them and extracts claims with an LLM you configure, and serves them back through a CLI, an MCP server, a Python SDK, and a web UI (the README also lists a REST API).

The Markdown vault is the trust root, and the graph is derived from it and can always be rebuilt.

The atomic unit is a Claim: one subject, predicate, object assertion anchored to its source block, the extractor activity, and the responsible agent.

Neuron is on a 0.x release line, and versions up to 0.2.0 were published as prereleases under the name Marginalia.

## 2. What it does and where the repo shows it

| Feature | What it does | Where the repo shows it |
|---|---|---|
| Claims with provenance; ask with include_sources | Returns the block_id, byte range, content_hash and vault-relative path for every source; content_hash is sha256(raw[byte_start:byte_end]) | Every step an agent asks; a script re-reads the cited bytes and checks the hash |
| Supersession on edit | A judge LLM confirms a genuine correction, the old claim is filtered from recall, and a supersedes edge links new to old | Steps 4 and 7 |
| Curation view | A review queue for predicate folds, entity merges and node candidates | Step 7, when an old runbook disagrees with a new rule |
| Multiple vaults | ask, explore and remember each accept a per-call vault name, and list_vaults returns names only | Reviewer's private vault; a script checks its notes never appear in the team vault's answers |
| synthesis_status, explore | Every ask reports ok or degraded, and provider_error means the model was unreachable; explore() walks the graph with no LLM | Step 9, when the model is down |
| Vault pinning and folder watcher | A .okto-neuron-vault file names the project's vault and is read by the agent; a folder watcher keeps a vault in sync as files change | Step 1: setup and every later note edit |

## 3. Why we picked these features

They answer problems developers already have. An agent in an existing codebase can follow a stale rule, give an answer nobody can check, or fail without saying so. Supersession, provenance, and synthesis_status map onto those three, and Neuron's own guidance for provider_error is never to report "I couldn't find anything" on it.

Each one has a visible result. A source line, a supersedes edge, a Curation entry, and a status field all show up in a screenshot and can be checked by a script.

They are what Neuron leads with. Its README describes the product as memory "with cited sources and an MCP server" and lists "living memory" and "provenance you can trust" as headline features, so the repo tests those first.

Left out on purpose:

- Remember: live in a session. A measured ingest took minutes, and Claude Code aborts a tool call after 300 seconds, so notes enter through the folder watcher.
- Subgraph answers. Neuron keeps source-block synthesis as the default because it scored higher on its own evaluation set, and its retrieval ADR treats the older single-run figures as indicative.
- Benchmark numbers. The LoCoMo run was made on development builds, and the page says these are not release quality numbers.

## 4. The scenario in one paragraph

A small team ships three features to an existing blogging app in ten steps. Three Claude Code sessions do the work, and none remember the others, so every rule they follow comes from Neuron. Along the way, the Maintainer (the person running the repo) changes two rules and drops in an old document that still states the previous rule. The agents follow the current rule, show where it came from, and say so plainly when Neuron cannot answer.

The app is a fresh fork of gothinkster/node-express-realworld-example-app (Node, Express, Prisma, Postgres), the same upstream the Nexus demo uses.

## 5. The cast

| Who | Does | Vault used |
|---|---|---|
| Planner (session) | Reads the rules and writes a short task spec into the vault for each feature | team |
| Builder (session) | Writes the migration, endpoint, and tests from the spec and the rules | team |
| Reviewer (session) | Checks each diff against the current rules, cites the source, keeps private findings | team and reviewer-private |
| Maintainer (you) | Edits two rules and adds the old runbook | Edits vault/ |

Neuron runs one daemon per project on the machine with bearer-authenticated tools, so roles are separated by task and by fresh sessions. The vault split shows scoped answers.

## 6. The ten steps

| Step | What happens | Shows |
|---|---|---|
| 1 | Install Neuron, create both vaults, load 14 notes through the folder watcher | Setup, pinning |
| 2 | Planner asks the rules for feature 1 (comment editing) and writes the spec | Answers with sources |
| 3 | Builder adds PUT /api/articles/:slug/comments/:id and an editedAt migration, using a 15-minute edit window | Agent working from cited rules |
| 4 | Maintainer changes the edit window to 30 minutes. A fresh Reviewer asks, gets 30, sees 15 marked replaced, and flags the code | Supersession |
| 5 | A fresh Builder fixes the window; Reviewer approves and logs a private finding | Vaults |
| 6 | Feature 2, a cap on the article list limit, planned, built, and reviewed from the notes | Recall across fresh sessions |
| 7 | Maintainer replaces the error response rule and adds ops-runbook.md, which still describes the old one | Conflict across files, Curation |
| 8 | Feature 3, soft delete for comments, built to the new error rule and reviewed against it | Current rule wins, with proof |
| 9 | Model endpoint stopped; every ask returns provider_error, agents report it and fall back to explore | Honest failure |
| 10 | Close-out script totals the run and verifies every citation from steps 2 to 8 | Scoreboard |

run_demo.py replays any set of steps (--steps 4 7 9, --start, --dry-run). A dry run prints every prompt and needs no Neuron.

## 7. The 14 notes

- Eight read from the fork's code, so each can be checked against a file: auth header, migrations, error shape, comment ownership, test layout, and three more written the same way.
- Six demo policies, labeled as such: edit window (15 then 30), editedAt marker, article list limit cap, error response rule (replaced in step 7), soft delete rule, and release checklist.
- One added in step 7: ops-runbook.md, which still describes the old error response.

In step 7, the repo records whatever Neuron does with the runbook, either retiring the old claim or holding it in the Curation view, and shows the result in a screenshot.

## 8. The scoreboard

demo-state/closeout-result.json is built from every recorded ask in demo-state/asks.jsonl:

- questions asked, and how many returned sources
- citations that passed the hash check
- claims replaced, and any stale rule an agent still followed after replacement
- answers marked provider_error and how each agent handled them
- private notes that appeared in the team vault (the target is zero)
- ingest time per note

The README prints these numbers from the real run and nothing else.

## 9. Repo layout and automated checks

Layout: app/, vault/, demo-state/ (recorded answers, close-out file, screenshots), docs/ (walkthrough, one prompt per role per step, VERIFIED.md, hero and architecture SVGs), agents/ (a CLAUDE.md per role and one shared skill file), scripts/, tests/, .github/workflows/validate.yml, run_demo.py, plus the vault pin, MCP and env examples and docker-compose.yml.

The README follows the Nexus and Pulse order: banner, About, The Problem, How It Works, Neuron in Action, Architecture, Repository Structure, Prerequisites, Quickstart, the ten steps, Where to Find Artifacts, Conclusion.

Checks on every push: unit tests for the citation verifier on recorded answers, a test that every recorded ask carries a synthesis_status, link and JSON checks, a compile check, and a dry run of all ten steps. docs/VERIFIED.md states the Neuron version and date the commands were verified.

## 10. Limits the Neuron README states up front

- A 15,882-byte file took 297 seconds to ingest on a LAN inference server and 1,536 seconds on a local endpoint, so notes stay small, each step's script waits for ingest to finish, and the repo ships the finished run.
- Document IDs hash absolute paths, so the repo ships Markdown notes, recorded answers and screenshots, and adds a vault snapshot only if it opens from any folder.
- A single document over 65,536 characters fails on the default Grafx backend, so every note stays far below that.
- Neuron's README says its install was rehearsed on Linux, and no published version has passed a Windows PowerShell lifecycle. This run was done on macOS arm64, so the repo says exactly that and claims nothing about Linux or Windows.

## 11. Decisions from setup (2026-10-19)

- (Superseded 2026-10-30.) No Neuron version appears in README text. The installed version and date are recorded only in docs/VERIFIED.md. Now the README names the pinned version 0.3.1, `pins.json` holds the release URL and SHA-256, and every run records its versions in `run-manifest.json`.
- The verifier and scoreboard handle all six synthesis_status values: ok, no_llm, empty, provider_error, truncated, abnormal_stop. Any finish_reason other than stop is counted separately as suspect.
- The ask wrapper checks every response for vault_override_ignored and records it in asks.jsonl.
- This run is on macOS arm64. The README states what was verified and where, and does not claim Linux.
- Each role runs with `claude -p --strict-mcp-config --mcp-config <file>` (the flag exists in claude 2.1.303), so a role only sees the MCP config run_demo.py gives it and not the user-scope okto-neuron entry.
- Scripts must run on Python 3.9 (macOS system Python): no match statements, no `X | Y` type unions at runtime, and `from __future__ import annotations` where needed.
- Ingest is serial. Concurrency and batch settings change only if the Neuron README documents them, and any change is recorded in docs/VERIFIED.md. Notes stay short.
- vault-private/ stays in .gitignore. The private note's text is shipped in docs/ as a labelled example.

Sources: Neuron decision recall walkthrough, Pulse demo, Nexus demo, RealWorld Node app.
