# Walkthrough

This explains what each step does and what to look at afterwards. Nothing here is a result. Results come from a real run and go in `demo-state/`.

Run one step with `python3 run_demo.py --steps N`. Print the prompts without running with `--dry-run`.

## Before step 1

1. Install Neuron with the command in its README.
2. Copy `.env.example` to `.env` and fill in the model settings and key. Load it with `set -a; source .env; set +a`.
3. Start the app database with `docker compose up -d`.

## Step 1: setup

`scripts/setup_vaults.sh` onboards Neuron for both vaults, restarts the daemon so it reads the saved key, registers `vault/` for the `team` vault and `vault-private/` for the `reviewer-private` vault, and waits for ingest. The folder is tied to the vault with `okto-neuron watch-folder add <folder> --vault <vault path>`.

Check: `okto-neuron watch-folder list --vault <path>` lists only that vault's folder.

## Steps 2 and 3: feature 1, comment editing

The Planner asks the team vault for the rules and writes `vault/specs/feature-1-comment-editing.md`. The Builder reads it, asks again, and writes the endpoint, the migration and the tests with the 15 minute window.

Check: the spec lists each rule with a source path and byte range, and the Builder's closing list names the same sources.

## Step 4: the window changes

The Maintainer edits `vault/policy-edit-window.md` to 30 minutes. The runner waits for ingest. A fresh Reviewer then asks which value is current and whether an older one was replaced.

Check: the Reviewer's answer says 30, and the Reviewer flags code that still uses 15. Whether Neuron marks 15 as replaced is what this step shows, so read the recorded answer.

## Step 5: the fix and the private finding

A fresh Builder fixes the window. The Reviewer approves and writes a private finding to `vault-private/`.

Check: `scripts/closeout.py` reports zero private notes in team answers.

## Step 6: feature 2, the article list limit

Planned, built and reviewed from the notes. The Reviewer also asks the private vault what it recorded earlier.

## Step 7: the error rule changes and a stale runbook appears

The Maintainer replaces `vault/policy-error-response.md` and adds `vault/ops-runbook.md`, which still describes the old shape. The two notes disagree.

Check: open the Curation view at `http://127.0.0.1:7777/` and take a screenshot of whatever Neuron shows, into `demo-state/screenshots/`. Then read how the next asks treat the two notes. The repo records what Neuron did, not what it was expected to do.

## Step 8: feature 3, soft delete

Built to the new error rule and reviewed against it. The Reviewer is told to say if a runbook still describes the replaced rule.

## Step 9: the model is unreachable

Stop the model endpoint by hand when the runner asks. Asks then return `provider_error`. The Reviewer must report that and fall back to `explore`.

Check: `closeout.py` lists each `provider_error` answer with the agent's next sentence, and flags any that claims nothing was found.

## Step 10: close-out

`python3 scripts/closeout.py --recheck` totals `demo-state/asks.jsonl` into `demo-state/closeout-result.json`. `--recheck` re-reads the cited bytes now as well as at record time. A later edit to a note changes the bytes Neuron holds, so older citations can fail the recheck and still have passed at record time.
