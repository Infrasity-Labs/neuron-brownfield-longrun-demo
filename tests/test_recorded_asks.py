import json
import os
import unittest

import helpers

ASKS = os.path.join(helpers.REPO, "demo-state", "asks.jsonl")
SIX = {"ok", "no_llm", "empty", "provider_error", "truncated", "abnormal_stop", "unparsed"}


class RecordedAsks(unittest.TestCase):
    @unittest.skipUnless(os.path.isfile(ASKS), "no recorded run yet: demo-state/asks.jsonl does not exist")
    def test_every_recorded_ask_has_a_synthesis_status(self):
        for number, line in enumerate(open(ASKS), 1):
            if not line.strip():
                continue
            rec = json.loads(line)
            self.assertIn(rec.get("synthesis_status"), SIX, "line %d" % number)
            self.assertIn("vault_override_ignored", rec, "line %d" % number)
            self.assertIn("finish_reason", rec, "line %d" % number)


if __name__ == "__main__":
    unittest.main()
