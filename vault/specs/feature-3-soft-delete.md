# Feature 3: soft delete for comments

Status: BLOCKED. Neuron's graph has a policy-soft-delete document, but no answer returned its text. The field, value and read rule are therefore not set here. Confirm the rule before building.

## Rules used

1. Error body: new errors use {"error":{"code":"<machine_code>","message":"<text>"}}. HTTP status codes do not change. Source: vault policy-error-response.md, bytes 101-280. Neuron says this is current and replaces the errors-by-field body. Conflict: ops-runbook.md (bytes 15-234) says new errors should use the errors-key shape. Follow the policy.
2. Current app error shapes, not to copy: {"errors":{"body":[...]}} for 422 and {"status":"error","message":...} for 401. Source: code-error-shape.md, bytes 0-504.
3. Comment fields today: id, createdAt, updatedAt, body, articleId, authorId. No deletedAt. Source: code-comment-model.md, bytes 0-245.
4. Delete today is a hard delete, which removes the row. Source: code-comment-ownership.md, bytes 0-427.
5. Not found or not owner: 404 with empty body. Source: code-comment-ownership.md, bytes 0-427.

## Open items for Builder

- Soft-delete field, deleted value, and whether reads exclude deleted rows: pending the policy-soft-delete text.
- comment.model.ts omits authorId, which the Prisma model has. Check it.
- editedAt comes from feature 1 and is out of scope here.
