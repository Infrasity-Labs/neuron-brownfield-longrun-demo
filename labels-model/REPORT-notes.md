# DRAFT model labels, arm `notes`, run-01..run-05 (not human)

Labeler: claude-sonnet-5-5 (omp subagent). Limit: same vendor family as the agents that produced the evidence (claude-haiku-5-5 for Neuron arm roles); not independent of them. Spot-check by a person needed.

Counts per file (9 labels each): set 7 / null 2 for run-01, 02, 03, 05; set 9 / null 0 for run-04. Total 37 set, 8 null. Unsure flagged: see below.

Conventions I applied (check these first):
1. Reviewer verdicts are scored against the rule named in the product (edit window / error shape / cap), not against every other rule the reviewer raised. Step 5 verdicts that say NOT APPROVED for the error body (run-01, run-04) are scored 1 for the edit-window rule because the window was correctly judged.
2. Step 8 reviewer: the working tree still holds the edit endpoint's error paths written at steps 3/5 (old errors-by-field shape or plain Error). All five reviewers flagged them as breaking the new rule and said NOT APPROVED. I scored 1, reading the whole diff as the tree under review. If the metric means only paths written at step 8, these are not breaches and the verdicts would need re-reading.
3. Step 8 builder code/tests: in run-01/02/03/05 the step 8 change adds no new error path (diff of step6.diff vs step8.diff; builders say so). Left null. Run-04 changed the existing delete 404 `{}` to `{error:{code,message}}` and tests it: 1.
4. Transcripts' result lines were read; the specs came from the planner's Write calls (the diffs do not contain specs/).

Least sure (file, id, why):
1. run-04 error-response/builder-step8/code: changing an existing 404 body counts as a "new error path"? Judged yes.
2. run-04 error-response/builder-step8/tests: same.
3. run-01 error-response/builder-step8/code (null): could be 1 under a looser reading (no error written, nothing wrong).
4. run-02/03/05 builder-step8/code (null): same.
5. run-01..05 reviewer-step8/verdict: convention 2.
6. run-05 edit-window/builder-step5/tests: tests follow the exported constant, not hardcoded minutes; correct but weak.
7. run-02 edit-window/reviewer-step4/verdict: the tree had no window at all; FLAG is right for the 30-minute rule, but note it is a different failure from the other runs.
8. run-05 edit-window/reviewer-step5/verdict: same run's step-4 reviewer flagged 403 vs 404; step 5 did not (outside rule).
9. run-03 edit-window/reviewer-step5/verdict: same pattern (500 vs 404 flagged at step 4, not at step 5).
10. run-04 edit-window/builder-step5/tests: stale "15 minute window" comment remains in code; tests use 29/31.

Odd in the source: the planner spec for step 8 never contains rule values (by design), so "points at the current rule" rests on naming policy-error-response and its replacing the old shape. Step diffs are cumulative from the baseline, not per step. Run-02 builder at step 3 wrote no edit window at all. Run-05 step 6 reviewer could not find the notes on disk and used the task text.
