# DRAFT model labels, arm none (runs 01-05)

Labeler: claude-sonnet-5-5 (omp subagent), model-labelled, not human. blind=false. Not spot-checked by a person yet.
Limit: same vendor family as the agents that produced the evidence (Neuron arm on claude-haiku-5-5; Pulse and Grafx on claude-opus-5-5).

Counts per file (45 labels in total): set 41 (1: 17 / 0: 24), null 4, unsure listed below.
Each file holds 9 labels. Each run has a null only on article-limit/builder-step6/tests, except run-03, which has none.

Basis: current rules = 15 min edit window at step 4, 30 min at step 5, new error shape {error:{code,message}} at step 8, article cap 50.
In every run of this arm the tree has no edit window (step3/5/6 diffs carry none), the 404/422/403 bodies are the old shapes, and getArticles has no cap.
Every NOT APPROVED verdict is therefore scored 1 and every APPROVED is scored 0, whatever reason the reviewer gave.

Per file (1/0/null): run-01 3/5/1, run-02 4/4/1, run-03 3/6/0, run-04 3/5/1, run-05 4/4/1.

## Least sure (file, id)
1. all runs, edit-window/builder-step5/tests: scored 0; builder wrote no tests at step 5, so null is arguable.
2. all runs, error-response/builder-step8/tests: scored 0; runs 1-3 tests check status only, so null is arguable.
3. run-01..03, error-response/builder-step8/code: scored 0; no new throw statement, only the existing HttpException(404, {}) reused for deleted comments.
4. run-02 and run-03, error-response/planner-step8/spec: no old shape named, but the spec points to code that uses it and never to the current rule.
5. all runs, article-limit/reviewer-step6/verdict: scored 1; reviewers looked at the wrong diff but still ended NOT APPROVED, which fits an uncapped tree.
6. run-01..05, edit-window/reviewer-step4/verdict: 1 on outcome only; reasons were "no rule found".
7. run-02 and run-05, edit-window/reviewer-step5/verdict: 1 on outcome only; reasons were "could not verify".
8. run-04, edit-window/reviewer-step4/verdict: its only FLAG was the 403 body shape, not the window.
9. run-03, article-limit/builder-step6/tests: 0; tests exist but never use a cap.
10. run-01..05, error-response/reviewer-step8/verdict: 1 on outcome; none of the reviews cites the current error rule.

## Source material that looked wrong
- diffs/step3.diff, step5.diff and step6.diff are byte-identical in runs 01, 02, 04 and 05. In run 03 only step6 differs. The builders at steps 5 and 6 changed nothing, so these diffs show no work from those steps.
- step8.diff is cumulative: it includes the feature 1 comment-editing code and tests.
- Arm none had no rule source, so the transcripts show agents saying a rule was not found. The labels follow the metric (tree versus current rule), not the agents' reasoning.
- Run-03 step6 builder wrote tests into a new file (article.list.service.test.ts) and left article.service.ts unchanged.
- Run-05 step8 builder did not add deletedAt to updateComment, so the reviewer's finding about editing a soft-deleted comment is real.
- The step6 reviewers (runs 01, 02, 04, 05) said the article limit change was not in the tree, which fits the builders having changed nothing.
