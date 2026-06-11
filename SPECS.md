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
| `server.py` | FastMCP instance, tool definitions (signatures + docstrings), `main()`. |
| `client.py` | All direct yfinance usage; caching; error normalization. |
| `formatting.py` | Convert pandas/yfinance output to compact, JSON-safe values. |
| `errors.py` | `ToolError`, `SymbolNotFoundError`, `RateLimitError`. |

## 4. Transport & runtime

- **Transport:** stdio. stdout carries JSON-RPC only; **all logging goes to
  stderr** (`logging.basicConfig(stream=sys.stderr)`).
- **Entry points:** `python -m yahoo_finance_mcp.server` or the
  `yahoo-finance-mcp` console script.
- **Python:** 3.11+ (developed/verified on 3.14).

## 5. Data source rules

- Single source: `yfinance`. No other provider, no direct HTTP scraping.
- `Ticker` objects are cached in-memory for `_TICKER_TTL` (60 s) to coalesce
  bursts of related calls and reduce rate-limit risk.
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

## 9. Error handling

- Expected failures raise a `ToolError` subclass with a concise message
  (surfaced to the client; never a raw traceback).
  - `SymbolNotFoundError` — unknown symbol / empty result.
  - `RateLimitError` — Yahoo throttling (`YFRateLimitError` is mapped to it via
    `client._wrap_upstream`).
- All upstream yfinance exceptions are normalized through `_wrap_upstream`,
  which preserves operation-specific context for non-rate-limit errors.

## 10. Testing

- Unit tests mock `yfinance` and run **offline** (`tests/test_client.py`,
  `tests/test_formatting.py`).
- `tests/smoke.py` is an ad-hoc **live** check against Yahoo; it is not part of
  the pytest suite (no `test_*` functions, so it is not collected).
- CI (GitHub Actions) runs `pytest` on Python 3.11-3.13.

## 11. Future work (not yet implemented)

- Multi-symbol batch for `get_quote`.
- Persistent caching (`requests-cache`) with tiered TTLs.
- Input validation of `period`/`interval`/`freq` against known value sets.
- Configurable log level via environment variable.
