# Specification — Unofficial Yahoo Finance MCP Server

## 1. Purpose

An [MCP](https://modelcontextprotocol.io) server that gives MCP clients (e.g.
Claude Desktop) read-only access to Yahoo Finance market data. Data is sourced
through the [`yfinance`](https://github.com/ranaroussi/yfinance) library, which
talks to Yahoo's unofficial endpoints.

## 2. Scope

**In scope:** quotes (single and multi-symbol), historical OHLCV, company
profile and fundamentals (financial statements incl. trailing-twelve-month),
dividends and splits, shares outstanding, news, analyst recommendations,
estimates and rating changes, earnings, holders and insider activity, SEC
filings, the corporate calendar, options chains, fund/ETF profiles,
sector/industry browsing, and symbol lookup by name / ticker / ISIN.

**Out of scope (non-goals):** placing trades, real-time streaming, portfolio
persistence, authentication/paid data feeds, write operations of any kind.

## 3. Architecture

```
MCP client (Claude)  --stdio/JSON-RPC-->  server.py (MCPServer)
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
| `server.py` | MCPServer instance, tool definitions (signatures + docstrings), CLI/`main()`. |
| `__main__.py` | Enables `python -m benethos_yahoo_finance_mcp` (delegates to `server.main`). |
| `client.py` | All direct yfinance usage, ticker cache, error normalization. |
| `cache.py` | Persistent result cache (SQLite) with per-tool TTLs. |
| `formatting.py` | Convert pandas/yfinance output to compact, JSON-safe values. |
| `errors.py` | `ToolError`, `SymbolNotFoundError`, `RateLimitError`. |
| `py.typed` | PEP 561 marker. Without it a type checker skips the installed package and every annotation in it goes unused. |

## 4. Transport & runtime

- **Transport:** selectable via `--transport`:
  - `stdio` (default) — local subprocess for Claude Desktop and similar.
  - `streamable-http` / `sse` — standalone, network-reachable HTTP service.
- **Logging:** always to stderr (`logging.basicConfig(stream=sys.stderr)`), so
  under stdio stdout carries JSON-RPC only.
- **CLI flags:** `--transport`, `--host` (default 127.0.0.1), `--port`
  (default 8000), `--path` (default `/mcp`, `/sse` for sse), `--allowed-hosts`,
  `--allowed-origins`, `--log-level`. Host/port/path/allow-list apply to the
  HTTP transports only. For stdio they are ignored.
- **Environment:** every CLI flag has an env-var equivalent (CLI > env >
  default): `YF_MCP_TRANSPORT`, `YF_MCP_HOST`, `YF_MCP_PORT`, `YF_MCP_PATH`,
  `YF_MCP_ALLOWED_HOSTS`, `YF_MCP_ALLOWED_ORIGINS`, `YF_MCP_LOG_LEVEL`, and the
  cache vars `YF_MCP_CACHE`, `YF_MCP_CACHE_DIR`, `YF_MCP_CACHE_TTL_<NAME>`.
- **Entry points:** `python -m benethos_yahoo_finance_mcp` or the
  `benethos-yahoo-finance-mcp` console script.
- **Python:** 3.11-3.14, all covered by the CI matrix.
- **HTTP security:** the HTTP transports have no built-in auth. Bind to
  `0.0.0.0` only on trusted networks and front them with a proxy/auth layer.
  The MCP HTTP transport also runs a DNS-rebinding `Host`/`Origin` guard. It is
  derived from the actual bind host and passed to `MCPServer.run()` as an
  explicit argument: a localhost bind keeps the protective localhost allow-list,
  an exposed bind accepts any `Host` unless `--allowed-hosts` /
  `--allowed-origins` narrow it (mismatches get HTTP 421). stdio has no HTTP
  surface and is handed no transport options at all.
- **Deployment:** a `Dockerfile` (multi-stage, non-root, healthcheck,
  dependencies installed reproducibly from `uv.lock` via uv) and a
  `compose.yaml` host the server over streamable-HTTP on port 8000. The image
  is configured entirely via env vars (no default CMD args) and persists its
  cache to a `/cache` volume. Compose publishes the port on **127.0.0.1 only**,
  because the server has no authentication of its own. Drop that prefix only
  behind a reverse proxy that provides one.

## 5. Data source rules

- Single source: `yfinance`. No other provider, no direct HTTP scraping.
- Two cache layers: `Ticker` objects are cached in-memory for `_TICKER_TTL`
  (60 s) to coalesce bursts within a process. Successful tool **results** are
  cached persistently with per-tool TTLs (see §8a). requests-cache is **not**
  usable here — yfinance uses curl_cffi and rejects caching sessions — so the
  result cache operates on our normalized output, not on HTTP responses.
- Symbol resolution (name / ticker / ISIN) uses `yfinance.Search`, and the same
  endpoint handles all three input kinds.

## 6. Symbol model

- All `get_*` tools pass the given `symbol` through to yfinance unchanged. The
  server itself resolves nothing (Variant A) and never assembles or rewrites a
  symbol.
- In practice that accepts both a **Yahoo ticker** (`AAPL`, `SAP.DE`) and a
  **plain ISIN** (`US0378331005`), because Yahoo resolves ISINs server-side.
  Probed 2026-08-16: all 18 symbol-taking tools return correct data for an ISIN.
  This is **observed behaviour of an unofficial endpoint, not a guarantee** — it
  did not work at all when this section was first written, and it can change
  back.
- A **company name** is not a symbol. Callers resolve one via `search` and pass
  back the `symbol` it returns.
- Every tool echoes the `symbol` it was given, uppercased, so the answer can
  always be matched to the question. `get_company_info` is the one tool that
  also learns Yahoo's resolved ticker, and reports it as `resolved_symbol` when
  it differs from the input — an ISIN in returns the ISIN plus the ticker it
  stands for.
- **WKNs resolve nowhere**, not through the tools and not through `search`
  (five probed, zero hits). Yahoo has no lookup for them.

## 7. Tools

All tools are read-only. `symbol` always means a Yahoo ticker. The two
exceptions are `get_sector` / `get_industry`, which take a sector/industry
**key** (e.g. `technology`, `semiconductors`) rather than a symbol.

| Tool | Inputs | Output (shape) |
|------|--------|----------------|
| `search` | `query` (name/ticker/ISIN), `limit` 1-25 (=8) | list of `{symbol, name, exchange, type, sector, industry}` |
| `get_quote` | `symbol` | `{symbol, currency, exchange, quoteType, lastPrice, previousClose, open, dayHigh, dayLow, lastVolume, marketCap, 50/200d avg, yearHigh/Low, yearChange}` |
| `get_quotes` | `symbols[]` (≤50) | `{count, quotes[{symbol, currency, lastPrice, previousClose, open, dayHigh, dayLow, marketCap}], not_found[], truncated}` |
| `get_history` | `symbol`, `period` (=1mo), `interval` (=1d), `start?`, `end?` | `{symbol, interval, period, start, end, count, truncated, rows[]}` (OHLCV, ≤250 rows, tail kept) |
| `get_company_info` | `symbol` | curated profile + key statistics, plus `resolved_symbol` when Yahoo resolves the input to a different ticker (i.e. for an ISIN) |
| `get_financials` | `symbol`, `statement` (income/balance/cashflow), `freq` (annual/quarterly/ttm — ttm income/cashflow only) | `{symbol, statement, freq, rows[]}` (rows = line items, columns = periods) |
| `get_dividends` | `symbol` | `{symbol, dividends[], splits[]}` |
| `get_news` | `symbol`, `limit` 1-30 (=10) | `{symbol, count, articles[{title, summary, publisher, published, url}]}` |
| `get_recommendations` | `symbol` | `{symbol, price_targets, recommendation_trend[]}` |
| `get_options` | `symbol`, `expiration?` | without `expiration`: `{symbol, expirations[]}`, with it: `{symbol, expiration, calls[], puts[]}` |
| `get_earnings` | `symbol`, `limit` 1-50 (=12) | `{symbol, earnings_dates[], earnings_history[]}` (equity-only) |
| `get_estimates` | `symbol` | `{symbol, earnings_estimate[], revenue_estimate[], eps_trend[], eps_revisions[], growth_estimates[]}` (equity-only) |
| `get_upgrades_downgrades` | `symbol`, `limit` 1-100 (=50) | `{symbol, changes[]}` (rating changes, newest first, equity-only) |
| `get_holders` | `symbol`, `limit` 1-100 (=25) | `{symbol, major_holders[], institutional_holders[], mutualfund_holders[]}` (top holders first, equity-only) |
| `get_insider_activity` | `symbol`, `limit` 1-100 (=50) | `{symbol, transactions[], purchases_summary[], roster[]}` (transactions newest first, equity-only) |
| `get_sec_filings` | `symbol`, `limit` 1-100 (=25) | `{symbol, count, filings[{date, type, title, url, exhibits}]}` (equity-only) |
| `get_calendar` | `symbol` | `{symbol, calendar{}}` (next earnings/dividend dates + estimate ranges, equity-only) |
| `get_shares` | `symbol`, `start?`, `end?`, `limit` 1-250 (=50) | `{symbol, count, shares[{date, shares}]}` (most recent kept) |
| `get_fund_data` | `symbol`, `limit` 1-100 (=25) | `{symbol, description, fund_overview, asset_classes, sector_weightings, top_holdings[]}` (fund/ETF-only) |
| `get_sector` | `key` (sector key), `limit` 1-100 (=25) | `{key, name, index_symbol, overview, top_companies[], top_etfs, top_mutual_funds, industries[]}` (module-level, not a symbol) |
| `get_industry` | `key` (industry key), `limit` 1-100 (=25) | `{key, name, index_symbol, sector_key, sector_name, overview, top_companies[], top_performing_companies[], top_growth_companies[]}` (module-level, not a symbol) |
| `get_market` | `key` (market key, =US) | `{key, status, count, indices[{symbol, shortName, fullExchangeName, marketState, price, previous close, change, change %}]}` (module-level, `status` only for `US`, null elsewhere) |

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
  within the client's token budget. Truncation keeps the most recent rows.

## 8a. Result cache (`cache.py`)

- Caches the **normalized tool results** (not HTTP responses) in a SQLite file
  so they survive restarts, and each tool category has its own TTL.
- Cache names (the `<NAME>` in `--cache-ttl <NAME>=<SECONDS>` /
  `YF_MCP_CACHE_TTL_<NAME>`) and default TTLs:

  | Name | Tool | Default TTL |
  |------|------|-------------|
  | `quote` | `get_quote` | 30 s |
  | `quotes` | `get_quotes` | 30 s |
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
  | `sector` | `get_sector` | 24 h |
  | `industry` | `get_industry` | 24 h |
  | `market` | `get_market` | 60 s |
- **Opt-in: off by default.** Within a single process yfinance already reuses
  identical requests, so the cache mainly helps across restarts and as
  rate-limit protection. Enable it with `--cache` / `YF_MCP_CACHE=1`.
- Disabled until `configure()` is called (which `server.main` does), so
  importing the package or calling client functions in tests/library use does
  not touch disk unless caching is explicitly enabled.
- Config precedence CLI > env > default: `--cache/--no-cache` (`YF_MCP_CACHE`),
  `--cache-dir` (`YF_MCP_CACHE_DIR`), `--cache-ttl <NAME>=<SECONDS>`
  (`YF_MCP_CACHE_TTL_<NAME>`). A TTL of `0` bypasses caching for that tool.
- Only successful, non-empty returns are cached. Exceptions propagate and are
  never cached, and empty results (e.g. a search with no matches) are not
  pinned for the TTL.

## 9. Error handling

- Expected failures raise a `ToolError` subclass with a concise message
  (surfaced to the client, never a raw traceback).
  - `SymbolNotFoundError` — unknown symbol / empty result.
  - `RateLimitError` — Yahoo throttling (`YFRateLimitError` is mapped to it via
    `client._wrap_upstream`).
- All upstream yfinance exceptions are normalized through `_wrap_upstream`,
  which preserves operation-specific context for non-rate-limit errors.

## 10. Testing

- Unit tests mock `yfinance` and run **offline**, covering the client wrapper
  and error normalization, formatting, the cache, CLI/transport selection, tool
  registration/schema, and end-to-end tool invocation via `mcp.call_tool`
  (`tests/test_client.py`, `test_formatting.py`, `test_cache.py`, `test_cli.py`,
  `test_server.py`, `test_tools_integration.py`). Two more guard what ships
  rather than what runs: `test_packaging.py` on the PEP 561 marker and
  `test_readme.py` on link targets that PyPI cannot resolve.
- `tests/smoke.py` is an ad-hoc **live** check against Yahoo, and it is not part of
  the pytest suite (no `test_*` functions, so it is not collected).
- Quality gates: ruff (lint + format), mypy (type check), and a coverage floor
  of 80% (currently ~94%).
- CI (GitHub Actions): a `lint` job (ruff + mypy), a `test` matrix running
  `pytest` with coverage on Python 3.11-3.14, a `docker` job that builds the
  image and smoke-tests that the container serves HTTP, and a `fresh-install`
  job. The first three install from `uv.lock` (`uv sync --frozen`) for
  reproducibility. `fresh-install` deliberately does **not**: it builds the
  wheel and installs it into a clean environment with no lockfile, then imports
  the package, lists the tools and runs the entry point. That is the path a user
  takes, and a lockfile hides breakage in the *declared* dependency ranges —
  0.3.0 shipped an unbounded `mcp` requirement, resolved to an incompatible major
  on a fresh install and failed at import while every other job stayed green.
- Dependabot covers GitHub Actions. It does little for the Python dependencies,
  because the requirements here are open `>=` ranges and new releases fall inside
  them, so there is nothing for it to bump. It also does not touch `uv.lock`.
  Keeping the lockfile current is a manual `uv lock --upgrade`.
- A separate `publish` workflow runs when a GitHub release is published and does
  two independent things. It builds the sdist + wheel (`uv build`) and uploads
  them to **PyPI via Trusted Publishing (OIDC)**, and it builds the container
  image for `linux/amd64` and `linux/arm64` and pushes it to **ghcr.io** as
  `ghcr.io/benethos-hub/yahoo-finance-mcp`, authenticating with the automatic
  `GITHUB_TOKEN`. Neither half stores a secret, and a failure in one does not
  withhold the other. Release tags become `X.Y.Z`, `X.Y` and `latest`. The
  workflow can also be started by hand, which pushes the image as `edge` and
  skips PyPI, because a version may only be uploaded there once. Note that a
  ghcr package is private when first created and has to be made public by an
  organisation owner, which is also gated by an organisation-level setting.
  One name is used throughout: the PyPI
  distribution, the import package (`benethos_yahoo_finance_mcp`, underscores
  because a module name cannot contain hyphens), the console script, and the
  MCP server identity are all `benethos-yahoo-finance-mcp`. Only the GitHub
  repository keeps the plain `yahoo-finance-mcp`, deliberately, for
  discoverability.

## 11. Future work (not yet implemented)

- Input validation of `period`/`interval` against known value sets. The
  `statement` and `freq` arguments of `get_financials` are already validated,
  as are the sector and industry keys.
- Stale-on-error: serve an expired cache entry when Yahoo is rate limiting.

(Multi-symbol batch quoting is implemented as `get_quotes` — see §7 and §12.)

## 12. Tool expansion plan

Goal: expose every **working** yfinance method as an MCP tool. "Working" was
verified empirically (probed live on a stock `AAPL`, an ETF `SPY`, and a crypto
pair `BTC-USD`). Only methods that return real data are in scope. Availability
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
- **Dependency note:** `get_earnings_dates` requires `lxml`. It was added to
  `dependencies` when Phase 1 landed.

### Proposed new tools (grouped, not one-per-method)

Grouping keeps the tool list legible for the LLM. Each takes a `Symbol`, is
wrapped via `_wrap_upstream`, cached with a per-tool TTL, and row-capped.

| Tool | Backed by | Notes |
|------|-----------|-------|
| `get_earnings` | `get_earnings_dates`, `earnings_history` | upcoming + historical EPS estimate/actual/surprise, **needs `lxml`** |
| `get_estimates` | `earnings_estimate`, `revenue_estimate`, `eps_trend`, `eps_revisions`, `growth_estimates` | forward analyst estimates |
| `get_upgrades_downgrades` | `upgrades_downgrades` | analyst rating changes (large, row-capped) |
| `get_holders` | `major_holders`, `institutional_holders`, `mutualfund_holders` | ownership breakdown |
| `get_insider_activity` | `insider_transactions`, `insider_purchases`, `insider_roster_holders` | insider trading |
| `get_sec_filings` | `sec_filings` | recent filings |
| `get_calendar` | `calendar` | next earnings/ex-div dates |
| `get_shares` | `get_shares_full` | shares outstanding over time |
| `get_fund_data` | `funds_data` | holdings/sector weights — ETFs & funds |
| extend `get_financials` | `ttm_income_stmt`, `ttm_cashflow` | add a `ttm` frequency (income/cashflow only, no `ttm_balance_sheet` upstream) |

Excluded from tools: `sustainability`, `capital_gains` (empty). `isin`/
`history_metadata` are minor and may be folded into existing tools rather than
new ones. The planned `get_recommendations` extension was **dropped**:
`recommendations_summary` is identical to `recommendations`, which the existing
tool already returns as `recommendation_trend`.

### Module-level (separate, larger category)

These take no per-symbol `Ticker`. `Sector` / `Industry` browsing landed in
Phase 4 (`get_sector` / `get_industry`). Still open: `Market` (market
status/summary) and `Lookup` (richer search — overlaps the existing `search`,
so likely an extension rather than a new tool), the screener
(`screen` / `EquityQuery`), and multi-symbol (`download` / `Tickers`, which also
covers the §11 multi-symbol-quote item).

The sector/industry key set is sourced from yfinance's own constant
(`yfinance.const.SECTOR_INDUSTY_MAPPING_LC`, imported defensively in
`client.py`), so the validation, the tool descriptions, and the error messages
share one source of truth. The README's collapsible **"Sector & industry keys"**
block is produced from the same constant — regenerate it after a yfinance bump
(one sector per paragraph) and paste it over the existing `<details>` block:

```
uv run python - <<'PY'
import sys; sys.stdout.reconfigure(encoding="utf-8")
import yfinance.const as c
m = c.SECTOR_INDUSTY_MAPPING_LC
print("<details>")
print(f'<summary><b>📊 Sector &amp; industry keys</b> — click to expand '
      f'({len(m)} sectors, {sum(len(v) for v in m.values())} industries, generated)</summary>')
print()
for s in sorted(m):
    print(f'**`{s}`** ({len(m[s])})')
    print(", ".join(f"`{i}`" for i in sorted(m[s])))
    print()
print("</details>")
PY
```

(Some industry keys use an em-dash, not a hyphen — copy them from `get_sector`
output rather than typing them.)

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
- **Phase 4 — done:** module-level sector/industry browsing — `get_sector`
  (`yf.Sector`) and `get_industry` (`yf.Industry`). These take a sector/industry
  key, not a symbol.
- **Phase 5 — done:** `get_quotes` — compact multi-symbol quotes in one call
  (per-symbol `not_found`), covering the §11 multi-symbol-quote item. Backed by
  per-symbol `fast_info` (yfinance's `Tickers` is only a convenience wrapper, not
  true batching, and `yf.download` is reserved for a possible future bulk-history
  tool, which needs hard payload caps).

### Remaining roadmap (optional, not yet built)

All per-symbol `Ticker` methods that return real data are now exposed. What is
left is a smaller, optional set. In rough priority / effort order:

- **`get_market`** (`yf.Market`) — **done.** Eight fixed market keys. Probed
  live: only `US` serves a trading status, every other key raises upstream when
  asked for one, so `status` is `null` there. The index summary works for all
  eight, which is why the tool leads with it and treats the status as optional.
- **Screener** (`yf.screen` / `EquityQuery`) — **next.** The only remaining
  candidate that adds a capability rather than convenience: filtering the market
  by criteria is impossible with any current tool. Probed live and working. Most
  design work of the four, since it needs a query schema (field/operator/value)
  exposed to the LLM, and the raw hits carry a lot of noise that wants curating.
  Consult `yfinance.const.EQUITY_SCREENER_FIELDS` / `EQUITY_SCREENER_EQ_MAP`.
- **Bulk history** (`yf.download`) — deferred. Probed live and working, but it
  returns a **MultiIndex** over columns (`('Close', 'AAPL')`) that
  `dataframe_to_records` does not handle, the payload grows with symbols × rows,
  and `download` does not raise on bad symbols (silent NaN columns). The model
  can already loop over `get_history`, so this buys convenience, not capability.
- **`Lookup`** (`yf.Lookup`) — deferred. Probed live: 25 rows carrying
  `regularMarketPrice`, `industryName` and `rank`, so genuinely richer than
  `search`. But it overlaps `search` almost entirely, and two near-duplicate
  tools make the toolset harder for a model to navigate. If ever, extend
  `search` rather than adding a tool.

A note on the ordering above: it is deliberately not "everything that is
technically possible". With 22 tools already registered, every additional
description competes for the model's attention on every single request. A tool
that only saves a loop is a net loss.

Decisions still apply: read-only only, native Yahoo tickers, grouped tools,
empirically probe each method live before building, one reviewable PR per phase,
keep responses row/symbol-capped for the token budget.
