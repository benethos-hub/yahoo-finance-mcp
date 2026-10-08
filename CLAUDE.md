# Working guidelines for Claude

How to work in this repository. Read this before making changes. See
[SPECS.md](SPECS.md) for what the project is and does.

## Golden rules

1. **Virtual environment only.** Never use the global Python/pip. Work inside a
   virtual environment — a `uv`-created `.venv` counts as one, so `uv run ...`
   satisfies this rule. Without uv, invoke the project venv interpreter:
   - `.\.venv\Scripts\python.exe ...` (PowerShell)
   - `.venv/Scripts/python.exe ...` (Bash on Windows)
   Install deps into the venv (`uv sync --extra dev`, or `-e .` / `-e ".[dev]"`).
2. **English in the repo.** All code, comments, docstrings, and docs are in
   English. (Conversation with the user may be in German.)
3. **stdio is sacred.** stdout carries the MCP JSON-RPC stream. Never `print()`
   to stdout from server/library code; log to **stderr** only.
4. **Read-only domain.** This server only reads market data. Do not add write
   or trade operations, and do not authenticate to Yahoo or any paid feed (see
   non-goals in SPECS.md). Guarding this server's own HTTP port is a different
   thing and is allowed — see `transport/http.py`.

## Environment

- Windows, PowerShell or Bash. Python 3.11-3.14 (developed on 3.14).
- Set up (recommended): `uv sync --extra dev` (creates `.venv`, installs the
  versions pinned in `uv.lock`). Without uv: `py -m venv .venv` then
  `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`.
- Run the server (stdio): `uv run benethos-yahoo-finance-mcp`, or
  `.\.venv\Scripts\python.exe -m benethos_yahoo_finance_mcp`. For HTTP
  transports and Docker/Compose hosting, see the README (`--transport`) and
  `containers/README.md`.

## Project layout

```
src/benethos_yahoo_finance_mcp/
  cli.py          # parser + main(): settings, log, cache, build, hand to transport
  __main__.py     # enables `python -m benethos_yahoo_finance_mcp`
  settings.py     # every YF_MCP_* variable and flag, resolved once, TTL defaults
  server.py       # instructions + build_server() + refused-arguments logging
  tools/          # the tools a client sees, one module per subject, thin
    _base.py      #   Symbol, READ_ONLY, register_tool (adds the log line)
  yahoo/          # all yfinance access, the same seven subjects as tools/
    tickers.py    #   get_ticker, upstream(), normalize()
  cache.py        # opt-in persistent result cache (SQLite) with per-tool TTLs
  formatting.py   # pandas/yfinance -> compact JSON-safe values
  logbook/        # every log line as a function, the one stderr handler
  transport/      # stdio.py, http.py (Host allow-list + optional bearer guard)
  errors.py       # ToolError / SymbolNotFoundError / RateLimitError
  py.typed        # PEP 561 marker, without it the annotations reach nobody
tests/            # mocked, offline unit tests (+ live smoke.py, not collected)
  yahoo/          #   one test file per yahoo module, FakeTicker in fakes.py
containers/
  images/yahoo-finance-mcp/Dockerfile   # build context: the repository root
  production/     # compose.yaml + .env.example, the published image
  development/    # compose.yaml, built from the checkout, port 8001
.github/workflows/
  ci.yml          # lint, test matrix, fresh-install, lowest-versions, docker
  publish.yml     # PyPI + ghcr on a published GitHub release
```

Keep the layers separate: **tools stay thin** and hand their arguments to the
yahoo function of the same name. Put any new yfinance call in `yahoo/`, never
in a tool. `tests/test_layers.py` holds the import table (which unit may
import which), and a new module needs a line there. Packages are entered only
through their `__init__.py`, so a new public name goes into its `__all__`.

**Logging goes through `logbook/`.** No other module imports `logging`. A new
line is a function in `logbook/lifecycle.py`, `calls.py`, `cache.py` or
`upstream.py`, taking parameters from the vocabulary in
`tests/test_logbook_catalog.py`, and it never carries a search query, the
token, a URL's query string, Yahoo's data or an error's text (see SPECS §4).
A tool writes no line of its own, `register_tool` writes one per call.

## How to add or change a tool

1. Add the data-fetching logic to the matching module in `yahoo/`. Put every
   yfinance call inside
   `with tickers.upstream("Failed to load ... for {symbol!r}"):`, which routes
   failures through `wrap_upstream` so rate limits map to `RateLimitError`
   and other errors keep context. Get the ticker with `tickers.get_ticker`,
   called through the module so the tests' one patch reaches it. Raise
   `SymbolNotFoundError(symbol)` on empty results, and echo the symbol as
   `tickers.normalize(symbol)`. Decorate the function with
   `@cache.cached("<category>")` and add that category with a TTL to
   `settings.DEFAULT_TTLS` (the cache is opt-in, and the decorator is a no-op
   until enabled). If "nothing found" is a non-empty value, pass
   `worth_keeping=` so it is not cached. Export it from `yahoo/__init__.py`.
2. Convert pandas output with `formatting.dataframe_to_records` / `to_jsonable`.
   It takes `None`, caps at `max_rows` and keeps the tail. Pass `head=True` for
   a frame ranked from the top. Cap silently only where the tail or head is
   obviously what a caller wants, and otherwise report `truncated`.
3. Expose it in the `tools/` module of the same name and add it to that
   module's `register()`. `register_tool` gives it the shared
   `readOnlyHint`/`openWorldHint` pair every tool carries (a test asserts it
   for all of them) and its log line. The **docstring becomes the
   tool description** Claude sees — write it for an LLM caller, and leave
   allowed values to the parameter descriptions rather than repeating them.
   Give every parameter an `Annotated[type, Field(description=...)]` (reuse
   the `Symbol` alias for ticker arguments); add `ge`/`le` bounds for numeric
   limits. A row cap is called `limit`, in the tool and in the yahoo function.
