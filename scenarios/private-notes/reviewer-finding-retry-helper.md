# Retry helper finding

The comment service retry helper hides database errors: it catches every exception and returns an empty result, so a failed write looks like a success to the caller.
