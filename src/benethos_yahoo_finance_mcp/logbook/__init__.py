"""Every line this server writes to its log, and where the log goes.

Nothing outside this package imports :mod:`logging`. A line is a function in
one of four modules, named for what happened:

- :mod:`.lifecycle` — starting, what the port is guarded by, settings ignored
- :mod:`.calls` — one line per tool call, and arguments a call refused
- :mod:`.cache` — the result cache's state and its failures
- :mod:`.upstream` — what Yahoo did: rate limits, a missing constant

The parameters come from a small vocabulary that ``tests/test_logbook_catalog.py``
holds, and :mod:`._describe` turns them into text. That is where the rules about
what a line may carry are kept: a symbol or a key yes, since they are public
identifiers. Never the bearer token, a search query (free text a person typed),
a URL's query string, anything from Yahoo's answer, or the text of an error
this server raised, which is written for the model. A line names the error's
class instead.

:mod:`.output` installs the one handler on stderr, and :mod:`.access` shapes
uvicorn's request log to the same rules.
"""

from __future__ import annotations

from . import cache, calls, lifecycle, output, upstream

__all__ = ["cache", "calls", "lifecycle", "output", "upstream"]
