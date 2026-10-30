# Support-sample DRAFT model labels (neuron runs 01-05)

Labeler: claude-sonnet-5-5 (omp subagent), model-labelled, not human. Spot-check by a person is pending. Limit: same vendor family as the Neuron agents (claude-haiku-5-5), different model. Judged only against each entry's own `cited_text`.

| file | supported rate | full | partial | none |
|---|---|---|---|---|
| run-01 | 0.900 | 8 | 2 | 0 |
| run-02 | 0.900 | 8 | 2 | 0 |
| run-03 | 0.900 | 8 | 2 | 0 |
| run-04 | 0.750 | 6 | 3 | 1 |
| run-05 | 0.900 | 9 | 0 | 1 |

(Output of `python3 scripts/support_sample.py report` per file.)

Rules applied: 0.5 where the answer states "new error responses must use the errors-key shape / no extra wrapper" with only code-error-shape cited (no cited text says that). 0 where the only source for the claim has no cited_text (stale anchor): run-04 #3, run-05 #2.

Judgment calls: answers that frame the soft-delete policy as "intended" vs the schema as "current code" were scored 1 (hedged inference from two accurately quoted sources): run-01 #8, run-03 #8, run-04 #7, run-05 #1, #8. Run-03 #9 is an abstention ("no soft-delete policy in notes"); scored 1 against its cited text, which holds no soft-delete source. Run-05 #7 (multi-note recap) scored 1 after reading the full cited review and step-5 notes.
