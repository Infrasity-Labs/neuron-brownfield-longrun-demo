import prismaMock from '../prisma-mock';
import { deleteComment, getCommentsByArticle } from '../../app/routes/article/article.service';

describe('deleteComment', () => {
  const commentId = 123;
  const userId = 456;

  test('should throw 404 with an empty body when the comment is not found or not owned', async () => {
    // When
    // @ts-ignore
    prismaMock.comment.findFirst.mockResolvedValue(null);

    // Then
    await expect(deleteComment(commentId, userId)).rejects.toMatchObject({
      errorCode: 404,
      message: {},
    });
    expect(prismaMock.comment.update).not.toHaveBeenCalled();
    expect(prismaMock.comment.delete).not.toHaveBeenCalled();
  });

  test('should look up the comment by id and author', async () => {
    // When
    // @ts-ignore
    prismaMock.comment.findFirst.mockResolvedValue(null);

    // Then
    await expect(deleteComment(commentId, userId)).rejects.toThrowError();
    expect(prismaMock.comment.findFirst).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { id: commentId, author: { id: userId } },
      }),
    );
  });

  test('should set deletedAt and keep the row instead of removing it', async () => {
    // When
    const existingComment = { author: { id: userId, username: 'RealWorld' } };
    // @ts-ignore
    prismaMock.comment.findFirst.mockResolvedValue(existingComment);
    // @ts-ignore
    prismaMock.comment.update.mockResolvedValue({});

    // Then
    await expect(deleteComment(commentId, userId)).resolves.toBeUndefined();
    expect(prismaMock.comment.update).toHaveBeenCalledWith({
      where: { id: commentId },
      data: { deletedAt: expect.any(Date) },
    });
    expect(prismaMock.comment.delete).not.toHaveBeenCalled();
  });
});

describe('getCommentsByArticle', () => {
  const slug = 'some-article-1';

  test('should leave out comments that have a deletedAt value', async () => {
    // When
    // @ts-ignore
    prismaMock.article.findUnique.mockResolvedValue({ comments: [] });

    // Then
    await getCommentsByArticle(slug);
    expect(prismaMock.article.findUnique).toHaveBeenCalledWith(
      expect.objectContaining({
        include: expect.objectContaining({
          comments: expect.objectContaining({
            where: expect.objectContaining({ deletedAt: null }),
          }),
        }),
      }),
    );
  });

  test('should still filter deleted comments when a user is logged in', async () => {
    // When
    // @ts-ignore
    prismaMock.article.findUnique.mockResolvedValue({ comments: [] });

    // Then
    await getCommentsByArticle(slug, 456);
    expect(prismaMock.article.findUnique).toHaveBeenCalledWith(
      expect.objectContaining({
        include: expect.objectContaining({
          comments: expect.objectContaining({
            where: expect.objectContaining({ deletedAt: null }),
          }),
        }),
      }),
    );
  });
});
