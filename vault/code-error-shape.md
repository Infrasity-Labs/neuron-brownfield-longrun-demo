# Error shape in the code today

Read from app/src/main.ts and app/src/app/models/http-exception.model.ts.

Services throw HttpException with a status code and a body. The error handler in main.ts sends that body as the whole JSON response. Validation errors use the status 422 and a body like {"errors":{"body":["can't be blank"]}}. A missing or bad token returns 401 with {"status":"error","message":"missing authorization credentials"}. Any other error returns 500 with the error message as the body.
