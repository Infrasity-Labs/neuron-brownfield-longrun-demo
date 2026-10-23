# Ops runbook

When an API call fails, support reads the errors key in the response body. It maps each field name to a list of messages, for example {"errors":{"body":["can't be blank"]}}. New error responses should follow this shape.
