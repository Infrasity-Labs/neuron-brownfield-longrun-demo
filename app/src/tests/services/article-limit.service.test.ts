import prismaMock from '../prisma-mock';
import { getArticles } from '../../app/routes/article/article.service';

describe('getArticles limit', () => {
  beforeEach(() => {
    // @ts-ignore
    prismaMock.article.count.mockResolvedValue(0);
    // @ts-ignore
    prismaMock.article.findMany.mockResolvedValue([]);
  });

  const takeFor = async (query: any) => {
    await getArticles(query);
    // @ts-ignore
    const args = prismaMock.article.findMany.mock.calls[0][0];
    return args.take;
  };

  test('limit 50 returns 50', async () => {
    expect(await takeFor({ limit: '50' })).toBe(50);
  });

  test('limit 51 is capped to 50', async () => {
    expect(await takeFor({ limit: '51' })).toBe(50);
  });

  test('no limit returns the default of 10', async () => {
    expect(await takeFor({})).toBe(10);
  });

  test('limit "abc" returns the default of 10', async () => {
    expect(await takeFor({ limit: 'abc' })).toBe(10);
  });

  test('limit 20 is passed through unchanged', async () => {
    expect(await takeFor({ limit: '20' })).toBe(20);
  });

  test('limit 0 returns the default of 10', async () => {
    expect(await takeFor({ limit: '0' })).toBe(10);
  });

  test('negative limit returns the default of 10', async () => {
    expect(await takeFor({ limit: '-5' })).toBe(10);
  });
});
