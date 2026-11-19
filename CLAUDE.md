# Working guidelines for Claude

How to work in this repository. Read this before making changes. See
[docs/CONCEPT.md](docs/CONCEPT.md) for what the project is and does, and
[docs/concept/](docs/concept/) for each topic.

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
   non-goals in docs/CONCEPT.md). Guarding this server's own HTTP port is a different
   thing and is allowed — see `transport/http.py`.

## Environment

- Windows, PowerShell or Bash. Python 3.11-3.15 (3.11.5 at least, developed
  on 3.15).
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
  prompts/        # the prompts a client offers, recipes in plain text that chain the tools
    _base.py      #   Prompt (the abstract base), Symbol, RESOLVE, RULES
                  #   one module per prompt, named like it, dividend_calendar.py the one
                  #   taking share counts, which reach no tool and no log line
  tools/          # the tools a client sees, one module per subject, thin
    _base.py      #   Symbol, READ_ONLY, register_tool (adds the log line)
    status.py     #   server_status: plain text, no log line, asks Yahoo nothing
  yahoo/          # all yfinance access, the eight subjects of tools/, status has no twin
    tickers.py    #   get_ticker, upstream(), normalize(), last_answer()
  cache.py        # opt-in persistent result cache (SQLite) with per-tool TTLs
  formatting.py   # pandas/yfinance -> compact JSON-safe values
  logbook/        # every log line as a function, the one stderr handler
    _describe.py  #   what a line may carry: printable(), subject(), size()
    output.py     #   the one stderr handler, other libraries' lines made printable
    formats.py    #   how a line looks, plain or in colour
    access.py     #   uvicorn's request log, without the query string
    lifecycle.py  #   the lines: starting, the guard, settings ignored
    calls.py      #   the lines: one per tool call, arguments refused
    cache.py      #   the lines: the result cache's state and failures
    upstream.py   #   the lines: rate limits, a missing constant
  transport/      # stdio.py, http.py (Host allow-list + optional bearer guard)
  errors.py       # ToolError / SymbolNotFoundError / RateLimitError
  py.typed        # PEP 561 marker, without it the annotations reach nobody
tests/            # mocked, offline unit tests (+ live smoke.py, not collected), FakeTicker in fakes.py
  yahoo/          #   one test file per yahoo module, test_tickers.py included,
                  #   plus the cross-module test_empty_answers.py
docs/
  CONCEPT.md      # what the server is for and its scope, and where each section is
  concept/        #   one file per topic, the sections under their numbers
  RELEASING.md    # the steps of a release, in order
containers/
  README.md       # hosting with Docker and Compose
  images/yahoo-finance-mcp/Dockerfile   # build context: the repository root
  production/     # compose.yaml + Caddyfile + .env.example, the published image
  development/    # compose.yaml, built from the checkout, port 8001
.github/workflows/
  ci.yml          # brand, lint, test, lowest-versions, audit, coverage-badge, codeql, dockerfile-lint (the organisation's workflows), fresh-install, docker (HTTP and stdio smoke tests)
  publish.yml     # PyPI, ghcr, .mcpb bundle, MCP Registry on a published release, through the organisation's actions
  freshness.yml   # daily and after each Publish run: the organisation's freshness report with its newest and index jobs, do the newest versions allowed still work, two issues
  codeql.yml      # weekly: the organisation's CodeQL analysis, the security and the quality queries on code nobody changed, findings under Security
.github/dependabot.yml   # weekly proposals for uv, the actions and the Dockerfile
.github/ISSUE_TEMPLATE/  # the bug report form, its version example read by test_packaging.py
.github/publish/   # one folder per place a release is listed, read by publish.yml
  mcp-registry/   # server.json (the entry, its bundle hash filled in at release)
  mcpb/            # Claude Desktop bundles: manifest.json, server.py, build.py (pinned, and --auto-update from it),
                   #   sync_manifest.py (writes the manifest's tools and prompts from the server)
assets/           # render_icon.py, the architecture diagram it draws, old icon copies
  brand/          # icon.svg, and icon.png (512x512) and social-preview.png (1280x640) exported from it
