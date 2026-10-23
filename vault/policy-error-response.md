# Error response rule (demo policy)

This is a demo policy for this repo, not behaviour of the app.

All new error responses use an error object: {"error":{"code":"<machine_code>","message":"<text>"}}. This replaces the older errors-by-field body. HTTP status codes do not change.
