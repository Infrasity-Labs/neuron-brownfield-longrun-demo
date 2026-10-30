#!/usr/bin/env bash
# Step 1: reset the notes, check the pinned Neuron version, start an ISOLATED daemon, onboard both vaults, register the
# watched folders, wait for ingest.
#
# Isolation: every okto-neuron command here runs with a separate HOME (default <repo>/.demo-home) and the daemon uses
# non-default ports (REST 17777, MCP 18201). Neuron's app home is ~/.okto-neuron, so the demo's vaults, saved key,
# runtime files and token are all inside that folder. The script never reads, restarts or reconfigures a daemon or a vault
# of your own. docs/NEURON-USAGE.md lists each command and path with its source.
#
# The API key is NOT passed on the command line. It is taken from the environment variable named in DEMO_LLM_API_KEY_ENV;
# `okto-neuron onboard --non-interactive --api-key-env NAME` reads that variable and saves it for the daemon.
#
# Settings come from the environment, see .env.example. DEMO_WITH_DECOY=1 also creates a third vault, decoy, for the
# negative boundary test (scripts/negative_test.py).
#
# Status: run end to end live on 2026-10-29 in every Neuron-arm run and in the negative test (docs/VERIFIED.md, "Live study"); it
# needed DEMO_LLM_API_BASE=https://api.anthropic.com for the anthropic provider.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HOME="${DEMO_NEURON_HOME:-$ROOT/.demo-home}"
mkdir -p "$HOME"
REST_PORT="${DEMO_NEURON_REST_PORT:-17777}"
MCP_PORT="${DEMO_NEURON_MCP_PORT:-18201}"
export PATH="$HOME/tool/bin:$PATH"   # the pinned install from scripts/install_neuron.sh wins over one of your own
export OKTO_NEURON_ENDPOINT="http://127.0.0.1:${REST_PORT}"
export OKTO_NEURON_NO_OPEN=1
VAULTS="$HOME/.okto-neuron/vaults"
export OKTO_NEURON_VAULTS_DIR="$VAULTS"
INGEST_OUT="${DEMO_INGEST_OUT:-$ROOT/.demo-home/ingest-times.jsonl}"
EVENTS_ARGS=()
[ -n "${DEMO_EVENTS:-}" ] && EVENTS_ARGS=(--events "$DEMO_EVENTS")

: "${DEMO_LLM_PROVIDER:?set DEMO_LLM_PROVIDER (see .env.example)}"
: "${DEMO_LLM_MODEL:?set DEMO_LLM_MODEL}"
: "${DEMO_LLM_API_KEY_ENV:?set DEMO_LLM_API_KEY_ENV, for example OKTO_NEURON_ANTHROPIC_API_KEY}"
[ -n "${!DEMO_LLM_API_KEY_ENV:-}" ] || { echo "the variable $DEMO_LLM_API_KEY_ENV is empty"; exit 1; }

# 0. Starting state of the notes, then the pinned version. The check fails when the installed version differs.
python3 "$ROOT/scripts/reset.py"
python3 "$ROOT/scripts/neuron_ctl.py" version

BASE_ARGS=()
[ -n "${DEMO_LLM_API_BASE:-}" ] && BASE_ARGS=(--api-base "$DEMO_LLM_API_BASE")

VAULT_NAMES=(team reviewer-private)
[ "${DEMO_WITH_DECOY:-0}" = "1" ] && VAULT_NAMES+=(decoy)

for vault in "${VAULT_NAMES[@]}"; do
  okto-neuron onboard --non-interactive --reconfigure --vault "$vault" \
    --provider "$DEMO_LLM_PROVIDER" --model "$DEMO_LLM_MODEL" ${BASE_ARGS[@]+"${BASE_ARGS[@]}"} \
    --api-key-env "$DEMO_LLM_API_KEY_ENV" --allow-remote-llm --yes
done

# The daemon reads the saved key only at start, so (re)start the isolated daemon after onboarding.
okto-neuron stop || true
okto-neuron serve --daemon --no-open --port "$REST_PORT" --mcp-port "$MCP_PORT"

mkdir -p "$ROOT/vault-private"
okto-neuron watch-folder add "$ROOT/vault" --vault "$VAULTS/team"
okto-neuron watch-folder add "$ROOT/vault-private" --vault "$VAULTS/reviewer-private"
if [ "${DEMO_WITH_DECOY:-0}" = "1" ]; then
  okto-neuron watch-folder add "$ROOT/scenarios/decoy-notes" --vault "$VAULTS/decoy"
fi

mkdir -p "$(dirname "$INGEST_OUT")"
python3 "$ROOT/scripts/wait_ingest.py" --label "initial notes" --vault team --settle 5 --out "$INGEST_OUT" ${EVENTS_ARGS[@]+"${EVENTS_ARGS[@]}"} --event-label initial
