Plan feature 1: comment editing for the blogging API.

The feature lets a comment author change the text of their own comment through PUT /api/articles/:slug/comments/:id with a body of {"comment":{"body":"..."}}.

Ask Neuron for the rules this feature depends on: who may edit a comment, how long after creation an edit is allowed, how an edit is marked on the comment, how errors are returned, how migrations and tests are organised. Then write the spec to vault/specs/feature-1-comment-editing.md. For each rule give its name and its source path and byte range, without copying the value.
