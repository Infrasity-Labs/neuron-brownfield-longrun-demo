# Migrations

Read from app/src/prisma/ and app/package.json.

The database schema is the Prisma file app/src/prisma/schema.prisma. Migrations live in app/src/prisma/migrations, one folder per migration, named with a timestamp. The folder has four migrations today. They are applied with npx prisma migrate deploy, and the database address comes from the DATABASE_URL environment variable.
