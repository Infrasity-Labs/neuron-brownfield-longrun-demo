# Release checklist (demo policy)

This is a demo policy for this repo, not behaviour of the app.

Before a change ships, run npx nx test api and run npx prisma migrate deploy against a fresh database. Every new migration needs a one line note saying how to undo it.
