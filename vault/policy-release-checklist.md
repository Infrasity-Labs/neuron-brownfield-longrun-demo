# Release checklist

Before a change ships, run npx prisma migrate deploy against a fresh database. Every new migration needs a one line note saying how to undo it.
