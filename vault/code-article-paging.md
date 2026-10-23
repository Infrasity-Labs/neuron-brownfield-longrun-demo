# Article list paging

Read from getArticles in app/src/app/routes/article/article.service.ts.

GET /api/articles reads the query parameters offset and limit. Offset defaults to 0 and limit defaults to 10. There is no upper bound on limit in the code today.
