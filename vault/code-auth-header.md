# Auth header

Read from app/src/app/routes/auth/auth.ts.

The API reads the login token from the Authorization header. The header value is the word Token or the word Bearer, a space, then the JWT. Any other scheme is ignored and the request counts as having no token.
