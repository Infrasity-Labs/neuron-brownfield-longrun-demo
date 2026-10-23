# Test fixtures

- `ask_ok.json` and `ask_provider_error.json` are real responses from the Neuron `ask` tool, saved during the setup check on 2026-10-22 (see docs/VERIFIED.md). The second one is a real `provider_error` caused by a free-tier rate limit.
- `vaults/team/.marginalia/sources/14bfef7e474715c5/setup-test.md` is the 177 byte source file those responses cite. The tests read it the way the verifier reads a real vault.
- Test inputs that were written by hand for a unit test, and are not recorded results, say "synthetic" in the test that builds them.
