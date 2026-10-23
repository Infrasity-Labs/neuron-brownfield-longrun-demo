# Comment ownership

Read from deleteComment in app/src/app/routes/article/article.service.ts.

A comment belongs to the user in its authorId field. Deleting a comment looks it up by id and by the current user id together. When the comment is not found, or belongs to someone else, the API returns 404 with an empty body. The 403 branch that follows in the code cannot be reached, because the lookup already filters by author.
