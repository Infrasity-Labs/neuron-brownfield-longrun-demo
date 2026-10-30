# Neuron usage and where each piece is documented

Every Okto Neuron command, flag, variable and path this repository uses, with a pointer to the public documentation or
the label **undocumented in the README**. "Source" means the public source of okto-neuron 0.3.1
(`https://github.com/OktoLabsAI/okto-neuron`, tag `v0.3.1`), which was read on 2026-10-30. Nothing here was run against a
daemon: this file records what the documentation and the source say, not what a live daemon did.

README means the public README of okto-neuron (the repository's front page).

| What | Where used | Documented in the README? | Source and notes |
|---|---|---|---|
| `okto-neuron --version` | `scripts/neuron_ctl.py version`, `scripts/setup_vaults.sh` | Yes, as supported by the base wheel ("package imports, `--version`, command help") | `cli/__init__.py`: `click.version_option`, message `okto-neuron <version>` on the first line |
| Install the release wheel with `uv tool install` | `scripts/install_neuron.sh` | Yes: "Direct Python consumers install ... the exact wheel file or release URL" and the `uv tool install --python 3.12 "okto-neuron[serve,litellm]"` form | Wheel URL and SHA-256 are on the release page for v0.3.1 and in `pins.json`. The README's `curl .../main/install.sh \| bash` is not used: `main` moves, the installer starts a daemon on the default ports and registers an MCP server in your Claude Code configuration |
| `okto-neuron onboard --non-interactive --reconfigure --vault --provider --model --api-base --yes` | `scripts/setup_vaults.sh` | `onboard`, `--non-interactive`, `--reconfigure`, `--model` and `--provider` (example: `--provider local`) are described. `--vault`, `--api-base` and `--yes` are undocumented in the README | `cli/__init__.py` `onboard` options; `--yes` is "Accept remote-egress confirmations" |
| `--allow-remote-llm` | `scripts/setup_vaults.sh` | The README says non-loopback endpoints "require explicit remote-egress confirmation". The flag name is not in the README | Used by the pilot's recorded commands (`docs/VERIFIED.md`) |
| `--api-key-env NAME` and the key in the environment | `scripts/setup_vaults.sh` | Not in the README | Source: with `--non-interactive` and no `--api-key`, `onboard` reads the variable named by `--api-key-env` and saves it to `~/.okto-neuron/env`. The README only says API keys stay out of `okto-neuron.yaml` |
| `--api-key VALUE` | **not used any more** | Not in the README | Source help text: "API key to save into ~/.okto-neuron/env. Prefer the interactive prompt." The pilot passed the key this way, which puts it in the process list |
| `okto-neuron serve --daemon --no-open --port N --mcp-port M` | `scripts/neuron_ctl.py`, `scripts/setup_vaults.sh` | `serve`, `--daemon`, `--no-open` are in the README. `--port` and `--mcp-port` are undocumented in the README (it gives only the default ports 7777 and 8201) | `serve` options in `cli/__init__.py` |
| `okto-neuron stop`, `okto-neuron status` | `scripts/neuron_ctl.py`, `scripts/wait_ingest.py` | Yes (`status`, `stop` in "Use it") | The `Ingest: idle (... 0 processing, 0 queued)` line that `wait_ingest.py` matches is **undocumented in the README**; it is the pilot's observed output |
| `OKTO_NEURON_ENDPOINT` | `scripts/neuron_ctl.py` (`neuron_env`) | Undocumented in the README | `cli/_client.py`: precedence is the `--endpoint` flag, then this variable, then `http://127.0.0.1:7777` |
| `okto-neuron watch-folder add FOLDER --vault PATH` | `scripts/setup_vaults.sh` | `watch-folder add ./notes` is in the README. `--vault` takes a vault path: **undocumented in the README** | `cli/__init__.py`; the pilot recorded that `--vault` takes a path, not a name (`docs/VERIFIED.md`) |
| Isolated app home: a separate `HOME` | `scripts/neuron_ctl.py`, `scripts/setup_vaults.sh` | The README names `~/.okto-neuron` as the app home and `~/.okto-neuron/vaults/<name>` for vaults | `_compat.py`: `app_home()` is `Path.home() / ".okto-neuron"` |
| MCP bearer token at `~/.okto-neuron/daemon-<rest port>.token` | `run_demo.py`, `scripts/state_probe.py` | **Undocumented in the README.** It says MCP "requires the daemon bearer credential" and nothing more | `server/runtime.py`: `auth_token_path` returns `app_home() / f"daemon-{rest_port}.token"`. The installer defines `DAEMON_TOKEN_FILE="${HOME_ROOT}/daemon-7777.token"`. With the isolated REST port 17777 the file is `daemon-17777.token` |
| MCP at `http://127.0.0.1:<mcp port>/mcp`, `?vault=` pinning, `vault_override_ignored` | `run_demo.py` | Yes ("MCP tools") | |
| MCP tools `ask` (`include_sources`), `explore`, `list_vaults` | role runs, `scripts/state_probe.py` | Yes | |
| `synthesis_status`, `finish_reason` | `scripts/neuron_asks.py`, `scripts/closeout.py` | Yes ("Reading an `ask` response") | |
| `.okto-neuron-vault` file | repository root | Yes ("A project can pin its vault with a `.okto-neuron-vault` file") | The file is read by the agent, never by the server |
| Source `path` is vault-relative under `.marginalia/sources/<id>/` | `scripts/verify_citations.py` | The README says the path is vault-relative and absolute paths are not returned. The `.marginalia/sources/<id>/` layout is **undocumented in the README** | Observed in the pilot (`docs/VERIFIED.md`) |
| `okto-neuron init VAULT --wipe` | not used by the scripts; mentioned in `docs/VERIFIED.md` | Yes ("Start fresh") | |
| Okto Neuron licence | README | Yes ("License") | |

## Settings that are the demo's own, not Neuron's

`DEMO_NEURON_HOME`, `DEMO_NEURON_REST_PORT`, `DEMO_NEURON_MCP_PORT`, `DEMO_LLM_*`, `DEMO_WITH_DECOY`, `DEMO_INGEST_OUT`,
`DEMO_EVENTS`. They are read by the scripts in this repository only.

## Why the demo does not use your own daemon

The installer and a plain `okto-neuron serve` use ports 7777 and 8201 and the home `~/.okto-neuron`. A daemon shared with
other vaults is restarted by `okto-neuron stop`, and its vault names are visible to every role through `list_vaults`
(the pilot's personal vault was visible this way). The demo therefore runs a separate daemon with a separate `HOME` and
separate ports, and never calls `stop` or `onboard` against anything else.
