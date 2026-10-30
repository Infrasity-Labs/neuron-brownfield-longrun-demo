# Edited marker

A comment has a nullable timestamp field named editedAt. It stays null until the first edit. Each successful edit sets it to the time of the edit. The migration that adds it must not change existing rows.