4. Add unit tests in `tests/yahoo/test_<module>.py` using the `FakeTicker`
   pattern (the `patch_ticker` fixture patches `tickers.get_ticker`, or patch
   `tickers.yf.Search`). Do not hit the network in tests.

## Verifying

Commands use uv (recommended); the venv interpreter forms
(`.venv/Scripts/python.exe -m ...`) work too.

- Tests: `uv run pytest -q` (must stay green; offline).
- Lint + format: `uv run ruff check .` and `uv run ruff format .`
  (CI checks `ruff format --check`).
- Types: `uv run mypy`.
- Coverage (CI floor 80%):
  `uv run pytest --cov=benethos_yahoo_finance_mcp --cov-fail-under=80`.
- Inspect what the client sends to Claude (no Desktop restart needed):
  ```
  uv run python -c "import asyncio,json;from benethos_yahoo_finance_mcp.server import mcp;print(json.dumps([t.model_dump() for t in asyncio.run(mcp.list_tools())],indent=2,default=str))"
  ```
- Live check against Yahoo: `uv run python tests/smoke.py`.
- After changing tool signatures/docstrings, **fully restart Claude Desktop**
  (quit from the tray, not just close the window) to reload the tools.

**The gates above do not cover a `yfinance` upgrade.** The unit tests mock
yfinance completely and stay green through any change in its behaviour, field
names or response shapes, and the `fresh-install` CI job only catches import
errors. Bump it on its own, run `tests/smoke.py` **before** the bump as a
baseline and again afterwards, and check that every section returned data rather
than trusting the exit code. Without the baseline a green run afterwards cannot
be told apart from Yahoo simply having a good day.

**They do not cover an `mcp` upgrade either.** The suite stops at the yahoo
package and never travels through the SDK, so a change in the layer between the tools
and the client passes every gate. Version 2.1.0 did exactly that: it began
forwarding a tool's error text only for exceptions deriving from the SDK's own
`ToolError`, and the messages here reached the model as
`Error executing tool <name>` and nothing else, with 246 tests green. On any
`mcp` bump, read the release notes for behaviour changes around tool results,
errors and schemas, and exercise a tool through `mcp.call_tool` rather than
trusting the suite. `tests/test_tools_integration.py` is where that happens,
and it now asserts the message text as well.

## Conventions

- Type hints everywhere; `from __future__ import annotations` at the top.
- Surface expected failures as `ToolError` subclasses with concise messages —
  never leak a raw traceback to the client. `errors.ToolError` derives from the
  SDK's own `ToolError`, and that is what carries the message: anything else
  raised from a tool is reported to the client as `Error executing tool <name>`
  with the text dropped.
- Default tool output is compact JSON; keep responses small (row caps) to
  respect the client's token budget.

## Git / commits

- Commit only when the user asks. Use clear, descriptive messages.
- Every CI job must pass before a merge, except `lowest-versions`. That one
  installs the oldest versions `pyproject.toml` allows and is an early warning,
  not a gate. When it goes red, raise the lower bound it names, it is not a
  reason to hold a pull request.
- Do not commit `.venv/`, `__pycache__/`, or `*.egg-info/` (already gitignored).

## Releasing

A release is its own `release/X.Y.Z` branch and PR. In this order:

1. **`uv lock --upgrade --dry-run` first.** Dependabot lifts direct
   dependencies only, and the transitive ones underneath move only when a
   direct bump happens to drag them along. An index installation (`uvx`,
   `pip`) resolves the newest of everything at install time, the container
   image freezes whatever `uv.lock` says, so a release is the moment the image
   catches up with what every index user already has. Refresh with
   `uv lock --upgrade` as its own commit, then the gates, plus the `yfinance`
   or `mcp` checks above for anything that sits under those. A security hole
   does not wait for this step: Dependabot's security updates read the whole
   lockfile, transitive packages included, and arrive on their own.
   The same goes for the two image digests in the `Dockerfile`
   (`containers/images/yahoo-finance-mcp/`): look up the
   current digest of each tag in its registry and pin it. Dependabot proposes
   a newer tag, but not reliably a rebuild under the same one, and the Debian
   fixes in `python:3.14-slim` arrive as exactly that.
2. Bump `version` in `pyproject.toml`, then `uv lock` and `uv sync --extra dev`
   (the packaging tests read the *installed* metadata). Let
   `tests/test_packaging.py` name every stale version example instead of
   hunting for them by eye.
3. Close `[Unreleased]` in `CHANGELOG.md` as `[X.Y.Z] - <date>` and add the
   compare links.
4. After the squash merge: annotated tag `vX.Y.Z`, push it, then
   `gh release create vX.Y.Z --verify-tag` with the changelog section as the
   notes. Publishing the release is what triggers `publish.yml`. Both of
   its jobs stop first when the tag is not `v` plus the version in
   `pyproject.toml` (`.github/scripts/tag_matches_version.py`), and a
   pre-release leaves `latest` where it is.
5. **Check what shipped, not the build.** The three ghcr tags (`X.Y.Z`, `X.Y`,
   `latest`) of `benethos-yahoo-finance-mcp` must carry the same
   `org.opencontainers.image.revision` annotation, and during the 0.7 line
   the old name `yahoo-finance-mcp` the same digest, the versions *inside* the image must be what the lockfile says
   (`docker run --rm --entrypoint python <image> -c "import
   importlib.metadata as m; print(m.version('mcp'))"`), and PyPI's simple
   index with a cache-buster must list the version — the JSON API reports the
   old one for minutes after an upload.
