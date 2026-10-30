# Walkthrough

This explains what each step does and what to look at afterwards. It states no expected result: the only recorded results are the pilot's, in `demo-state/` (see [demo-state/README.md](../demo-state/README.md)), and no comparison run has been recorded under `runs/`. Where a step says "check", it names a file to read, not an outcome to expect.

Run one step with `python3 run_demo.py --steps N` (a partial run is marked as partial in its manifest). Print the prompts without running with `--dry-run`, and choose the arm with `--arm none|notes|neuron`.

## Before step 1

1. Run the offline checks: `python3 -m unittest discover -s tests` and `python3 scripts/check_all.py`.
2. Install the pinned Neuron into the demo's own folder with `bash scripts/install_neuron.sh`. The runner checks `okto-neuron --version` against `pins.json` at the start of every run.
3. Copy `.env.example` to `.env`, fill in the model settings and key, and load it with `set -a; source .env; set +a`.
4. For the executable outcome check, run `cd app && npm ci`. The app's database is not needed.

## Step 1: setup

The runner resets the notes (`scripts/reset.py`), then `scripts/setup_vaults.sh` starts an isolated daemon (separate `HOME`, ports 17777 and 18201), onboards both vaults, registers `vault/` for the `team` vault and `vault-private/` for the `reviewer-private` vault, and waits for ingest. The folder is tied to the vault with `okto-neuron watch-folder add <folder> --vault <vault path>`. Arms A and B need no daemon and skip this step apart from the reset.

Check: `okto-neuron watch-folder list --vault <path>` (with `OKTO_NEURON_ENDPOINT` pointing at the isolated daemon) lists only that vault's folder.

## Steps 2 and 3: feature 1, comment editing

The Planner gathers the rules from its rule source and writes `specs/feature-1-comment-editing.md` in its own directory. The runner copies the spec to the shared spec channel. The Builder gets the spec, gets the rules, and writes the endpoint, the migration and the tests.

Check: the spec names each rule and where it came from and carries no rule value (`scripts/scan_rule_values.py --specs`). After step 3 the runner runs the executable outcome check with the window that is current at that point.

## Step 4: the window changes

The Maintainer script copies `scenarios/step04/after/policy-edit-window.md` into `vault/` and records a `maintainer_edit` event. In arm C the runner waits for ingest, records an `ingest_complete` event, and `scripts/state_probe.py` asks Neuron a neutral question and an `explore` and stores both raw results. Only then does a fresh Reviewer run.

Check: `runs/<arm>/<run-id>/events.jsonl` for the order of edit, ingest, probe and first ask, and `probes/step4.summary.json` for what Neuron said about its own state.

## Step 5: the current rule and the private finding

A fresh Builder checks the code against the rules as they now stand. A Reviewer reviews it and writes one private finding to `private-out/`, which the runner copies to `vault-private/`.

Check: `diffs/step5.diff` and `code-outcome/step5.json`, and, in arm C, that `closeout-result.json` lists no private note in a team answer.

## Step 6: feature 2, the article list limit

Planned, built and reviewed from the rule source and the code. The Reviewer also asks for what it recorded in earlier reviews.

## Step 7: the error rule changes and a stale runbook appears

The Maintainer script copies `scenarios/step07/after/` into `vault/`: a replaced error rule and `ops-runbook.md`, which still describes the old shape. The two notes disagree.

Check: in arm C, open the Curation view of the isolated daemon (`http://127.0.0.1:17777/`) and take a screenshot of whatever Neuron shows, into the run folder. Then read how the next asks treat the two notes. The repository records what Neuron did.

## Step 8: feature 3, soft delete

Planned, built and reviewed. The prompts ask the roles to report any disagreement between two sources about a rule, in every arm.

## Step 9: the model is unreachable (arm C only)

The script restarts the isolated daemon with an invalid model key, the Reviewer asks, and the daemon is restored in a `finally` block, so a crash or Ctrl-C still brings a working daemon back. Asks then return `provider_error`.

Check: `closeout.py` lists each `provider_error` answer with the agent's next sentence and flags any that claims nothing was found.

## Step 10: close-out

The runner reads every transcript with `scripts/check_transcripts.py`, scans the recorded questions for rule values, checks the order of events, and in arm C runs `scripts/closeout.py --recheck`, which totals `asks.jsonl` into `closeout-result.json` and re-reads the cited bytes now as well as at record time. A later edit to a note changes the bytes Neuron holds, so older citations can fail the recheck and still have passed at record time.

## After the runs

Create label sheets with `scripts/make_label_sheet.py`, have a named person fill them in (`labels/README.md`), then `python3 scripts/score_runs.py`.
