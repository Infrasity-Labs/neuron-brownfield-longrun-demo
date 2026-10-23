# Test layout

Read from app/src/tests/ and app/jest.config.ts.

Unit tests are Jest files named *.test.ts under app/src/tests/services and app/src/tests/utils. They are run with npx nx test api. The database is mocked in app/src/tests/prisma-mock.ts with jest-mock-extended, so these tests do not need Postgres. End to end tests are in the separate app/e2e folder.
