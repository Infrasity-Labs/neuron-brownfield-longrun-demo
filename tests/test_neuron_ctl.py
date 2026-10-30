import os
import re
import unittest
from unittest import mock

import helpers  # noqa: F401
import neuron_ctl as nc


class Version(unittest.TestCase):
    def test_parse_version_reads_the_first_line(self):
        self.assertEqual(nc.parse_version("okto-neuron 0.3.1\nOkto Neuron by Okto Labs"), "0.3.1")
        self.assertEqual(nc.parse_version("okto-neuron 0.4.0rc1\nx"), "0.4.0rc1")
        self.assertIsNone(nc.parse_version(""))
        self.assertIsNone(nc.parse_version("command not found"))

    def test_a_different_installed_version_stops_the_run(self):
        with mock.patch.object(nc, "installed_version", return_value="0.3.2"):
            with self.assertRaises(RuntimeError) as caught:
                nc.require_version("0.3.1")
        self.assertIn("pinned to 0.3.1", str(caught.exception))

    def test_a_missing_binary_stops_the_run(self):
        with mock.patch.object(nc, "installed_version", return_value=None):
            with self.assertRaises(RuntimeError):
                nc.require_version("0.3.1")

    def test_the_matching_version_passes(self):
        with mock.patch.object(nc, "installed_version", return_value="0.3.1"):
            self.assertEqual(nc.require_version("0.3.1"), "0.3.1")


class Isolation(unittest.TestCase):
    def test_commands_run_with_a_separate_home_non_default_ports_and_endpoint(self):
        with mock.patch.dict(os.environ, {"DEMO_NEURON_HOME": "/tmp/demo-home"}, clear=False):
            for name in ("DEMO_NEURON_REST_PORT", "DEMO_NEURON_MCP_PORT"):
                os.environ.pop(name, None)
            env = nc.neuron_env()
            self.assertEqual(env["HOME"], "/tmp/demo-home")
            self.assertEqual(env["OKTO_NEURON_ENDPOINT"], "http://127.0.0.1:17777")
            self.assertEqual(env["OKTO_NEURON_VAULTS_DIR"], "/tmp/demo-home/.okto-neuron/vaults")
            self.assertTrue(env["PATH"].startswith("/tmp/demo-home/tool/bin"))
            self.assertEqual(nc.mcp_url(), "http://127.0.0.1:18201/mcp")
            self.assertEqual(nc.token_file(), "/tmp/demo-home/.okto-neuron/daemon-17777.token")
            self.assertNotIn(nc.rest_port(), (7777,))
            self.assertNotIn(nc.mcp_port(), (8201,))

    def test_the_token_file_follows_the_rest_port(self):
        with mock.patch.dict(os.environ, {"DEMO_NEURON_HOME": "/h", "DEMO_NEURON_REST_PORT": "19000"}):
            self.assertEqual(nc.token_file(), "/h/.okto-neuron/daemon-19000.token")

    def test_the_demo_never_uses_the_real_home_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEMO_NEURON_HOME", None)
            self.assertTrue(nc.demo_home().endswith(".demo-home"))
            self.assertNotEqual(nc.demo_home(), os.path.expanduser("~"))


class ResetState(unittest.TestCase):
    def test_reset_deletes_the_isolated_app_home_and_keeps_the_install(self):
        import tempfile
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, ".okto-neuron", "vaults", "team"))
            os.makedirs(os.path.join(home, "tool", "bin"))
            with mock.patch.dict(os.environ, {"DEMO_NEURON_HOME": home}), mock.patch.object(nc, "stop") as stopped:
                nc.reset_state()
            stopped.assert_called_once()
            self.assertFalse(os.path.exists(os.path.join(home, ".okto-neuron")))
            self.assertTrue(os.path.isdir(os.path.join(home, "tool", "bin")))

    def test_reset_refuses_the_real_home(self):
        with mock.patch.dict(os.environ, {"DEMO_NEURON_HOME": os.path.expanduser("~")}), mock.patch.object(nc, "stop"):
            with self.assertRaises(RuntimeError):
                nc.reset_state()


class IngestCounts(unittest.TestCase):
    # the two status lines are copied from a live okto-neuron 0.3.1 daemon (2026-10-30)
    def test_both_status_forms_are_parsed(self):
        self.assertEqual(nc.parse_ingest_counts("  Ingest:   active (20/22 terminal, 1 processing, 1 queued)\n"), (20, 22))
        self.assertEqual(nc.parse_ingest_counts("  Ingest:   idle (22/22 terminal, 0 processing, 0 queued)\n"), (22, 22))
        self.assertIsNone(nc.parse_ingest_counts("Okto Neuron 0.3.1 - ok"))


class WaitIngest(unittest.TestCase):
    def run_wait(self, counts, idle, extra):
        import tempfile
        import wait_ingest
        out = os.path.join(tempfile.mkdtemp(), "ingest.jsonl")
        argv = ["--label", "x", "--vault", "team", "--settle", "0", "--poll", "0", "--out", out] + extra
        with mock.patch.object(wait_ingest.neuron_ctl, "ingest_counts", side_effect=counts), \
                mock.patch.object(wait_ingest, "ingest_idle", side_effect=idle), \
                mock.patch.object(wait_ingest.time, "sleep"):
            return wait_ingest.main(argv)

    def test_idle_before_the_edit_was_queued_is_not_accepted(self):
        # total 22 before the edit; the watcher has not queued the file for the first two samples although the queue is idle
        counts = [(22, 22), (22, 22), (22, 23), (22, 23), (23, 23)]
        calls = []
        def idle():
            calls.append(1)
            return True
        self.assertEqual(self.run_wait(counts, idle, ["--after-total", "22", "--min-new", "1"]), 0)
        self.assertEqual(len(calls), 2)  # idle is only sampled once the new file is counted, and twice in a row

    def test_a_file_the_daemon_never_queues_fails_the_wait(self):
        import wait_ingest
        with mock.patch.object(wait_ingest.time, "time", side_effect=[0, 1, 500, 500, 500]):
            self.assertEqual(self.run_wait([(22, 22)] * 5, lambda: True, ["--after-total", "22", "--queue-timeout", "180"]), 2)


class Outage(unittest.TestCase):
    def run_outage(self, body):
        calls = []
        with mock.patch.object(nc, "stop", lambda env=None: calls.append("stop")), \
                mock.patch.object(nc, "start", lambda env=None, wait_s=0: calls.append(("start", (env or {}).get("KEY_ENV")))):
            try:
                with nc.outage("KEY_ENV"):
                    calls.append("inside")
                    body()
            except RuntimeError:
                calls.append("raised")
        return calls

    def test_the_daemon_is_restarted_with_an_invalid_key_and_restored_afterwards(self):
        calls = self.run_outage(lambda: None)
        self.assertEqual(calls, ["stop", ("start", nc.INVALID_KEY), "inside", "stop", ("start", None)])

    def test_the_daemon_is_restored_even_when_the_role_run_fails(self):
        def boom():
            raise RuntimeError("role crashed")
        calls = self.run_outage(boom)
        self.assertEqual(calls[-3:], ["stop", ("start", None), "raised"])
        self.assertEqual(calls.count("stop"), 2)


if __name__ == "__main__":
    unittest.main()