SECURITY.md       # how to report a vulnerability, and what the server guards
glama.json        # names the maintainers who may claim the Glama listing
.githooks/        # pre-commit: refuses staged tokens, keys and local state files
```

The brand folder follows the rules of the benethos-hub organisation, kept in
its `.github` repository. `assets/render_icon.py` writes both PNGs there, and
the `brand` job in CI fails when one is missing, has the wrong size or is older
than the SVG. The icon files directly in `assets/` are the copies from before
the brand folder. The MCP Registry entries up to 0.8.5 point at them on main,
so they stay until those entries no longer matter.

Keep the layers separate: **tools stay thin** and hand their arguments to the
yahoo function of the same name. Put any new yfinance call in `yahoo/`, never
in a tool. `tests/test_layers.py` holds the import table (which unit imports
which, checked in both directions), so a new module needs a line there and a
new or dropped import changes its row. The same file pins every library to
its one home module and keeps the environment out of every module but
`settings.py`, `NO_COLOR` in `logbook/formats.py` excepted. Packages are entered only through their `__init__.py`, so a
new public name goes into its `__all__`.

**Logging goes through `logbook/`.** No other module imports `logging`. A new
line is a function in `logbook/lifecycle.py`, `calls.py`, `cache.py` or
`upstream.py`, taking parameters from the vocabulary in
`tests/test_logbook_catalog.py`, and it never carries a search query, the
token, a URL's query string, Yahoo's data or an error's text (see CONCEPT §4).
A tool writes no line of its own, `register_tool` writes one per call.
`server_status` is registered past it and writes none, see CONCEPT §4.
`logbook/formats.py` reads `NO_COLOR` from the environment itself, the one
exception to `settings.py` being the only module that does.

## How to add or change a tool

1. Add the data-fetching logic to the matching module in `yahoo/`. Put every
   yfinance call inside
   `with tickers.upstream("Failed to load ... for {symbol!r}"):`, which routes
   failures through `wrap_upstream` so rate limits map to `RateLimitError`
   and other errors keep context. An exception that means "no such data for
   this symbol" goes in its `not_found=` and becomes a `SymbolNotFoundError`.
   Get the ticker with `tickers.get_ticker`,
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
   module's `register()` with a short title, which a client shows a person in
   place of the name (a test wants one per tool, no two alike). The bundle
   manifest in `.github/publish/mcpb/` lists every tool with the first
   sentence of its docstring. `uv run python
   .github/publish/mcpb/sync_manifest.py` writes that list from the server,
   and `tests/test_mcpb.py` fails until it has run.
   `register_tool` gives it the shared
   `readOnlyHint`/`openWorldHint` pair every tool carries (a test asserts it
   for all of them, `server_status` excepted) and its log line. The
   **docstring becomes the tool description** Claude sees — write it for an
   LLM caller, and leave allowed values to the parameter descriptions rather
   than repeating them. Say when to use the tool and name the sibling to
   take instead (`get_quotes` for several symbols, `get_fund_data` for an
   ETF). Glama's tool definition score weighs exactly this, and it was what
   the three weakest descriptions lacked.
   Give every parameter an `Annotated[type, Field(description=...)]` (reuse
   the `Symbol` alias for ticker arguments, and `Methodology` in
   `tools/analysts.py` for the EPS basis); add `ge`/`le` bounds for numeric
   limits. A row cap is called `limit`, in the tool and in the yahoo function.
   Its ceiling is a `*_MAX` constant in the yahoo module, exported from
   `yahoo/__init__.py` and used as the schema's `le`, and
   `tests/test_server.py` holds every number a description names to its
   constant.
4. Add unit tests in `tests/yahoo/test_<module>.py` using the `FakeTicker`
   pattern (the `patch_ticker` fixture patches `tickers.get_ticker`, or patch
   `tickers.yf.Search`). Do not hit the network in tests.

## How to add or change a prompt

1. Add a module to `prompts/` named like the prompt, with one subclass of
   `Prompt` from `_base.py`. Set `name` (the module's name) and `title`, and
   write `render`: its parameters become the arguments, each with an
   `Annotated[str, Field(description=...)]` (reuse `Symbol`), its docstring
   the one-line description. Every argument is a string, a later one may
   be optional. **`render` is a plain template:** an optional argument
   defaults to `""`, goes into the text as it came, and the text says in
   words what an empty one means. No `or` default and no `if` that picks
   another sentence, so the manifest's text with the arguments put in is
   exactly what a client gets. `tests/test_prompts.py` checks it for every
   prompt. Both bundles set `prompts_generated` and `tools_generated`,
   since Claude Desktop's own check keeps the placeholder of an empty
   argument and refuses every such prompt (CONCEPT §7a). Do not take the
   flags out of the pinned manifest.
2. Write the text for the model. Name tools and the fields they return in
   backticks, start with `RESOLVE` where an argument may be a company name,
   and end a data recipe with `RULES`. `tests/test_prompts.py` fails on a
   backticked name that is neither a tool nor listed there as a field.
3. Add an instance to `_PROMPTS` in `prompts/__init__.py`, whose order is the
   order a client lists them in. After adding or changing a prompt, run
   `uv run python .github/publish/mcpb/sync_manifest.py`, which writes the
   manifest's `prompts` from the server, `tests/test_mcpb.py` fails until
   it has.
4. A prompt asks Yahoo nothing and writes no log line. One that takes
   personal data says so in README, CONCEPT §7a and SECURITY.md and keeps it
   out of every tool call, as `dividend_calendar.py` does with share counts.
   Examples and tests use invented values, never a real portfolio.

## Verifying

Commands use uv (recommended); the venv interpreter forms
(`.venv/Scripts/python.exe -m ...`) work too.

- Tests: `uv run pytest -q` (must stay green; offline).
- Lint + format: `uv run ruff check .` and `uv run ruff format .`
  (CI checks `ruff format --check`).
- Types: `uv run mypy`.
- Coverage (CI floor 80%, measured in `test / Python 3.15` only, the other
  versions run without it):
  `uv run pytest --cov=benethos_yahoo_finance_mcp --cov-fail-under=80`.
- Inspect what the client sends to Claude (no Desktop restart needed):
  ```
  uv run python -c "import asyncio,json;from benethos_yahoo_finance_mcp.server import mcp;print(json.dumps([t.model_dump() for t in asyncio.run(mcp.list_tools())],indent=2,default=str))"
  ```
- Live check against Yahoo: `uv run python tests/smoke.py`.
- When Claude Desktop runs the server from this checkout, `uv sync` on
  Windows cannot replace the server's `.exe` in `.venv` (os error 32). Run
  the checks in a second environment instead, with
  `UV_PROJECT_ENVIRONMENT` pointing at a folder outside the repository.
- After changing tool signatures/docstrings, **fully restart Claude Desktop**
  (quit from the tray, not just close the window) to reload the tools.

**The gates above do not cover a `yfinance` upgrade.** The unit tests mock
yfinance completely and stay green through any change in its behaviour, field
names or response shapes, and the `fresh-install` CI job only catches import
errors. Bump it on its own, run `tests/smoke.py` **before** the bump as a
baseline and again afterwards, and compare the sections. It exits with 1 when a
section or one of its lists comes back empty, but a wrong value still passes, and
with 3 when Yahoo rate-limits the run.
Without the baseline a green run afterwards cannot be told apart from Yahoo
simply having a good day.

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
- ruff's `BLE` rule is on: a bare `except Exception` carries
  `# noqa: BLE001` with its reason in the comment, and there are seven such
  places, each a deliberate fallback.
