# JWT settings

Read from app/src/app/routes/auth/auth.ts and app/src/app/routes/auth/token.utils.ts.

Tokens are signed with HS256. The secret comes from the JWT_SECRET environment variable, and falls back to the string superSecret when it is not set. A token expires after 60 days.
