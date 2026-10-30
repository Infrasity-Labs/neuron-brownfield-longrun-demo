# Error response rule

New error responses use the body the app already sends: an object with an errors key that maps a field name to a list of messages, for example {"errors":{"body":["can't be blank"]}}. There is no extra wrapper object.
