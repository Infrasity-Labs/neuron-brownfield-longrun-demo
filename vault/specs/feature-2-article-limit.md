# Feature 2: cap on the article list limit

Goal: GET /api/articles returns at most 50 articles per request.

## Rules (Neuron vault "team")

1. Max limit is 50. A higher limit is treated as 50.
   Source: vault/policy-article-list-limit.md, bytes 0-222.
   Caveat: this file calls itself a demo policy.
2. Default limit is 10. Default offset is 0.
   Source: vault/code-article-paging.md, bytes 0-258.

## Current code

- article.controller.ts:31-38 passes req.query to getArticles.
- article.service.ts:83 uses `take: Number(query.limit) || 10`. No upper bound today.

## Conflict

The code note (rule 2 source) says there is no upper bound, which matches the code.
The 50 cap comes only from the demo policy (rule 1). Builder implements 50.
Maintainer should confirm 50 is the real value.

## Builder notes

- Likely change: `take: Math.min(Number(query.limit) || 10, 50)`.
- No rule covers negative limits. Builder decides.
- Out of scope: GET /api/articles/feed.

## Tests

- limit 50 gives 50; limit 51 gives 50; no limit gives 10; limit "abc" gives 10.
