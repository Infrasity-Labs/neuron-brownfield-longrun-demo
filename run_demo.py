#!/usr/bin/env python3
"""Replay the ten steps of the demo in one of three arms, in isolation, and record everything checkable.

  python3 run_demo.py --dry-run                      print every prompt for the neuron arm, needs no Neuron
  python3 run_demo.py --dry-run --arm notes          print the same prompts with the notes pasted in
  python3 run_demo.py --reset                        put the notes and the private folder back to the starting state
  python3 run_demo.py --arm neuron --run-id run-01   one full run of arm C (Neuron), steps 1 to 10
  python3 run_demo.py --arm none --runs 5            five runs of arm A, run-01 to run-05
  python3 run_demo.py --arm neuron --steps 4 7       only some steps (a partial run is marked as such in its manifest)
  python3 run_demo.py --negative                     the negative boundary tests (needs a Neuron daemon with a decoy vault)

Arms (docs/METRIC.md): none = no memory, notes = the current notes pasted into each prompt, neuron = Okto Neuron.
Prompts, fixed questions, model, turn limit and tool limits are identical in every arm.

Every role is a fresh `claude -p` session in its own temporary working directory (scripts/build_workdir.py) that holds
only app/, the spec channel and the Reviewer's private-out/ folder. Notes, the plan, the docs and the recorded results are
not in it. After each role the isolation checker reads its transcript. A run writes runs/<arm>/<run-id>/:

  run-manifest.json   versions, settings, metric fingerprint, per-session facts, check results
  events.jsonl        UTC timeline: edits, ingest complete, state probes, asks, role start and end
  transcripts/        one stream-json transcript per role session
  asks.jsonl, explores.jsonl, ingest-times.jsonl, closeout-result.json   (arm neuron)
  probes/             the neutral state probe after each edit (arm neuron)
  code-outcome/       the executable outcome checks on the Builder's code
  diffs/              git diff of the code after each Builder step

Neuron runs in an isolated daemon (separate HOME and ports, scripts/neuron_ctl.py), never the user's own.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import build_workdir  # noqa: E402
import check_transcripts  # noqa: E402
import code_outcome  # noqa: E402
import events as event_log  # noqa: E402
import maintainer_edit  # noqa: E402
import manifest as manifest_mod  # noqa: E402
import neuron_ctl  # noqa: E402
import prompts  # noqa: E402
import reset as reset_mod  # noqa: E402
import scan_rule_values  # noqa: E402
import steps as step_table  # noqa: E402

VAULT_DIR = os.path.join(REPO, "vault")
PRIVATE_DIR = os.path.join(REPO, "vault-private")
EDIT_WINDOW_AT_STEP = {3: 15, 5: 30, 6: 30, 8: 30}


def mcp_url() -> str:
    return os.environ.get("OKTO_NEURON_MCP_URL") or neuron_ctl.mcp_url()


def token_file() -> str:
    return os.environ.get("OKTO_NEURON_TOKEN_FILE") or neuron_ctl.token_file()


def role_url(role: str) -> str:
    query = step_table.ROLES[role]["mcp_vault_query"]
    return mcp_url() + ("?vault=" + query if query else "")


def write_mcp_config(role: str, arm: str, directory: str) -> str:
    """Write the per-role MCP config. Arm C gets the daemon token (read here, never printed); the others get no server."""
    config: dict = {"mcpServers": {}}
    if step_table.ARMS[arm]["neuron"]:
        with open(token_file()) as handle:
            token = handle.read().strip()
        config["mcpServers"]["okto-neuron"] = {"type": "http", "url": role_url(role),
                                               "headers": {"Authorization": "Bearer " + token}}
    path = os.path.join(directory, "mcp-%s.json" % role)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(config, handle)
    return path


def claude_command(role: str, arm: str, prompt: str, mcp_config: str, max_turns: int, model: Optional[str],
                   bare: bool) -> List[str]:
    spec = step_table.ROLES[role]
    model_args = ["--model", model] if model else []
    return (["claude", "-p", prompt] + model_args + [
        "--strict-mcp-config", "--mcp-config", mcp_config,
        # No user or local settings: no hooks, no personal allow rules. The role's directory has no project settings.
        "--setting-sources", "project",
        "--append-system-prompt", prompts.build_system_prompt(arm, role),
        "--permission-mode", "acceptEdits",
        "--output-format", "stream-json", "--verbose",
        "--max-turns", str(max_turns),
        "--tools", ",".join(spec["builtin_tools"]),
    ] + (["--bare"] if bare else []) + ["--allowedTools"] + step_table.allowed_tools(role, arm))


def dry_run_step(step: dict, arm: str) -> None:
    print("=" * 78)
    print("STEP %d  %s" % (step["id"], step["title"]))
    print("=" * 78)
    if step.get("neuron_only") and not step_table.ARMS[arm]["neuron"]:
        print("[skipped in arm %s: this step needs a Neuron daemon]\n" % arm)
        return
    if step["kind"] == "setup":
        if step_table.ARMS[arm]["neuron"]:
            print("[maintainer] python3 scripts/reset.py, then bash scripts/setup_vaults.sh   (pinned install check, isolated daemon, onboard, vaults, watched folders, wait for ingest)")
        else:
            print("[maintainer] python3 scripts/reset.py   (arm %s needs no Neuron)" % arm)
    if step.get("maintainer"):
        if step["maintainer"] == "step9":
            print("[maintainer] scripted outage: restart the isolated daemon with an invalid key, run the role, restore the daemon in a finally block")
        else:
            extra = ", then python3 scripts/wait_ingest.py and python3 scripts/state_probe.py" if step_table.ARMS[arm]["neuron"] else ""
            print("[maintainer] python3 scripts/maintainer_edit.py %s%s" % (step["maintainer"], extra))
    for role, prompt_path in step["runs"]:
        spec = step_table.ROLES[role]
        print("\n--- role: %s | prompt: %s | arm: %s (%s)" % (role, prompt_path, arm, step_table.ARMS[arm]["memory"]))
        if step_table.ARMS[arm]["neuron"]:
            print("MCP url       : %s" % role_url(role))
        print("working dir   : a clean temporary directory with only %s" % ", ".join(
            sorted(build_workdir.ALLOWED_TOP[role] - {".gitignore"})))
        print("builtin tools : %s" % ", ".join(spec["builtin_tools"]))
        print("allowed tools : %s" % ", ".join(step_table.allowed_tools(role, arm)))
        print("system prompt : %s" % " + ".join(
            [spec["claude_md"], step_table.COMMON_MD] + ([spec["neuron_md"], step_table.NEURON_SKILL_MD] if step_table.ARMS[arm]["neuron"] else [])))
        print("prompt:")
        text = prompts.build_prompt(arm, prompt_path, VAULT_DIR, PRIVATE_DIR)
        print("\n".join("    " + line for line in text.strip().splitlines()))
    if step["kind"] == "closeout":
        print("[script] scripts/closeout.py (arm neuron), scripts/check_transcripts.py, scripts/scan_rule_values.py, event order check, manifest")
    print()


class Run:
    """One run of one arm: its directory, its canonical tree, its events and its manifest."""

    def __init__(self, arm: str, run_id: str, args: argparse.Namespace, partial: bool) -> None:
        self.arm = arm
        self.run_id = run_id
        self.args = args
        self.neuron = step_table.ARMS[arm]["neuron"]
        self.dir = os.path.join(args.runs_dir, arm, run_id)
        self.events = os.path.join(self.dir, "events.jsonl")
        self.asks = os.path.join(self.dir, "asks.jsonl")
        self.explores = os.path.join(self.dir, "explores.jsonl")
        self.ingest = os.path.join(self.dir, "ingest-times.jsonl")
        self.transcripts = os.path.join(self.dir, "transcripts")
        self.canonical = tempfile.mkdtemp(prefix="neuron-demo-canonical-")
        self.tmp = tempfile.mkdtemp(prefix="neuron-demo-mcp-")
        self.partial = partial
        self.hard_failures: List[str] = []
        self.outcome_failures: List[str] = []
        self.manifest: dict = {}

    # ---- helpers -------------------------------------------------------------------------------------------------

    def script(self, name: str, *argv: str) -> int:
        env = neuron_ctl.neuron_env() if self.neuron else None
        return subprocess.call([sys.executable, os.path.join(REPO, "scripts", name)] + list(argv), cwd=REPO, env=env)

    def fail(self, message: str) -> None:
        print("FAILED CHECK: " + message)
        self.hard_failures.append(message)

    # ---- lifecycle -----------------------------------------------------------------------------------------------

    def start(self) -> None:
        if os.path.exists(self.dir):
            raise SystemExit("%s already exists. A recorded run is never overwritten: pick another --run-id." % self.dir)
        os.makedirs(self.transcripts)
        neuron_version = None
        if self.neuron:
            # HOME stays the real one here: the claude CLI keeps its login there. Only the okto-neuron commands and the
            # scripts that read the isolated vaults get the isolated HOME, through neuron_ctl.neuron_env().
            os.environ.update({k: v for k, v in neuron_ctl.neuron_env().items() if k.startswith("OKTO_NEURON_")})
            if self.args.skip_version_check:
                neuron_version = neuron_ctl.installed_version()
            else:
                neuron_version = neuron_ctl.require_version(neuron_ctl.load_pins()["neuron"]["version"])
        # Reset BEFORE the manifest is made: the manifest fingerprints vault/, and the second run of a series would otherwise
        # fingerprint the notes the first run left edited (found in the live study: runs 2 to 5 of two arms got another hash).
        reset_mod.reset()
        flags = {"bare": bool(self.args.bare), "setting_sources": "project", "permission_mode": "acceptEdits",
                 "partial_run": self.partial}
        self.manifest = manifest_mod.collect(self.arm, self.run_id, self.args.model, self.args.max_turns, flags, neuron_version)
        pinned = self.manifest["versions"]["claude_cli_pinned"]
        found = self.manifest["versions"]["claude_cli"]
        if found and found != pinned:
            print("note: claude CLI is %s, the pin is %s (recorded in the manifest)" % (found, pinned))
        manifest_mod.write(os.path.join(self.dir, "run-manifest.json"), self.manifest)
        build_workdir.init_canonical(self.canonical)
        event_log.log_event(self.events, "run_start", arm=self.arm, run_id=self.run_id)
        self.baseline_outcome()

    def baseline_outcome(self) -> None:
        """Run the outcome check on the untouched app before any role runs.

        On the starting app, accepts-inside and caps-above fail (no edit endpoint, no cap yet). Every outcome must be
        "pass" or "fail", never "error": "error" means the suite did not run (missing dependencies, a Node version the
        app does not support), and the whole run's executable scores would be silently left out. This catches that
        before the first model call.
        """
        try:
            record = code_outcome.run(self.canonical, self.dir, "baseline", 15)
        except RuntimeError as error:
            self.manifest["checks"]["code_outcome_baseline"] = "not run: %s" % error
            if self.args.require_outcome:
                self.fail("outcome check could not run on the starting app: %s" % error)
            return
        self.manifest["checks"]["code_outcome_baseline"] = record["outcomes"]
        errored = sorted(k for k, v in record["outcomes"].items() if v == "error")
        if errored:
            raise SystemExit("outcome check does not run on the starting app (%s); nothing was spent on a model. See "
                             "%s/code-outcome/baseline.json, remove %s and fix the environment" % (", ".join(errored), self.dir, self.dir))

    def finish(self) -> int:
        self.closeout()
        self.manifest["finished_at"] = event_log.utc_now()
        self.manifest["checks"]["hard_failures"] = self.hard_failures
        self.manifest["checks"]["outcome_failures"] = self.outcome_failures
        event_log.log_event(self.events, "run_end", hard_failures=len(self.hard_failures))
        manifest_mod.write(os.path.join(self.dir, "run-manifest.json"), self.manifest)
        shutil.rmtree(self.canonical, ignore_errors=True)
        shutil.rmtree(self.tmp, ignore_errors=True)
        if self.hard_failures:
            return 1
        if self.outcome_failures and self.args.fail_on_outcome:
            return 1
        return 0

    # ---- steps ---------------------------------------------------------------------------------------------------

    def run_step(self, step: dict) -> int:
        print("\nSTEP %d: %s" % (step["id"], step["title"]))
        if step.get("neuron_only") and not self.neuron:
            print("skipped: needs a Neuron daemon")
            return 0
        if step["kind"] == "setup":
            if self.neuron:
                neuron_ctl.reset_state()  # every run starts on an empty graph, never on the previous run's vaults
                return subprocess.call(["bash", os.path.join(REPO, "scripts", "setup_vaults.sh")], cwd=REPO,
                                       env=neuron_ctl.neuron_env({"DEMO_INGEST_OUT": self.ingest, "DEMO_EVENTS": self.events}))
            return 0
        if step["kind"] == "closeout":
            return 0  # finish() does the close-out, so that it also runs after a partial or failed run
        action = step.get("maintainer")
        if action in ("step4", "step7"):
            self.maintainer_edit(step, action)
        if action == "step9":
            with neuron_ctl.outage(os.environ.get("DEMO_LLM_API_KEY_ENV", "OKTO_NEURON_LLM_API_KEY"), self.events):
                return self.run_roles(step)
        return self.run_roles(step)

    def maintainer_edit(self, step: dict, action: str) -> None:
        counts = neuron_ctl.ingest_counts() if self.neuron else None  # read before the edit, see scripts/wait_ingest.py
        written = maintainer_edit.edit(action, VAULT_DIR, maintainer_edit.SCENARIOS, self.events)
        if not self.neuron:
            return
        code = self.script("wait_ingest.py", "--label", "step %d edit" % step["id"], "--vault", step_table.TEAM_VAULT, "--settle", "8",
                           "--out", self.ingest, "--events", self.events, "--event-label", action,
                           *self.queue_args(counts, len(written)))
        if code != 0:
            raise SystemExit("ingest did not finish after %s" % action)
        rule = "edit-window" if action == "step4" else "error-response"
        code = self.script("state_probe.py", "--rule", rule, "--label", action, "--step", str(step["id"]),
                           "--run-dir", self.dir, "--events", self.events)
        if code != 0:
            self.fail("state probe after %s did not complete" % action)

    @staticmethod
    def queue_args(counts: Optional[tuple], new_files: int) -> List[str]:
        return ["--after-total", str(counts[1]), "--min-new", str(new_files)] if counts and new_files else []

    def run_roles(self, step: dict) -> int:
        vault_before = _snapshot(VAULT_DIR, PRIVATE_DIR)
        counts = neuron_ctl.ingest_counts() if self.neuron else None
        for role, prompt_path in step["runs"]:
            code = self.run_role(step, role, prompt_path)
            if code != 0:
                return code
        if self.neuron and step["runs"]:
            after = _snapshot(VAULT_DIR, PRIVATE_DIR)
            changed = [path for path in after if vault_before.get(path) != after[path]]
            if changed:
                # A role wrote a private finding into a watched folder, so wait for it to be ingested.
                return self.script("wait_ingest.py", "--label", "after step %d" % step["id"], "--vault", step_table.TEAM_VAULT,
                                   "--settle", "8", "--out", self.ingest, "--events", self.events,
                                   "--event-label", "after-step-%d" % step["id"], *self.queue_args(counts, len(changed)))
        return 0

    def run_role(self, step: dict, role: str, prompt_path: str) -> int:
        number = step["id"]
        name = "step%02d-%s" % (number, role)
        transcript = os.path.join(self.transcripts, name + ".jsonl")
        workdir = tempfile.mkdtemp(prefix="neuron-demo-%s-" % role)
        try:
            info = build_workdir.build_role_dir(role, self.canonical, os.path.join(workdir, "w"))
            wd = info["dest"]
            os.makedirs(os.path.join(self.dir, "workdir-manifests"), exist_ok=True)
            with open(os.path.join(self.dir, "workdir-manifests", name + ".json"), "w") as handle:
                json.dump(info["files"], handle, indent=1)
            prompt = prompts.build_prompt(self.arm, prompt_path, VAULT_DIR, PRIVATE_DIR)
            config = write_mcp_config(role, self.arm, self.tmp)
            command = claude_command(role, self.arm, prompt, config, self.args.max_turns, self.args.model, self.args.bare)
            print("running %s ..." % role)
            event_log.log_event(self.events, "role_start", step=number, role=role, transcript="transcripts/%s.jsonl" % name,
                                visible_files=len(info["files"]))
            with open(transcript, "w") as out:
                code = subprocess.call(command, cwd=wd, stdout=out)
            event_log.log_event(self.events, "role_end", step=number, role=role, exit_code=code)
            if code != 0:
                print("claude exited with %d, see %s" % (code, transcript))
                self.fail("claude exited with %d at step %d %s" % (code, number, role))
                return code
            collected = build_workdir.collect(role, wd, self.canonical, PRIVATE_DIR if role == "reviewer" else None)
            session = manifest_mod.session_versions(transcript)
            session.update({"step": number, "role": role, "transcript": "transcripts/%s.jsonl" % name,
                            "visible_files": len(info["files"]), "collected": {k: v for k, v in collected.items() if v}})
            self.manifest["sessions"].append(session)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        if self.neuron:
            asks_args = [transcript, "--step", str(number), "--role", role, "--out", self.asks, "--explores-out", self.explores,
                         "--events", self.events, "--vault-root", "%s=%s" % (step_table.TEAM_VAULT, os.path.join(neuron_ctl.vaults_dir(), step_table.TEAM_VAULT)),
                         "--vault-root", "%s=%s" % (step_table.PRIVATE_VAULT, os.path.join(neuron_ctl.vaults_dir(), step_table.PRIVATE_VAULT))]
            self.script("neuron_asks.py", *asks_args)
        report = check_transcripts.check_transcript(transcript)
        if report["violations"]:
            self.fail("isolation: %s %s reached %d forbidden path(s)" % (name, role, len(report["violations"])))
        if role == "planner":
            self.check_spec(step)
        if role == "builder":
            self.after_builder(step)
        return 0

    def check_spec(self, step: dict) -> None:
        """Record which rule values the Planner copied into a spec (the one-hop channel to the Builder).

        This is a measurement, not a failure: in every arm a Planner may write a field name such as deletedAt into its spec
        (in the no-memory arm it invents one). The hits are kept per run in checks.spec_rule_values so the report can state
        how often each arm's specs carried a value. Each spec is scanned once, in the step that wrote it.
        """
        hits = scan_rule_values.scan(specs=os.path.join(self.canonical, "specs"))
        seen = self.manifest["checks"].setdefault("spec_rule_values", [])
        known = {(h["spec"], h["rule"]) for h in seen}
        for hit in hits:
            if (hit["where"], hit["rule"]) not in known:
                known.add((hit["where"], hit["rule"]))
                seen.append({"step": step["id"], "spec": hit["where"], "rule": hit["rule"], "match": hit["match"]})

    def after_builder(self, step: dict) -> None:
        number = step["id"]
        os.makedirs(os.path.join(self.dir, "diffs"), exist_ok=True)
        diff = subprocess.run(["git", "-C", self.canonical, "diff", "--", "app"], capture_output=True, text=True).stdout
        with open(os.path.join(self.dir, "diffs", "step%d.diff" % number), "w") as handle:
            handle.write(diff)
        window = EDIT_WINDOW_AT_STEP.get(number)
        if window is None:
            return
        try:
            record = code_outcome.run(self.canonical, self.dir, "step%d" % number, window)
        except RuntimeError as error:
            self.manifest["checks"]["code_outcome_step%d" % number] = "not run: %s" % error
            if self.args.require_outcome:
                self.fail("outcome check could not run: %s" % error)
            return
        self.manifest["checks"]["code_outcome_step%d" % number] = record["outcomes"]
        wanted = ["edit-window/accepts-inside", "edit-window/refuses-outside"] if number in (3, 5) else []
        if number == 6:
            wanted = ["article-limit/caps-above", "article-limit/keeps-below", "article-limit/keeps-default"]
        for outcome in wanted:
            if record["outcomes"].get(outcome) != "pass":
                self.outcome_failures.append("step %d: %s is %s" % (number, outcome, record["outcomes"].get(outcome)))

    def closeout(self) -> None:
        reports = [check_transcripts.check_transcript(os.path.join(self.transcripts, n))
                   for n in sorted(os.listdir(self.transcripts))] if os.path.isdir(self.transcripts) else []
        self.manifest["checks"]["isolation"] = {
            "transcripts": len(reports), "violations": sum(len(r["violations"]) for r in reports),
            "blocked_attempts": sum(len(r["blocked"]) for r in reports)}
        if not self.neuron:
            return
        events = event_log.read_events(self.events)
        problems = event_log.check_edit_order(events)
        self.manifest["checks"]["event_order_problems"] = problems
        for problem in problems:
            self.fail("timeline: " + problem)
        if os.path.isfile(self.asks):
            hits = scan_rule_values.scan(asks=self.asks)
            self.manifest["checks"]["rule_values_in_recorded_questions"] = len(hits)
            if hits:
                self.fail("a recorded question contains a rule value (%d hit(s)): see scripts/scan_rule_values.py --asks" % len(hits))
            self.script("closeout.py", "--asks", self.asks, "--ingest", self.ingest,
                        "--out", os.path.join(self.dir, "closeout-result.json"), "--recheck")


def _snapshot(*folders: str) -> dict:
    snap = {}
    for folder in folders:
        for base, _dirs, files in os.walk(folder):
            for name in files:
                path = os.path.join(base, name)
                snap[path] = os.path.getmtime(path)
    return snap


def run_negative(args: argparse.Namespace) -> int:
    return subprocess.call([sys.executable, os.path.join(REPO, "scripts", "negative_test.py"), "--model", args.model,
                            "--max-turns", str(args.max_turns), "--runs-dir", args.runs_dir]
                           + (["--bare"] if args.bare else []), cwd=REPO)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arm", choices=sorted(step_table.ARMS), default=step_table.DEFAULT_ARM)
    parser.add_argument("--run-id", help="name of this run (default run-01)")
    parser.add_argument("--runs", type=int, default=1, help="repeat the whole run this many times: run-01, run-02, ...")
    parser.add_argument("--steps", type=int, nargs="+", help="run only these steps, for example --steps 4 7")
    parser.add_argument("--start", type=int, help="run this step and every step after it")
    parser.add_argument("--dry-run", action="store_true", help="print every prompt, run nothing")
    parser.add_argument("--reset", action="store_true", help="restore the starting state of the notes and exit")
    parser.add_argument("--negative", action="store_true", help="run the negative boundary tests instead of the ten steps")
    parser.add_argument("--runs-dir", default=os.path.join(REPO, "runs"))
    parser.add_argument("--max-turns", type=int, default=25)
    parser.add_argument("--model", default=neuron_ctl.load_pins()["model"],
                        help="model for every role session; pass '' for Claude Code's own default")
    parser.add_argument("--bare", action="store_true", help="pass --bare to claude: no hooks, no CLAUDE.md discovery, API key auth only")
    parser.add_argument("--skip-version-check", action="store_true", help="do not fail when okto-neuron differs from pins.json (the version is still recorded)")
    parser.add_argument("--keep-going", action="store_true",
                        help="with --runs N: a run that records a hard failure does not stop the later runs (the exit status is still non-zero)")
    parser.add_argument("--require-outcome", action="store_true", help="fail when the executable outcome check cannot run")
    parser.add_argument("--fail-on-outcome", action="store_true", help="exit non-zero when an outcome check fails (integration workflow)")
    args = parser.parse_args(argv)

    if args.reset:
        for action in reset_mod.reset():
            print(action)
        return 0
    if args.negative:
        return run_negative(args)

    chosen = step_table.STEPS
    partial = bool(args.steps or args.start)
    if args.steps:
        chosen = [s for s in chosen if s["id"] in args.steps]
    elif args.start:
        chosen = [s for s in chosen if s["id"] >= args.start]
    if not chosen:
        parser.error("no such step; steps are 1 to 10")

    if args.dry_run:
        for step in chosen:
            dry_run_step(step, args.arm)
        return 0

    status = 0
    for index in range(args.runs):
        if args.runs > 1:
            run_id = "%s-%02d" % (args.run_id or "run", index + 1)
        else:
            run_id = args.run_id or "run-01"
        run = Run(args.arm, run_id, args, partial)
        run.start()
        try:
            for step in chosen:
                code = run.run_step(step)
                if code != 0:
                    print("stopped at step %d" % step["id"])
                    status = code
                    break
        finally:
            finish = run.finish()
        status = status or finish
        if status != 0 and not args.keep_going:
            break
    return status


if __name__ == "__main__":
    sys.exit(main())
