# Feature 1: comment editing

Paths: .marginalia/sources/14bfef7e474715c5/<name> (vault team). "demo" = policy, not app behaviour.

Endpoint: PUT /api/articles/:slug/comments/:id, body {"comment":{"body":"..."}}. Not in app yet.

## Rules
1. Author only. policy-edit-window 0-220 (demo); code-comment-ownership 0-427.
2. Edit window 15 min after createdAt; later edits refused (status not given). policy-edit-window 0-220 (demo).
3. editedAt: nullable timestamp, null until first edit, set on each edit. Migration keeps existing rows. policy-edited-at-marker 0-300 (demo).
4. Not found or not author: 404, empty body. code-comment-ownership 0-427.
5. 422 {"errors":{"body":["can't be blank"]}} for validation; 401 {"status":"error","message":"missing authorization credentials"}; other errors 500 with message. No wrapper. code-error-shape 0-504; policy-error-response 0-318 (demo).
6. Timestamped migration folders, npx prisma migrate deploy, DATABASE_URL. code-migrations 0-390. One-line undo note per migration. policy-release-checklist 0-267 (demo).
7. Jest *.test.ts in app/src/tests/services and app/src/tests/utils; npx nx test api. Prisma mocked in app/src/tests/prisma-mock.ts. code-test-layout 0-366.
8. Fields: id, createdAt, updatedAt, body, articleId, authorId; no editedAt yet. code-comment-model 0-245.

## Open (not from Neuron, Maintainer to confirm)
- Edit after window: proposed 422 with errors.body.
- Non-author edit: proposed 404, as delete does.
- app/src/app/routes/article/comment.model.ts omits authorId, which the Prisma model has. Builder should check.
