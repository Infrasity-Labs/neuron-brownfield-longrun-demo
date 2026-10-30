#!/usr/bin/env bash
# Install the pinned Okto Neuron release into the demo's own folder, without touching an install of your own.
#
# What it does:
#   1. reads the wheel URL, the SHA-256 and the version from pins.json;
#   2. downloads that wheel and refuses it unless its SHA-256 matches the pin;
#   3. installs it with `uv tool install --python 3.12` into $DEMO_NEURON_HOME/tool (UV_TOOL_DIR and UV_TOOL_BIN_DIR),
#      so your own `okto-neuron` and its uv tool environment stay as they are;
#   4. prints the version the new binary reports and fails if it differs from the pin.
#
# Why not `curl .../main/install.sh | bash`: `main` moves. And the installer at the v0.3.1 tag still bakes the 0.3.0 wheel as
# its default (checked in the public source on 2026-10-30), so a tag URL alone is not a pin either. The installer also starts
# a daemon on the default ports and registers an MCP server in your Claude Code configuration, which this demo must not do.
# The release page lists the wheel and its SHA-256: https://github.com/OktoLabsAI/okto-neuron/releases/tag/v0.3.1 .
# Installing "the exact wheel file or release URL" with uv is the path the public README describes for direct installs.
#
# Needs: uv, curl, python3 (any 3.9+). Status: run live on 2026-10-29 into a temporary DEMO_NEURON_HOME: 7 s, SHA-256 matched,
# okto-neuron 0.3.1 (docs/VERIFIED.md, "Live study").
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${DEMO_NEURON_HOME:-$ROOT/.demo-home}"
TOOL_DIR="$HOME_DIR/tool"

read -r URL SHA VERSION PYVER < <(python3 - "$ROOT/pins.json" <<'PY'
import json, sys
n = json.load(open(sys.argv[1]))["neuron"]
print(n["wheel_url"], n["wheel_sha256"], n["version"], n["python"])
PY
)

mkdir -p "$TOOL_DIR/download"
WHEEL="$TOOL_DIR/download/$(basename "$URL")"
curl -fsSL -o "$WHEEL" "$URL"
ACTUAL="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$WHEEL")"
if [ "$ACTUAL" != "$SHA" ]; then
  echo "checksum mismatch for $WHEEL: got $ACTUAL, pinned $SHA" >&2
  rm -f "$WHEEL"
  exit 1
fi

UV_TOOL_DIR="$TOOL_DIR/tools" UV_TOOL_BIN_DIR="$TOOL_DIR/bin" \
  uv tool install --force --python "$PYVER" "okto-neuron[serve,litellm] @ file://$WHEEL"

FOUND="$(HOME="$HOME_DIR" "$TOOL_DIR/bin/okto-neuron" --version | head -n 1)"
echo "$FOUND"
case "$FOUND" in
  *" $VERSION") echo "pinned version $VERSION installed in $TOOL_DIR" ;;
  *) echo "expected version $VERSION" >&2; exit 1 ;;
esac
echo "add to PATH for the demo scripts (they do it themselves): $TOOL_DIR/bin"
