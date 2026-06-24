# Working guidelines for Claude

How to work in this repository. Read this before making changes. See
[SPECS.md](SPECS.md) for what the project is and does.

## Golden rules

1. **Virtual environment only.** Never use the global Python/pip. Always invoke
   the project venv interpreter:
   - `.\.venv\Scripts\python.exe ...` (PowerShell)
   - `.venv/Scripts/python.exe ...` (Bash on Windows)
   Install deps into the venv (`-e .` or `-e ".[dev]"`).
2. **English in the repo.** All code, comments, docstrings, and docs are in
   English. (Conversation with the user may be in German.)
3. **stdio is sacred.** stdout carries the MCP JSON-RPC stream. Never `print()`
   to stdout from server/library code; log to **stderr** only.
4. **Read-only domain.** This server only reads market data. Do not add write,
   trade, or auth operations (see non-goals in SPECS.md).

## Environment

- Windows, PowerShell or Bash. Python 3.11+ (developed on 3.14).
- Set up: `py -m venv .venv` then `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`.
- Run the server (stdio): `.\.venv\Scripts\python.exe -m yahoo_finance_mcp`.
  For HTTP transports and Docker/Compose hosting, see the README
  (`--transport`, `Dockerfile`, `compose.yaml`).

## Project layout

```
src/yahoo_finance_mcp/
  server.py       # FastMCP instance + @mcp.tool() definitions + CLI main()
  __main__.py     # enables `python -m yahoo_finance_mcp` (delegates to main())
  client.py       # all yfinance access, in-memory ticker cache, error mapping
  cache.py        # opt-in persistent result cache (SQLite) with per-tool TTLs
  formatting.py   # pandas/yfinance -> compact JSON-safe values
  errors.py       # ToolError / SymbolNotFoundError / RateLimitError
tests/            # mocked, offline unit tests (+ live smoke.py, not collected)
```

Keep the layers separate: **tools in `server.py` stay thin** and delegate to
`client.py`. Put any new yfinance call in `client.py`, not in a tool function.

## How to add or change a tool

1. Add the data-fetching logic to `client.py`. Wrap every yfinance call in
   `try/except` and route failures through `_wrap_upstream(exc, "...")` so rate
   limits map to `RateLimitError` and other errors keep context. Raise
   `SymbolNotFoundError(symbol)` on empty results. Decorate the function with
   `@cache.cached("<category>")` and add that category with a TTL to
   `cache.DEFAULT_TTLS` (the cache is opt-in; the decorator is a no-op until
   enabled).
2. Convert pandas output with `formatting.dataframe_to_records` / `to_jsonable`;
   apply a sensible `max_rows`.
3. Expose it in `server.py` with `@mcp.tool()`. The **docstring becomes the
   tool description** Claude sees — write it for an LLM caller. Give every
   parameter an `Annotated[type, Field(description=...)]` (reuse the `Symbol`
   alias for ticker arguments); add `ge`/`le` bounds for numeric limits.
4. Add unit tests in `tests/` using the `FakeTicker` pattern (mock
   `client._get_ticker` / `client.yf.Search`). Do not hit the network in tests.

## Verifying

- Tests: `.venv/Scripts/python.exe -m pytest -q` (must stay green; offline).
- Lint + format: `.venv/Scripts/python.exe -m ruff check .` and
  `.venv/Scripts/python.exe -m ruff format .` (CI checks `ruff format --check`).
- Types: `.venv/Scripts/python.exe -m mypy`.
- Coverage (CI floor 80%): `… -m pytest --cov=yahoo_finance_mcp --cov-fail-under=80`.
- Inspect what the client sends to Claude (no Desktop restart needed):
  ```
  .venv/Scripts/python.exe -c "import asyncio,json;from yahoo_finance_mcp.server import mcp;print(json.dumps([t.model_dump() for t in asyncio.run(mcp.list_tools())],indent=2,default=str))"
  ```
- Live check against Yahoo: `.venv/Scripts/python.exe tests/smoke.py`.
- After changing tool signatures/docstrings, **fully restart Claude Desktop**
  (quit from the tray, not just close the window) to reload the tools.

## Conventions

- Type hints everywhere; `from __future__ import annotations` at the top.
- Surface expected failures as `ToolError` subclasses with concise messages —
  never leak a raw traceback to the client.
- Default tool output is compact JSON; keep responses small (row caps) to
  respect the client's token budget.

## Git / commits

- Commit only when the user asks. Use clear, descriptive messages.
- Do not commit `.venv/`, `__pycache__/`, or `*.egg-info/` (already gitignored).
