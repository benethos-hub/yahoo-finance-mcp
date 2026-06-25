# Specification — Yahoo Finance MCP Server

## 1. Purpose

An [MCP](https://modelcontextprotocol.io) server that gives MCP clients (e.g.
Claude Desktop) read-only access to Yahoo Finance market data. Data is sourced
through the [`yfinance`](https://github.com/ranaroussi/yfinance) library, which
talks to Yahoo's unofficial endpoints.

## 2. Scope

**In scope:** quotes, historical OHLCV, company profile/fundamentals, dividends
and splits, news, analyst recommendations, options chains, and symbol lookup by
name / ticker / ISIN.

**Out of scope (non-goals):** placing trades, real-time streaming, portfolio
persistence, authentication/paid data feeds, write operations of any kind.

## 3. Architecture

```
MCP client (Claude)  --stdio/JSON-RPC-->  server.py (FastMCP)
                                              |
                          +-------------------+--------------------+
                          v                   v                    v
                     (tool funcs)         client.py           formatting.py
                                     (yfinance wrapper      (DataFrame/dict ->
                                      + TTL cache)           compact JSON)
                                              |
                                          yfinance --> query1/2.finance.yahoo.com
```

| Module | Responsibility |
|--------|----------------|
| `server.py` | FastMCP instance, tool definitions (signatures + docstrings), CLI/`main()`. |
| `__main__.py` | Enables `python -m yahoo_finance_mcp` (delegates to `server.main`). |
| `client.py` | All direct yfinance usage; ticker cache; error normalization. |
| `cache.py` | Persistent result cache (SQLite) with per-tool TTLs. |
| `formatting.py` | Convert pandas/yfinance output to compact, JSON-safe values. |
| `errors.py` | `ToolError`, `SymbolNotFoundError`, `RateLimitError`. |

## 4. Transport & runtime

- **Transport:** selectable via `--transport`:
  - `stdio` (default) — local subprocess for Claude Desktop and similar.
  - `streamable-http` / `sse` — standalone, network-reachable HTTP service.
- **Logging:** always to stderr (`logging.basicConfig(stream=sys.stderr)`), so
  under stdio stdout carries JSON-RPC only.
- **CLI flags:** `--transport`, `--host` (default 127.0.0.1), `--port`
  (default 8000), `--path` (default `/mcp`, `/sse` for sse), `--log-level`.
  Host/port/path apply to the HTTP transports only; for stdio they are ignored.
- **Environment:** every CLI flag has an env-var equivalent (CLI > env >
  default): `YF_MCP_TRANSPORT`, `YF_MCP_HOST`, `YF_MCP_PORT`, `YF_MCP_PATH`,
  `YF_MCP_LOG_LEVEL`, and the cache vars `YF_MCP_CACHE`, `YF_MCP_CACHE_DIR`,
  `YF_MCP_CACHE_TTL_<NAME>`.
- **Entry points:** `python -m yahoo_finance_mcp` or the `yahoo-finance-mcp`
  console script.
- **Python:** 3.11+ (developed/verified on 3.14).
- **HTTP security:** the HTTP transports have no built-in auth; bind to
  `0.0.0.0` only on trusted networks and front them with a proxy/auth layer.
- **Deployment:** a `Dockerfile` (multi-stage, non-root, healthcheck;
  dependencies installed reproducibly from `uv.lock` via uv) and a
  `compose.yaml` host the server over streamable-HTTP on port 8000. The image
  is configured entirely via env vars (no default CMD args) and persists its
  cache to a `/cache` volume.

## 5. Data source rules

- Single source: `yfinance`. No other provider, no direct HTTP scraping.
- Two cache layers: `Ticker` objects are cached in-memory for `_TICKER_TTL`
  (60 s) to coalesce bursts within a process; successful tool **results** are
  cached persistently with per-tool TTLs (see §8a). requests-cache is **not**
  usable here — yfinance uses curl_cffi and rejects caching sessions — so the
  result cache operates on our normalized output, not on HTTP responses.
- Symbol resolution (name / ticker / ISIN) uses `yfinance.Search`; the same
  endpoint handles all three input kinds.

## 6. Symbol model

- All `get_*` tools accept a **Yahoo Finance symbol** only (e.g. `AAPL`,
  `SAP.DE`). They do **not** auto-resolve names/ISINs (Variant A).
- Callers resolve names/ISINs to a symbol via `search` first.

## 7. Tools

All tools are read-only. `symbol` always means a Yahoo ticker.

| Tool | Inputs | Output (shape) |
|------|--------|----------------|
| `search` | `query` (name/ticker/ISIN), `limit` 1-25 (=8) | list of `{symbol, name, exchange, type, sector, industry}` |
| `get_quote` | `symbol` | `{symbol, currency, exchange, quoteType, lastPrice, previousClose, open, dayHigh, dayLow, lastVolume, marketCap, 50/200d avg, yearHigh/Low, yearChange}` |
| `get_history` | `symbol`, `period` (=1mo), `interval` (=1d), `start?`, `end?` | `{symbol, interval, period, start, end, count, truncated, rows[]}` (OHLCV; ≤250 rows, tail kept) |
| `get_company_info` | `symbol` | curated profile + key statistics |
| `get_financials` | `symbol`, `statement` (income/balance/cashflow), `freq` (annual/quarterly) | `{symbol, statement, freq, rows[]}` (rows = line items, columns = periods) |
| `get_dividends` | `symbol` | `{symbol, dividends[], splits[]}` |
| `get_news` | `symbol`, `limit` 1-30 (=10) | `{symbol, count, articles[{title, summary, publisher, published, url}]}` |
| `get_recommendations` | `symbol` | `{symbol, price_targets, recommendation_trend[]}` |
| `get_options` | `symbol`, `expiration?` | without `expiration`: `{symbol, expirations[]}`; with it: `{symbol, expiration, calls[], puts[]}` |

### Parameter descriptions

Every tool parameter carries a human-readable description and constraints via
`Annotated[..., Field(description=..., ge=..., le=...)]` so the client receives
a precise input schema (including enumerations like valid `period`/`interval`
values).

## 8. Output format

- Default output is **compact JSON** (JSON-safe dicts/lists).
- `formatting.to_jsonable` normalizes `NaN`/`inf` -> `null`, `Timestamp`/
  `datetime` -> ISO-8601 string, numpy scalars -> native, and recurses through
  containers.
- Tabular results are row-capped (`MAX_ROWS = 250`, tighter per tool) to stay
  within the client's token budget; truncation keeps the most recent rows.

## 8a. Result cache (`cache.py`)

- Caches the **normalized tool results** (not HTTP responses) in a SQLite file
  so they survive restarts; each tool category has its own TTL.
- Cache names (the `<NAME>` in `--cache-ttl <NAME>=<SECONDS>` /
  `YF_MCP_CACHE_TTL_<NAME>`) and default TTLs:

  | Name | Tool | Default TTL |
  |------|------|-------------|
  | `quote` | `get_quote` | 30 s |
  | `history` | `get_history` | 10 min |
  | `news` | `get_news` | 10 min |
  | `options` | `get_options` | 10 min |
  | `search` | `search` | 1 h |
  | `company_info` | `get_company_info` | 6 h |
  | `dividends` | `get_dividends` | 6 h |
  | `recommendations` | `get_recommendations` | 6 h |
  | `financials` | `get_financials` | 24 h |
- **Opt-in: off by default.** Within a single process yfinance already reuses
  identical requests, so the cache mainly helps across restarts and as
  rate-limit protection; enable it with `--cache` / `YF_MCP_CACHE=1`.
- Disabled until `configure()` is called (which `server.main` does), so
  importing the package or calling client functions in tests/library use does
  not touch disk unless caching is explicitly enabled.
- Config precedence CLI > env > default: `--cache/--no-cache` (`YF_MCP_CACHE`),
  `--cache-dir` (`YF_MCP_CACHE_DIR`), `--cache-ttl <NAME>=<SECONDS>`
  (`YF_MCP_CACHE_TTL_<NAME>`). A TTL of `0` bypasses caching for that tool.
- Only successful, non-empty returns are cached; exceptions propagate and are
  never cached, and empty results (e.g. a search with no matches) are not
  pinned for the TTL.

## 9. Error handling

- Expected failures raise a `ToolError` subclass with a concise message
  (surfaced to the client; never a raw traceback).
  - `SymbolNotFoundError` — unknown symbol / empty result.
  - `RateLimitError` — Yahoo throttling (`YFRateLimitError` is mapped to it via
    `client._wrap_upstream`).
- All upstream yfinance exceptions are normalized through `_wrap_upstream`,
  which preserves operation-specific context for non-rate-limit errors.

## 10. Testing

- Unit tests mock `yfinance` and run **offline**, covering the client wrapper
  and error normalization, formatting, the cache, CLI/transport selection, and
  tool registration/schema (`tests/test_client.py`, `test_formatting.py`,
  `test_cache.py`, `test_cli.py`, `test_server.py`).
- `tests/smoke.py` is an ad-hoc **live** check against Yahoo; it is not part of
  the pytest suite (no `test_*` functions, so it is not collected).
- Quality gates: ruff (lint + format), mypy (type check), and a coverage floor
  of 80% (currently ~90%).
- CI (GitHub Actions): a `lint` job (ruff + mypy) and a `test` matrix running
  `pytest` with coverage on Python 3.11-3.13, plus a `docker` job that builds
  the image and smoke-tests that the container serves HTTP. All jobs install
  dependencies via uv from `uv.lock` (`uv sync --frozen`). Dependabot keeps pip
  and Actions dependencies updated.

## 11. Future work (not yet implemented)

- Multi-symbol batch for `get_quote`.
- Input validation of `period`/`interval`/`freq` against known value sets.
- Stale-on-error: serve an expired cache entry when Yahoo is rate limiting.
