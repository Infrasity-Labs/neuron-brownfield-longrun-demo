import prismaMock from '../prisma-mock';
import { editComment } from '../../app/routes/article/article.service';

const MINUTE = 60 * 1000;

describe('editComment', () => {
  const commentId = 123;
  const userId = 456;

  const mockedUpdatedComment = (createdAt: Date) => ({
    id: commentId,
    createdAt,
    updatedAt: new Date(),
    editedAt: new Date(),
    body: 'edited body',
    articleId: 1,
    authorId: userId,
    author: {
      username: 'RealWorld',
      bio: null,
      image: null,
      followedBy: [],
    },
  });

  test('should throw 422 when the body is blank', async () => {
    // Given
    const createdAt = new Date(Date.now() - 1 * MINUTE);

    // When
    // @ts-ignore
    prismaMock.comment.findFirst.mockResolvedValue({ createdAt });

    // Then
    await expect(editComment('', commentId, userId)).rejects.toMatchObject({
      errorCode: 422,
      message: { errors: { body: ["can't be blank"] } },
    });
    expect(prismaMock.comment.update).not.toHaveBeenCalled();
  });

  test('should throw 404 with an empty body when the comment is not found or not owned', async () => {
    // When
    // @ts-ignore
    prismaMock.comment.findFirst.mockResolvedValue(null);

    // Then
    await expect(editComment('edited body', commentId, userId)).rejects.toMatchObject({
      errorCode: 404,
      message: {},
    });
    expect(prismaMock.comment.update).not.toHaveBeenCalled();
  });

  test('should look up the comment by id and author', async () => {
    // When
    // @ts-ignore
    prismaMock.comment.findFirst.mockResolvedValue(null);

    // Then
    await expect(editComment('edited body', commentId, userId)).rejects.toThrowError();
    expect(prismaMock.comment.findFirst).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { id: commentId, author: { id: userId } },
      }),
    );
  });

  test('should throw 422 when the edit window of 30 minutes has passed', async () => {
    // Given
    const createdAt = new Date(Date.now() - 31 * MINUTE);

    // When
    // @ts-ignore
    prismaMock.comment.findFirst.mockResolvedValue({ createdAt });

    // Then
    await expect(editComment('edited body', commentId, userId)).rejects.toMatchObject({
      errorCode: 422,
      message: { errors: { body: ['edit window has closed'] } },
    });
    expect(prismaMock.comment.update).not.toHaveBeenCalled();
  });

  test('should allow an edit just inside the 30 minute window', async () => {
    // Given
    const createdAt = new Date(Date.now() - 29 * MINUTE);

    // When
    // @ts-ignore
    prismaMock.comment.findFirst.mockResolvedValue({ createdAt });
    // @ts-ignore
    prismaMock.comment.update.mockResolvedValue(mockedUpdatedComment(createdAt));

    // Then
    await expect(editComment('edited body', commentId, userId)).resolves.toHaveProperty(
      'body',
      'edited body',
    );
  });

  test('should save the new body and set editedAt on a successful edit', async () => {
    // Given
    const createdAt = new Date(Date.now() - 2 * MINUTE);

    // When
    // @ts-ignore
    prismaMock.comment.findFirst.mockResolvedValue({ createdAt });
    // @ts-ignore
    prismaMock.comment.update.mockResolvedValue(mockedUpdatedComment(createdAt));

    // Then
    const result = await editComment('edited body', commentId, userId);

    expect(prismaMock.comment.update).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { id: commentId },
        data: expect.objectContaining({
          body: 'edited body',
          editedAt: expect.any(Date),
        }),
      }),
    );
    expect(result).toMatchObject({
      id: commentId,
      body: 'edited body',
      author: { username: 'RealWorld', following: false },
    });
    expect(result.editedAt).toBeInstanceOf(Date);
  });
});
