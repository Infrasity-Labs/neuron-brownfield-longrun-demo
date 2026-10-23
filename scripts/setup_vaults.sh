#!/usr/bin/env bash
# Step 1: onboard Neuron, create both vaults, register the watched folders, wait for ingest.
# Uses only commands the Neuron README documents. Reads settings from the environment, see .env.example.
# The API key is read from the variable named in DEMO_LLM_API_KEY_ENV and is never printed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VAULTS="${OKTO_NEURON_VAULTS_DIR:-$HOME/.okto-neuron/vaults}"

: "${DEMO_LLM_PROVIDER:?set DEMO_LLM_PROVIDER (see .env.example)}"
: "${DEMO_LLM_MODEL:?set DEMO_LLM_MODEL}"
: "${DEMO_LLM_API_KEY_ENV:?set DEMO_LLM_API_KEY_ENV, for example OKTO_NEURON_GEMINI_API_KEY}"
KEY_VALUE="${!DEMO_LLM_API_KEY_ENV:-}"
[ -n "$KEY_VALUE" ] || { echo "the variable $DEMO_LLM_API_KEY_ENV is empty"; exit 1; }

BASE_ARGS=()
[ -n "${DEMO_LLM_API_BASE:-}" ] && BASE_ARGS=(--api-base "$DEMO_LLM_API_BASE")

for vault in team reviewer-private; do
  okto-neuron onboard --non-interactive --reconfigure --vault "$vault" \
    --provider "$DEMO_LLM_PROVIDER" --model "$DEMO_LLM_MODEL" ${BASE_ARGS[@]+"${BASE_ARGS[@]}"} \
    --api-key-env "$DEMO_LLM_API_KEY_ENV" --api-key "$KEY_VALUE" --allow-remote-llm --yes
done

# The daemon reads ~/.okto-neuron/env only at start, so restart it after onboarding saved the key.
okto-neuron stop || true
OKTO_NEURON_NO_OPEN=1 okto-neuron serve --daemon --no-open

mkdir -p "$ROOT/vault-private"
okto-neuron watch-folder add "$ROOT/vault" --vault "$VAULTS/team"
okto-neuron watch-folder add "$ROOT/vault-private" --vault "$VAULTS/reviewer-private"

python3 "$ROOT/scripts/wait_ingest.py" --label "initial notes" --vault team --settle 5 --out "$ROOT/demo-state/ingest-times.jsonl"
