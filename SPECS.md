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
| `get_financials` | `symbol`, `statement` (income/balance/cashflow), `freq` (annual/quarterly/ttm — ttm income/cashflow only) | `{symbol, statement, freq, rows[]}` (rows = line items, columns = periods) |
| `get_dividends` | `symbol` | `{symbol, dividends[], splits[]}` |
| `get_news` | `symbol`, `limit` 1-30 (=10) | `{symbol, count, articles[{title, summary, publisher, published, url}]}` |
| `get_recommendations` | `symbol` | `{symbol, price_targets, recommendation_trend[]}` |
| `get_options` | `symbol`, `expiration?` | without `expiration`: `{symbol, expirations[]}`; with it: `{symbol, expiration, calls[], puts[]}` |
| `get_earnings` | `symbol`, `limit` 1-50 (=12) | `{symbol, earnings_dates[], earnings_history[]}` (equity-only) |
| `get_estimates` | `symbol` | `{symbol, earnings_estimate[], revenue_estimate[], eps_trend[], eps_revisions[], growth_estimates[]}` (equity-only) |
| `get_upgrades_downgrades` | `symbol`, `limit` 1-100 (=50) | `{symbol, changes[]}` (rating changes, newest first; equity-only) |
| `get_holders` | `symbol`, `limit` 1-100 (=25) | `{symbol, major_holders[], institutional_holders[], mutualfund_holders[]}` (top holders first; equity-only) |
| `get_insider_activity` | `symbol`, `limit` 1-100 (=50) | `{symbol, transactions[], purchases_summary[], roster[]}` (transactions newest first; equity-only) |
| `get_sec_filings` | `symbol`, `limit` 1-100 (=25) | `{symbol, count, filings[{date, type, title, url, exhibits}]}` (equity-only) |
| `get_calendar` | `symbol` | `{symbol, calendar{}}` (next earnings/dividend dates + estimate ranges; equity-only) |
| `get_shares` | `symbol`, `start?`, `end?`, `limit` 1-250 (=50) | `{symbol, count, shares[{date, shares}]}` (most recent kept) |
| `get_fund_data` | `symbol`, `limit` 1-100 (=25) | `{symbol, description, fund_overview, asset_classes, sector_weightings, top_holdings[]}` (fund/ETF-only) |

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
  | `earnings` | `get_earnings` | 6 h |
  | `estimates` | `get_estimates` | 6 h |
  | `upgrades_downgrades` | `get_upgrades_downgrades` | 6 h |
  | `insider_activity` | `get_insider_activity` | 6 h |
  | `sec_filings` | `get_sec_filings` | 6 h |
  | `calendar` | `get_calendar` | 6 h |
  | `financials` | `get_financials` | 24 h |
  | `holders` | `get_holders` | 24 h |
  | `shares` | `get_shares` | 24 h |
  | `fund_data` | `get_fund_data` | 24 h |
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

## 12. Tool expansion plan

Goal: expose every **working** yfinance method as an MCP tool. "Working" was
verified empirically (probed live on a stock `AAPL`, an ETF `SPY`, and a crypto
pair `BTC-USD`); only methods that return real data are in scope. Availability
is symbol-dependent (equity fields are empty for ETFs/crypto and vice versa) —
tools surface that as an empty result, not an error.

### Verified data sources (probe results)

- **Equity-only (data for AAPL, empty for SPY):** `upgrades_downgrades`,
  `recommendations_summary`, `analyst_price_targets`, `earnings_estimate`,
  `revenue_estimate`, `eps_trend`, `eps_revisions`, `growth_estimates`,
  `earnings_history`, `get_earnings_dates`, `major_holders`,
  `institutional_holders`, `mutualfund_holders`, `insider_purchases`,
  `insider_roster_holders`, `insider_transactions`, `sec_filings`, `calendar`,
  `ttm_income_stmt`, `ttm_cashflow`, `valuation`, `get_shares_full`.
- **Fund/ETF:** `funds_data`.
- **Any symbol:** `history_metadata`, `isin`.
- **Crypto (`BTC-USD`):** the existing core paths work — `history`,
  `fast_info`/`info` (rich), `history_metadata`, `isin` — so `get_quote`,
  `get_history`, and `get_company_info` already cover crypto. All
  equity-specific methods (analysts, holders, earnings, financials, calendar)
  are empty, so the new tools return empty for crypto.
- **Excluded — upstream empty for all probed symbols:** `sustainability` (ESG),
  `capital_gains`.
- **Out of scope (non-goals, §2):** `live`/`WebSocket` (streaming), `Auth`.
- **Dependency note:** `get_earnings_dates` requires `lxml` (not currently a
  dependency); adding the earnings tool means adding `lxml` to `dependencies`.

### Proposed new tools (grouped, not one-per-method)

Grouping keeps the tool list legible for the LLM. Each takes a `Symbol`, is
wrapped via `_wrap_upstream`, cached with a per-tool TTL, and row-capped.

| Tool | Backed by | Notes |
|------|-----------|-------|
| `get_earnings` | `get_earnings_dates`, `earnings_history` | upcoming + historical EPS estimate/actual/surprise; **needs `lxml`** |
| `get_estimates` | `earnings_estimate`, `revenue_estimate`, `eps_trend`, `eps_revisions`, `growth_estimates` | forward analyst estimates |
| `get_upgrades_downgrades` | `upgrades_downgrades` | analyst rating changes (large; row-capped) |
| `get_holders` | `major_holders`, `institutional_holders`, `mutualfund_holders` | ownership breakdown |
| `get_insider_activity` | `insider_transactions`, `insider_purchases`, `insider_roster_holders` | insider trading |
| `get_sec_filings` | `sec_filings` | recent filings |
| `get_calendar` | `calendar` | next earnings/ex-div dates |
| `get_shares` | `get_shares_full` | shares outstanding over time |
| `get_fund_data` | `funds_data` | holdings/sector weights — ETFs & funds |
| extend `get_financials` | `ttm_income_stmt`, `ttm_cashflow` | add a `ttm` frequency (income/cashflow only; no `ttm_balance_sheet` upstream) |

Excluded from tools: `sustainability`, `capital_gains` (empty). `isin`/
`history_metadata` are minor and may be folded into existing tools rather than
new ones. The planned `get_recommendations` extension was **dropped**:
`recommendations_summary` is identical to `recommendations`, which the existing
tool already returns as `recommendation_trend`.

### Module-level (later phase, larger)

`Sector` / `Industry` / `Market` / `Lookup` browsing, the screener
(`screen` / `EquityQuery`), and multi-symbol (`download` / `Tickers`, which also
covers the §11 multi-symbol-quote item) are a separate, larger category — not
part of the first per-symbol tool batch.

### Process

Per the working agreement: **plan (this section) → implement → test → update
docs**. Each tool follows the established pattern (client.py logic +
`@cache.cached`, server.py `@mcp.tool()` with `Annotated` Fields, FakeTicker
unit tests, and a smoke-test entry). Land in reviewable PRs (CI must stay
green).

### Phase status

- **Phase 1 — done:** `get_earnings`, `get_estimates`, `get_upgrades_downgrades`
  (added `lxml`).
- **Phase 2 — done:** `get_holders`, `get_insider_activity`, `get_sec_filings`,
  `get_calendar`.
- **Phase 3 — done:** `get_financials` gained a `ttm` frequency, plus new
  `get_shares` (`get_shares_full`) and `get_fund_data` (`funds_data`). The
  `get_recommendations`/`recommendations_summary` extension was dropped as
  redundant (see above).
- **Later (larger):** module-level browsing/screener and multi-symbol tools.