- **The concept moves with the code.** `docs/CONCEPT.md` is the overview,
  and `docs/concept/` holds one file per topic. A change that departs from
  them changes them in the same commit. The sections keep their numbers:
  "CONCEPT §4" in the code or in a document names section 4, and the
  overview's table leads to it.
- **A document is named for its subject.** One that stands directly in
  `docs/` is written in capitals: `CONCEPT.md`, `RELEASING.md`. One that
  grows too long becomes an overview, and its parts go into a folder of the
  same name in lowercase beside it: `CONCEPT.md` and `concept/`. A part is
  named in lowercase with hyphens. It starts with the name of its document,
  as in `# Concept: tools`, and a line that leads back to the overview. The
  overview lists every part in a table. `README.md`, `CHANGELOG.md`,
  `SECURITY.md` and `CLAUDE.md` stay where GitHub and the tools look for
  them. `tests/test_docs.py` checks the links and the parts.

## Git / commits

- Commit only when the user asks. Use clear, descriptive messages.
- Every CI job must pass before a merge, and the branch protection of main
  requires each of them. A new job is added to the required checks once it
  has run. `brand`, `lint`, `test`, `lowest-versions` and `audit` call the
  reusable workflows of benethos-hub/.github at main, so their checks are
  named `<job> / <name>`, for example `test / Python 3.15`. Renaming such a
  job renames its checks, and the required ones have to follow.
  `coverage-badge`, `codeql` and `dockerfile-lint` are the exceptions.
  `coverage-badge` runs on a push to main only, to publish the coverage
  badge on the `badges` branch. `codeql` and `dockerfile-lint` file what
  they find under Security, Code scanning, where it is read and fixed or
  dismissed with a reason, so a required check would add nothing. None of
  the three is one.
- `lowest-versions` installs the oldest versions `pyproject.toml` allows,
  runs the tests and audits those versions. When it goes red, raise the lower
  bound it names in the same pull request. `audit` checks every version in
  `uv.lock` against PyPI and OSV. A vulnerability without a fix yet is waived
  by its ID with `ignore-vulns`, in both jobs alike.
- Do not commit `.venv/`, `__pycache__/`, or `*.egg-info/` (already gitignored).
- The pre-commit hook in `.githooks/` refuses staged files that hold a
  token, a key or local state (an `.env`, a folder `secrets/`, the result
  cache) and staged lines that look like a credential, showing only the
  start of each. It is enabled once per clone with
  `git config core.hooksPath .githooks`. CI does not run it.
  `tests/test_pre_commit.py` runs it on each kind of line and on every
  tracked file at once. A line that must show such a form, such as an
  invented token in a test, ends with `pragma: allowlist secret`.

## Releasing

A release is its own `release/X.Y.Z` branch and PR. The steps in order, from
the refresh of every pin to what is checked after the publish:
[docs/RELEASING.md](docs/RELEASING.md).
