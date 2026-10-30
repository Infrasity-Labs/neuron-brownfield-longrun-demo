/*
 * Executable outcome checks for the Builder's code. Not part of the app: scripts/code_outcome.py copies this file
 * to app/src/tests/outcome/outcome.test.ts inside the run's own copy of app/, runs it with jest, and reads the
 * result. It never runs inside this repository's app/ tree.
 *
 * It drives the real Express router with the database mocked (the app's own prisma-mock), so it needs no Postgres
 * and does not care which Prisma methods the Builder chose. Every test name starts with a check id that
 * scripts/code_outcome.py maps to a work product.
 *
 *   EDIT_WINDOW_MINUTES  the edit window that is current when the check runs (15 or 30)
 *   ARTICLE_LIMIT_CAP    the article list cap (50)
 */
import * as http from 'http';
import { AddressInfo } from 'net';
import express from 'express';
import * as bodyParser from 'body-parser';
import prismaMock from '../prisma-mock';
import routes from '../../app/routes/routes';
import generateToken from '../../app/routes/auth/token.utils';

const MINUTE = 60 * 1000;
const WINDOW = Number(process.env.EDIT_WINDOW_MINUTES || '30');
const CAP = Number(process.env.ARTICLE_LIMIT_CAP || '50');
const USER_ID = 7;

function buildApp(): express.Express {
  const app = express();
  app.use(bodyParser.json());
  app.use(routes);
  // The same error handler as src/main.ts, which cannot be imported because it starts a server.
  app.use((err: any, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
    if (err && err.name === 'UnauthorizedError') {
      return res.status(401).json({ status: 'error', message: 'missing authorization credentials' });
    }
    if (err && err.errorCode) {
      return res.status(err.errorCode).json(err.message);
    }
    return res.status(500).json(err && err.message);
  });
  return app;
}

function request(
  server: http.Server,
  method: string,
  path: string,
  body?: any,
  headers: { [name: string]: string } = {},
): Promise<{ status: number; body: any }> {
  const { port } = server.address() as AddressInfo;
  const payload = body === undefined ? undefined : JSON.stringify(body);
  const allHeaders: { [name: string]: string } = { 'Content-Type': 'application/json' };
  if (payload !== undefined) {
    allHeaders['Content-Length'] = String(Buffer.byteLength(payload));
  }
  Object.keys(headers).forEach((name) => {
    allHeaders[name] = headers[name];
  });
  return new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port, method, path, headers: allHeaders }, (res) => {
      let data = '';
      res.on('data', (chunk) => {
        data += chunk;
      });
      res.on('end', () => {
        let parsed: any = data;
        try {
          parsed = data ? JSON.parse(data) : {};
        } catch (e) {
          parsed = data;
        }
        resolve({ status: res.statusCode || 0, body: parsed });
      });
    });
    req.on('error', reject);
    if (payload !== undefined) {
      req.write(payload);
    }
    req.end();
  });
}

function commentRow(ageMinutes: number): any {
  const createdAt = new Date(Date.now() - ageMinutes * MINUTE);
  return {
    id: 1,
    createdAt,
    updatedAt: createdAt,
    editedAt: null,
    deletedAt: null,
    body: 'original text',
    articleId: 1,
    authorId: USER_ID,
    author: { id: USER_ID, username: 'author', bio: null, image: null, followedBy: [] },
    article: { id: 1, slug: 'a-slug', authorId: USER_ID },
  };
}

// Whatever lookup the Builder chose, it finds this comment, owned by the caller, created `ageMinutes` ago.
function mockComment(ageMinutes: number): void {
  const row = commentRow(ageMinutes);
  const comment = prismaMock.comment as any;
  ['findFirst', 'findUnique', 'findFirstOrThrow', 'findUniqueOrThrow'].forEach((method) => {
    comment[method].mockResolvedValue(row);
  });
  comment.update.mockImplementation(async (args: any) => ({ ...row, ...(args && args.data ? args.data : {}) }));
  comment.updateMany.mockResolvedValue({ count: 1 });
  const article = prismaMock.article as any;
  article.findUnique.mockResolvedValue(row.article);
  article.findFirst.mockResolvedValue(row.article);
}

describe('outcome checks', () => {
  let server: http.Server;

  beforeAll((done) => {
    server = http.createServer(buildApp()).listen(0, '127.0.0.1', done);
  });

  afterAll((done) => {
    server.close(done);
  });

  const edit = () =>
    request(
      server,
      'PUT',
      '/api/articles/a-slug/comments/1',
      { comment: { body: 'edited text' } },
      { Authorization: 'Token ' + generateToken(USER_ID) },
    );

  test('edit-window: accepts an edit one minute inside the window', async () => {
    mockComment(WINDOW - 1);
    const res = await edit();
    expect([200, 201]).toContain(res.status);
  });

  test('edit-window: refuses an edit one minute outside the window', async () => {
    mockComment(WINDOW + 1);
    const res = await edit();
    // A client error is a refusal. A 500 is a crash, not a rule, so it does not count as refusing.
    expect(res.status).toBeGreaterThanOrEqual(400);
    expect(res.status).toBeLessThan(500);
  });

  const list = async (query: string) => {
    const article = prismaMock.article as any;
    article.count.mockResolvedValue(0);
    article.findMany.mockResolvedValue([]);
    const res = await request(server, 'GET', '/api/articles' + query);
    const calls = article.findMany.mock.calls;
    return { res, take: calls.length ? calls[calls.length - 1][0].take : undefined };
  };

  test('article-limit: caps a limit above the cap', async () => {
    const { res, take } = await list('?limit=' + (CAP + 1));
    expect(res.status).toBe(200);
    expect(take).toBe(CAP);
  });

  test('article-limit: keeps a limit below the cap', async () => {
    const { res, take } = await list('?limit=20');
    expect(res.status).toBe(200);
    expect(take).toBe(20);
  });

  test('article-limit: keeps the default limit when none is given', async () => {
    const { res, take } = await list('');
    expect(res.status).toBe(200);
    expect(take).toBe(10);
  });
});
