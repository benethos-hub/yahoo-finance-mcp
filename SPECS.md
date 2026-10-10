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
persistence, authenticating to Yahoo or any paid data feed, write operations
of any kind.

## 3. Architecture

```
MCP client (Claude)  --stdio / HTTP-->  transport/  -->  server.py (MCPServer)
                                                              |
                                                    tools/<subject>.py
                                                  (schemas + descriptions)
                                                              |
                                                    yahoo/<subject>.py  --> cache.py
                                              (yfinance calls, error mapping)
                                                              |
                                          yfinance --> query1/2.finance.yahoo.com
```

`cli.py` resolves the settings, sets up the log, builds the server and hands
it to a transport. `tools/` and `yahoo/` have the same eight modules, one per
subject (quotes, company, analysts, ownership, options, funds, browse,
screener), so
`tools/options.py` exposes exactly what `yahoo/options.py` fetches.

| Module | Responsibility |
|--------|----------------|
| `cli.py` | Command-line parser and `main()`: resolve settings, configure the log and the cache, build the server, hand it to `run_stdio` or `run_http`. |
| `__main__.py` | Enables `python -m benethos_yahoo_finance_mcp` (delegates to `cli.main`). |
| `settings.py` | Every `YF_MCP_*` variable and flag, resolved once into a `Settings` dataclass (flag > env > default), plus the default cache TTLs. The only module that reads the environment. |
| `server.py` | The server's identity and instructions, `build_server()`, and the `call_tool` override that logs refused arguments. |
| `tools/` | The tools a client sees, thin: parameters, descriptions, and a call to the yahoo function of the same name. `_base.py` holds the `Symbol` parameter, the shared annotations and `register_tool`, which wraps every tool with its log line. |
| `yahoo/` | All yfinance usage, one module per subject. `tickers.py` builds the `Ticker` and holds the error mapping every subject shares. The only package that imports yfinance. |
| `cache.py` | Opt-in persistent result cache (SQLite) with per-tool TTLs. Off until `configure(settings)` enables it. |
| `formatting.py` | Convert pandas/yfinance output to compact, JSON-safe values. |
| `logbook/` | Every log line, as a function, and the one stderr handler. The only package that imports `logging` (see §4). |
| `transport/` | `stdio.py`, and `http.py`: the HTTP app with the DNS-rebinding policy and the optional bearer guard in front, served by uvicorn. stdio never touches the HTTP half. |
| `errors.py` | `ToolError`, `SymbolNotFoundError`, `RateLimitError`. |
| `py.typed` | PEP 561 marker. Without it a type checker skips the installed package and every annotation in it goes unused. |

### Layers

Each top-level module or package may import only what its row names.
`tests/test_layers.py` reads every import from the source and checks it
against this table, and it checks that this table and its own copy agree, so
a new module needs a row in both.

<!-- layers:start -->
| Unit | May import |
|------|------------|
| `__init__.py` | — |
| `errors` | — |
| `settings` | — |
| `logbook` | — |
| `formatting` | `errors` |
| `cache` | `__init__.py`, `errors`, `settings`, `logbook` |
| `yahoo` | `errors`, `logbook`, `cache`, `formatting` |
| `tools` | `errors`, `logbook`, `yahoo` |
| `server` | `__init__.py`, `tools`, `settings`, `logbook` |
| `transport` | `server`, `errors`, `settings`, `logbook` |
| `cli` | everything except `__main__` |
| `__main__` | `cli` |
<!-- layers:end -->

`tools` never imports `formatting`: a tool returns what yahoo built. Only
`__main__` imports `cli`, and only `yahoo` imports yfinance. Packages are
entered only through their `__init__.py`: a name taken from another package
must be in its `__all__`, and no import reaches into another package's
submodules.

## 4. Transport & runtime

- **Transport:** selectable via `--transport`:
  - `stdio` (default) — local subprocess for Claude Desktop and similar.
  - `streamable-http` / `sse` — standalone, network-reachable HTTP service.
- **Logging:** always to stderr, one handler, installed by `cli.main` through
  `logbook.output.configure` and never at import, so under stdio stdout
  carries JSON-RPC only. `build_server` takes back the `RichHandler` the SDK's
  constructor installs, so a program that imports the package keeps its own
  logging. Every line is a function in `logbook/` (`lifecycle`, `calls`,
  `cache`, `upstream`), and nothing else imports `logging`, which
  `tests/test_logbook_catalog.py` checks along with the parameter vocabulary.
  - **How a line looks** (`logbook/formats.py`). Every line names its
    source short: `server`, `tools`, `yahoo`, `cache`, `uvicorn`, `http`, and
    any other library by its logger name. uvicorn calls its server log
    `uvicorn.error`, after the web servers' error log that holds everything
    a server says about itself, and written out a start read as a failure.
    Every line writes the time the same way, as ISO 8601 to the millisecond
    with its offset. Without a terminal, in a container log or the file
    Claude Desktop keeps, a line is plain:
    `2026-09-30T13:19:02.840+02:00 INFO     uvicorn: Started server process`.
    When stderr is a terminal and `NO_COLOR` is not set, the time is dim,
    the level in colour, the source in cyan and a request is method, path,
    status in colour and the client.
  - **Levels.** ERROR only from the SDK, with a traceback, for an exception
    that is not a `ToolError`. WARNING for a tool call that raised, a Yahoo
    rate limit, arguments a schema refused, a cache file that failed, an
    unguarded port, a token under stdio, an unusable setting. INFO for
    startup, the cache state, one line per tool call and a stop by Ctrl+C.
    DEBUG for every answered HTTP request.
  - **Ctrl+C.** uvicorn shuts down cleanly and then raises the interrupt
    again, so the process ends as interrupted. `cli.main` catches it, logs
    `Stopped by an interrupt` and exits with 130, stdio included. Uncaught it
    printed a traceback after `Finished server process`. SIGTERM, which
    `docker stop` sends, is not affected: Python turns only SIGINT into an
    exception.
  - **One line per call**, written by the wrapper `register_tool` puts around
    every tool: `get_history SAP.DE 250 rows, truncated, 412 ms`, with
    `cached` appended when the result cache answered (the cache notes that in
    a context variable).
  - **What a line may carry.** A symbol or a key, since both are public
    identifiers, with printable characters only and cut at 32, because the
    caller chose them and the line is written before Yahoo says whether they
    exist. A line break would forge a second line, an escape sequence would
    reach a terminal. Never the bearer token, a search query (free text a person
    typed, the line gives the number of matches), a URL's query string,
    anything from Yahoo's answer, or the text of an error this server raised,
    which is written for the model. A line names the error's class instead.
  - **Other loggers.** The chosen level applies to this package and to
    uvicorn's request log only. The root logger stays at WARNING, so every
    other library, including one nobody thought of, says only what went
    wrong. `mcp`, `sse_starlette`, `curl_cffi`, `urllib3`,
    `peewee`, `httpx` and `httpcore` are also pinned at WARNING by name:
    `mcp` quotes every failed call's text at INFO and `sse_starlette` logs
    every tool result in full at DEBUG. uvicorn's server log is held at INFO
    for its startup lines. uvicorn gets no
    handlers of its own. Its request log reaches the same stderr handler
    without the query string, at INFO only for a refused request (status 400
    and up, with the address that tried) and at DEBUG for all. `yfinance` is
    held at CRITICAL, which is silent: it logs an unknown symbol as up to four
    ERROR lines, one of them Yahoo's whole answer body, after the tool has
    already said "not found" in its own line. What yfinance raises still
    reaches the log through that line, and an unexpected exception through
    `wrap_upstream` with its traceback. `wrap_upstream` hands the model the
    text of yfinance's own exceptions only. A network error is named by
    class, since its text can carry the URL with Yahoo's crumb, and anything
    else by class as well.
- **CLI flags:** `--version`, `--transport`, `--host` (default 127.0.0.1), `--port`
  (default 8000, 1-65535, checked once an HTTP transport binds it), `--path`
  (default `/mcp`, `/sse` for sse), `--allowed-hosts`, `--allowed-origins`,
  `--log-level`, and the cache flags `--cache`/`--no-cache`, `--cache-dir`,
  `--cache-max-entries <N>`, `--cache-ttl <NAME>=<SECONDS>` (see §8a).
  Host/port/path/allow-list apply to the HTTP transports only. For stdio they
  are ignored.
- **Environment:** every CLI flag has an env-var equivalent (CLI > env >
  default): `YF_MCP_TRANSPORT`, `YF_MCP_HOST`, `YF_MCP_PORT`, `YF_MCP_PATH`,
  `YF_MCP_ALLOWED_HOSTS`, `YF_MCP_ALLOWED_ORIGINS`, `YF_MCP_LOG_LEVEL`, and the
  cache vars `YF_MCP_CACHE`, `YF_MCP_CACHE_DIR`, `YF_MCP_CACHE_MAX_ENTRIES`,
  `YF_MCP_CACHE_TTL_<NAME>`.
  `YF_MCP_BEARER_TOKEN` is the one exception with no flag: an argument is
  visible in the process list to every other user on the machine. All of them
  are read once, by `settings.load_settings`. A value that cannot be used
  falls back to its default with a warning in the log, a flag value that
  cannot be used is a usage error.
- **Entry points:** `python -m benethos_yahoo_finance_mcp` or the
  `benethos-yahoo-finance-mcp` console script.
- **Python:** 3.11-3.15, all covered by the CI matrix.
- **HTTP security:** an **optional** bearer token. With
  `YF_MCP_BEARER_TOKEN` set, every HTTP request must carry
  `Authorization: Bearer <token>` or gets HTTP 401. A single shared secret
  compared in constant time, not an OAuth flow: this server speaks for nobody
  and has no user to authorize. Off by default, since the ordinary case is a
  loopback bind on the machine that uses it. stdio ignores it. A token does not
  make a port safe to publish - bind to `0.0.0.0` only on trusted networks and
  front it with a proxy that authenticates. The guard sits in front of the
  whole ASGI app and lets only the lifespan scope through unchecked. A
  WebSocket handshake is closed with 1008 before it is accepted, and any
  other scope type gets no answer, so a route the SDK adds later is not
  open by default.
  The MCP HTTP transport also runs a DNS-rebinding `Host`/`Origin` guard. It is
  derived from the actual bind host and passed to the SDK's app builder
  (`streamable_http_app` / `sse_app`, via `transport.http_app`) as an
  explicit argument: a localhost bind keeps the protective localhost allow-list
  (decided by address, so `LOCALHOST`, `127.0.0.2` and `[::1]` count, and
  `YF_MCP_HOST` is trimmed first),
  an exposed bind accepts any `Host` unless `--allowed-hosts` /
  `--allowed-origins` narrow it (mismatches get HTTP 421). Either list is
  derived from the other when only one is given. stdio has no HTTP
  surface and is handed no transport options at all. Both compose files set
  `YF_MCP_ALLOWED_HOSTS` to the loopback names and their service name, because
  the image binds `0.0.0.0` and the guard would otherwise be off while the
  port sits on the host's loopback, reachable by a rebound browser page.
  Production appends `YAHOO_FINANCE_MCP_DOMAIN` when it is set, the name
  clients use through Caddy (see Deployment), which would otherwise get 421.
  `tests/test_cli.py` holds it to that.
- **Deployment:** everything for containers sits in `containers/`. The
  `Dockerfile` in `containers/images/yahoo-finance-mcp/` (multi-stage,
  non-root, healthcheck, dependencies installed reproducibly from `uv.lock`
  via uv, build context the repository root) hosts the server over
  streamable-HTTP on port 8000. The image is configured entirely via env vars
  (no default CMD args) and persists its cache to a `/cache` volume. Two
  compose files run it: `containers/production/` pulls the published image at
  the version `.env` names, required and without a default, and needs no
  clone, `containers/development/` builds from the checkout under a project
  name and host port of its own (8001), so both run side by side. Secrets such
  as the bearer token go in an optional `.env` beside the compose file, read
  through `env_file` and ignored by git and the build context, with
  `containers/production/.env.example` as the tracked template. Only Compose
  (or `docker run --env-file`) reads it, the server itself loads no file.
  Both publish the port on **127.0.0.1 only**, drop every Linux capability
  and set `no-new-privileges`, since the server runs as a non-root user on a
  high port and needs none, run on a read-only root file system with a tmpfs
  for `/tmp` and for `yfinance`'s cookie and time zone cache in the home
  directory, and cap the log Docker keeps of the container at 5 files of
  10 MB, since uvicorn writes a line per request and Docker's default keeps
  everything. CI asserts the loopback port, the read-only root, that
  development builds and that production pulls the published image.
  Drop the loopback prefix only behind a reverse proxy that authenticates, or
  at the very least with `YF_MCP_BEARER_TOKEN` set.
  Production brings that proxy along under the compose profile `https`
  (`COMPOSE_PROFILES=https` in `.env`): Caddy, configured by the `Caddyfile`
  beside the compose file, on ports 80 and 443 of every address, TCP and,
  for HTTP/3, UDP. It forwards to the server by service name over the
  compose network, so the server's port stays on 127.0.0.1. The domain comes
  from `YAHOO_FINANCE_MCP_DOMAIN`, the certificate from one of three
  snippets picked by `YAHOO_FINANCE_MCP_TLS`: `acme` (default, a public CA),
  `internal` (Caddy's own CA) or `files` (`secrets/tls/cert.pem` and
  `key.pem`, ignored by git). A request without an `Authorization` header
  gets 401 from Caddy and never reaches the server, which checks the token
  of every other, and the token is required with the profile. The server
  trusts no forwarded header, so its log names Caddy's address for a
  refused request, not the client's. Compose cannot require the domain for
  one profile only, since `:?` fails every start without it, so Caddy's
  command checks it first and stops with a message naming it. Caddy runs
  read-only with a tmpfs for `/tmp`, every capability dropped except
  `NET_BIND_SERVICE`, `no-new-privileges` and the same log cap, and keeps
  certificates and the ACME account in the volumes `caddy-data` and
  `caddy-config`. It starts once the server reports healthy.

## 5. Data source rules

- Single source: `yfinance`. No other provider, no direct HTTP scraping.
- One cache layer: successful tool **results** are cached persistently with
  per-tool TTLs (see §8a). `yahoo.tickers.get_ticker` builds a new
  `yf.Ticker` for every call and shares none. The SDK runs the sync tools in
  worker threads, and a `Ticker` fills its lazily loaded fields without a
  lock, which yfinance promises nothing about. Building one sends no request
  for a ticker. For an ISIN-shaped symbol the constructor looks it up through
  Yahoo's search, and yfinance keeps that answer in a cache file of its own.
  requests-cache is **not** usable here — yfinance uses curl_cffi and rejects
  caching sessions — so the result cache operates on our normalized output,
  not on HTTP responses.
- Symbol resolution (name / ticker / ISIN) uses `yfinance.Search`, and the same
  endpoint handles all three input kinds. The `search` tool calls it directly.
  For an ISIN passed as a symbol, `yf.Ticker` calls it on its own (see §6).

## 6. Symbol model

- All `get_*` tools pass the given `symbol` through to yfinance unchanged
  apart from trimming and uppercasing. The server itself resolves nothing
  (Variant A) and never assembles or rewrites a symbol.
- A symbol has at most 32 characters, which the schema says (`maxLength`), and
  must have the shape Yahoo uses: letters, digits and `. - ^ = &`, as in
  `^GSPC`, `EURUSD=X`, `BRK-B`, `M&M.NS`. `yahoo.tickers.get_ticker` answers
  anything else with `SymbolNotFoundError` before yfinance is asked, since the
  symbol goes into the path of Yahoo's URLs. 128 symbols from 25 live
  searches across markets, futures, currencies and crypto all fit, checked
  2026-09-30.
- In practice that accepts both a **Yahoo ticker** (`AAPL`, `SAP.DE`) and a
  **plain ISIN** (`US0378331005`). The ISIN is resolved by yfinance, not by
  this server and not by the data endpoints: `yf.Ticker` recognises anything
  shaped like an ISIN (`^[A-Z]{2}[A-Z0-9]{9}[0-9]$`), looks it up through
  Yahoo's search in its constructor and uses the ticker found from then on.
  Probed 2026-08-16: all 18 symbol-taking tools return correct data for an ISIN.
  It still rests on an unofficial search endpoint, so it is **observed
  behaviour, not a guarantee** — it did not work at all when this section was
  first written, and it can change back. When the search finds nothing the
  constructor raises, and the tool answers with `SymbolNotFoundError`.
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

All tools are read-only, and each one carries the MCP annotations
`readOnlyHint: true` and `openWorldHint: true` (one shared `ToolAnnotations`
in `tools/_base.py`, set by `register_tool`). `destructiveHint` and `idempotentHint` are omitted because
the spec defines them only for tools that are not read-only. Each tool also
has a short `title` (e.g. "Stock screener" for `screen`), which a client
shows a person in place of the name. The model reads the name and the
description, not the title. `symbol` always
means a Yahoo ticker or an ISIN (see §6). The four exceptions are
`get_sector` / `get_industry`, which take a sector/industry **key** (e.g.
`technology`, `semiconductors`), `get_market`, which takes a market key
(e.g. `US`), rather than a symbol, and `screen`, which takes filters and
returns symbols.

| Tool | Inputs | Output (shape) |
|------|--------|----------------|
| `search` | `query` (name/ticker/ISIN), `limit` 1-25 (=8) | list of `{symbol, name, exchange, type, sector, industry}` |
| `get_quote` | `symbol` | `{symbol, currency, exchange, quoteType, lastPrice, previousClose, open, dayHigh, dayLow, lastVolume, marketCap, 50/200d avg, yearHigh/Low, yearChange}` |
| `get_quotes` | `symbols[]` (≤50) | `{count, quotes[{symbol, currency, lastPrice, previousClose, open, dayHigh, dayLow, marketCap}], not_found[], truncated}` |
| `get_history` | `symbol`, `period` (=1mo), `interval` (=1d), `start?`, `end?` | `{symbol, interval, period, start, end, count, truncated, rows[]}` (OHLCV, ≤250 rows, tail kept) |
| `get_company_info` | `symbol` | curated profile + key statistics, plus `resolved_symbol` when the input resolves to a different ticker (i.e. for an ISIN, see §6) |
| `get_financials` | `symbol`, `statement` (income/balance/cashflow), `freq` (annual/quarterly/ttm — ttm income/cashflow only) | `{symbol, statement, freq, rows[]}` (every line item, columns = period-end dates as `YYYY-MM-DD`) |
| `get_dividends` | `symbol` | `{symbol, dividends[], splits[]}` (both empty for an instrument that never paid or split, an unknown symbol raises) |
| `get_news` | `symbol`, `limit` 1-10 (=10, Yahoo serves no more) | `{symbol, count, articles[{title, summary, publisher, published, url}]}` |
| `get_recommendations` | `symbol` | `{symbol, price_targets, recommendation_trend[]}` (trend rows keyed by `period`) |
| `get_options` | `symbol`, `expiration?` | without `expiration`: `{symbol, expirations[]}`, with it: `{symbol, expiration, truncated, calls[], puts[]}` (≤60 strikes per side, centred on the money, rows keyed by `contractSymbol`) |
| `get_earnings` | `symbol`, `limit` 1-50 (=12) | `{symbol, earnings_dates[], earnings_history[]}` (equity-only) |
| `get_estimates` | `symbol` | `{symbol, earnings_estimate[], revenue_estimate[], eps_trend[], eps_revisions[], growth_estimates[]}` (equity-only) |
| `get_upgrades_downgrades` | `symbol`, `limit` 1-100 (=50) | `{symbol, changes[]}` (rating changes, newest first, equity-only) |
| `get_holders` | `symbol`, `limit` 1-100 (=25) | `{symbol, major_holders[], institutional_holders[], mutualfund_holders[]}` (top holders first, equity-only) |
| `get_insider_activity` | `symbol`, `limit` 1-100 (=50) | `{symbol, transactions[], purchases_summary[], roster[]}` (transactions newest first, equity-only) |
| `get_sec_filings` | `symbol`, `limit` 1-100 (=25) | `{symbol, count, filings[{date, type, title, url, exhibits}]}` (equity-only) |
| `get_calendar` | `symbol` | `{symbol, calendar{}}` (next earnings/dividend dates + estimate ranges, equity-only) |
| `get_shares` | `symbol`, `start?`, `end?`, `limit` 1-250 (=50) | `{symbol, count, shares[{date, shares}]}` (most recent kept, last 18 months unless `start` is given) |
| `get_fund_data` | `symbol`, `limit` 1-100 (=25) | `{symbol, description, fund_overview, asset_classes, sector_weightings, top_holdings[]}` (fund/ETF-only) |
| `get_sector` | `key` (sector key), `limit` 1-100 (=25) | `{key, name, index_symbol, overview, top_companies[], top_etfs, top_mutual_funds, industries[]}` (module-level, not a symbol) |
| `get_industry` | `key` (industry key), `limit` 1-100 (=25) | `{key, name, index_symbol, sector_key, sector_name, overview, top_companies[], top_performing_companies[], top_growth_companies[]}` (module-level, not a symbol) |
| `get_market` | `key` (market key, =US) | `{key, status, count, indices[{symbol, shortName, fullExchangeName, marketState, price, previous close, change, change %}]}` (module-level, `status` only for `US`, null elsewhere) |
| `screen` | `filters[{field, op, value}]` (up to 10, all must hold), `sort_by` (=market_cap), `sort_desc` (=true), `limit` 1-100 (=25), `offset` 0-9900 (=0) | `{total, count, offset, matches[{symbol, name, exchange, currency, price, change_percent, market_cap, pe_ratio, price_to_book, eps, dividend_yield, change_52w_percent, avg_volume_3m}]}` (empty columns left out, module-level, see §12) |

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
  within the client's token budget. Which rows survive a cut depends on the
  shape: a time series keeps its tail (the most recent rows), a list ranked
  from the top keeps its head (holders, insider transactions, rating
  changes, top companies), and an option chain keeps the window around the
  money. A financial statement is a set of line items with no safe end to
  drop, so it is not cut at all. `get_history`, `get_quotes` and
  `get_options` report a `truncated` flag, `screen` the `total` number of
  matches with `offset` for the next page, the rest cap silently, and the
  server instructions say so.
- Column labels that are midnight timestamps, the period ends of a
  statement, are keyed by their plain ISO date (`2025-09-30`), since every
  row repeats every key.

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
  | `screen` | `screen` | 10 min |
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
- **Opt-in: off by default.** Every call asks Yahoo anew (§5), so the cache
  is what makes a repeat cheap, across restarts and as rate-limit protection.
  It stays off because the ordinary case is an interactive stdio session,
  where a repeat is rare and fresh data counts for more, and a file on disk
  is the operator's choice. Enable it with `--cache` / `YF_MCP_CACHE=1`.
- Disabled until `configure(settings)` is called (which `cli.main` does), so
  importing the package or calling the yahoo functions in tests/library use
  does not touch disk unless caching is explicitly enabled.
- Config precedence CLI > env > default: `--cache/--no-cache` (`YF_MCP_CACHE`),
  `--cache-dir` (`YF_MCP_CACHE_DIR`), `--cache-max-entries <N>`
  (`YF_MCP_CACHE_MAX_ENTRIES`, default 10 000, at least 1),
  `--cache-ttl <NAME>=<SECONDS>` (`YF_MCP_CACHE_TTL_<NAME>`). A TTL of `0`
  bypasses caching for that tool.
- Only successful, non-empty returns are cached. Exceptions propagate and are
  never cached, and empty results are not pinned for the TTL. Empty means a
  falsy value, a search with no matches say, or a dict whose `count` is 0,
  `get_news` without articles say (`cache.has_content`). A function whose
  "nothing found" looks different passes its own test via
  `cached(..., worth_keeping=...)`: a `get_quotes` call in which every symbol
  missed is not stored.
- The key is a hash of the package version, the category and the arguments.
  Text is trimmed and lower-cased, so a symbol is case-insensitive, and every
  other value keeps its type (`True` and `"true"` are two keys). The version
  makes a release start from an empty cache in effect, so a changed result
  shape is never served from before it.
- SQLite waits at most `LOCK_TIMEOUT` (0.5 s) for another process holding
  the file. The wait happens under the cache's own lock, where every tool
  call stands still, and past it the call runs without the cache.
- The cache never fails a call, and never the start. A database another
  process holds locked, or a damaged file, is logged as a warning and the
  result is fetched and returned as if caching were off. At startup the same
  goes for the file or its directory: `configure` logs a warning and the
  server runs without a cache.
- Housekeeping: an expired entry is deleted when it is read, and every
  hundredth write sweeps the whole file. Startup used to be the only sweep,
  and a long-running HTTP server kept every entry nobody asked for again.
  The pages a sweep frees go back to the file system (`auto_vacuum` in its
  incremental mode, `PRAGMA incremental_vacuum` after each sweep), so the
  file follows what it holds instead of staying at its largest size. A
  file made before that is rewritten once when it is opened, said in the
  log.
- Size: the TTLs bound how long an entry lives, not how many there are, and
  over HTTP a caller decides how many distinct keys arrive within one TTL.
  After the expired entries, every sweep, the one at startup included, drops
  the oldest beyond `cache_max_entries` and logs how many at INFO. Oldest
  means written first, by `rowid`, since `INSERT OR REPLACE` gives a
  rewritten key a new one. Ordering by expiry instead would let yesterday's
  24-hour entry push out a quote written a second ago. Between sweeps the
  count can run up to a hundred past the limit. The startup sweep makes a
  lowered limit hold at once.

## 9. Error handling

- Expected failures raise a `ToolError` subclass with a concise message
  (surfaced to the client, never a raw traceback).
  - `SymbolNotFoundError` — unknown symbol / empty result.
  - `RateLimitError` — Yahoo throttling (`YFRateLimitError` is mapped to it via
    `yahoo.tickers.wrap_upstream`).
- All upstream exceptions are normalized through `wrap_upstream`: a rate
  limit becomes `RateLimitError`, yfinance's own exceptions keep their text
  behind the operation's message, and a network error or anything unexpected
  is named by class only (§4 says why).
  The yahoo functions run their yfinance calls inside the
  `tickers.upstream(message)` context manager, which does exactly that. Its
  `not_found=` names the exceptions that mean the symbol simply has no such
  data, yfinance's `YFDataException` for the fund data of a stock say, and
  those become a `SymbolNotFoundError` instead, a rate limit excepted. The
  `Ticker` constructor is
  covered as well: an ISIN-shaped string Yahoo cannot resolve raises there
  and becomes a `SymbolNotFoundError`, and in `get_quotes` such a symbol is
  listed under `not_found` instead of failing the batch.
- An argument Yahoo would answer with no rows is checked before the call,
  because no rows reads as an unknown symbol. That covers `statement` and
  `freq` of `get_financials`, the sector, industry and market keys, and the
  arguments of `get_history`: `interval` from a fixed set, `period` listed or
  shaped as a count of d, wk, mo or y (Yahoo serves `7mo` and `3y` too), and
  `start`/`end` as real dates written `YYYY-MM-DD`, with `end` after `start`.
  yfinance's `end` is exclusive, so the same day twice is no day at all, and
  the description says so. `get_shares` takes its dates through the same
  check, `tickers.checked_range`, and `get_options` its `expiration` through
  `tickers.checked_date` before it is looked for among the listed dates. Each
  is checked only when it is used, so `period` is not checked next to
  `start`.
  Valid arguments can still come back empty: Yahoo keeps 1m bars for 8 days,
  2m to 90m for 60 and the hourly bars for 730. No intraday rows is therefore
  a `ToolError` naming that reach and the symbol as the other possibility,
  not a `SymbolNotFoundError`.
- `ToolError` derives from the SDK's own `ToolError`, and that is what carries
  the text. Since `mcp` 2.1.0 anything else raised from a tool is treated as
  unexpected: logged with a traceback, and reported to the client as
  `Error executing tool <name>` with the message dropped. A plain `Exception`
  base therefore silences every message in `errors.py`, which is what happened
  in 0.5.0 and is fixed in 0.5.1.

## 10. Testing

- Unit tests mock `yfinance` and run **offline**, covering the yahoo
  functions and error normalization (`tests/yahoo/`, one file per yahoo
  module), formatting, the cache, settings, CLI/transport selection, the log
  lines, tool registration/schema, and end-to-end tool invocation via
  `mcp.call_tool` (`test_formatting.py`, `test_cache.py`, `test_settings.py`,
  `test_cli.py`, `test_logbook.py`, `test_server.py`,
  `test_tools_integration.py`, `test_transport.py`). Two guard the shape of
  the code: `test_layers.py` the import table, `test_logbook_catalog.py` that
  every line is a logbook function. Two more guard what ships rather than
  what runs: `test_packaging.py` on the PEP 561 marker and the version
  examples, `test_readme.py` on link targets PyPI cannot resolve and on the
  tool list matching the registry.
- `tests/smoke.py` is an ad-hoc **live** check against Yahoo, and it is not part of
  the pytest suite (no `test_*` functions, so it is not collected).
- Quality gates: ruff (lint + format), mypy (type check), and a coverage floor
  of 80% (currently ~97%).
- **What the gates cannot see.** The suite mocks yfinance and stops at
  the yahoo package, so a behaviour change in either boundary passes every gate. For
  `yfinance` the answer is `tests/smoke.py` run before and after a bump, with a
  baseline to compare against. For `mcp` it is `tests/test_tools_integration.py`,
  which travels through `mcp.call_tool` and asserts a `ToolError`'s message
  arrives, since 2.1.0 dropped exactly that while 246 tests stayed green.
- CI (GitHub Actions): a `lint` job (ruff + mypy), a `test` matrix running
  `pytest` on Python 3.11-3.15, where only 3.15, the newest, measures
  coverage and enforces the floor, a `docker` job that builds the
  image for amd64 and arm64, smoke-tests that the container serves HTTP and
  passes its health check, and checks both compose files, production with
  its profile `https` (valid, every port on the loopback address except
  Caddy's 80 and 443, read-only root, development builds and production
  pulls), and a `fresh-install`
  job. The first three install from `uv.lock` (`uv sync --frozen`) for
  reproducibility. `fresh-install` deliberately does **not**: it builds the
  wheel and installs it into a clean environment with no lockfile, then imports
  the package, lists the tools and runs the entry point. That is the path a user
  takes, and a lockfile hides breakage in the *declared* dependency ranges —
  0.3.0 shipped an unbounded `mcp` requirement, resolved to an incompatible major
  on a fresh install and failed at import while every other job stayed green.
  A `lowest-versions` job checks the other end of those ranges: it installs
  every direct dependency at its lower bound (`--resolution lowest-direct`)
  on Python 3.11, again without the lockfile, and runs the suite. It is an
  early warning and not a required check on `main`. A red run means a lower
  bound in `pyproject.toml` needs raising.
- Every action in both workflows is pinned to a full commit SHA, with the
  version it stands for in a trailing comment, and the two base images in the
  `Dockerfile` (`containers/images/yahoo-finance-mcp/`) by digest next to
  their tag. A tag is a pointer its owner can
  move, and the publish workflow holds the credentials that push to PyPI and
  ghcr. Dependabot reads the comment and raises SHA and comment together.
  Caddy in the production compose file is the deliberate exception: `caddy:2`
  follows its major line. It is a server facing the internet that someone
  else runs, so `docker compose pull` should bring its security fixes the
  day they ship rather than with the next release here, and Caddy keeps its
  configuration compatible within a major version. Nothing is built from
  it, so no credentials depend on it.
- Dependabot covers GitHub Actions, the two images in the `Dockerfile` and,
  since 0.5.1, the Python dependencies in `uv.lock`. It reads `FROM` lines
  only, so the uv image is a stage of its own rather than a `COPY --from=`
  reference, and pinned to its patch, since Dependabot proposes only tags of
  the precision already written. Up to 0.7.0 it was neither and fell three
  patch releases behind unnoticed. That last entry used to name the `pip`
  ecosystem, which does not read `uv.lock` — and with every requirement declared
  as an open `>=` range there was no constraint for it to raise either, so it
  proposed nothing at all while the lockfile drifted fourteen packages behind.
  The ecosystem is `uv` now. It still only proposes **direct** dependencies, and
  transitive ones move only when a direct bump drags them along, so a periodic
  `uv lock --upgrade` remains the way to refresh the rest. The moment for it is
  **before every version bump**, as the first step of the release checklist in
  CLAUDE.md. 0.5.2 is why: three direct packages had moved through Dependabot
  and eleven transitive ones underneath had not, and an image that ships the
  first without the second is half a rebuild.
  Minor and patch updates arrive grouped, one pull request per ecosystem and
  week, a major on its own, and `yfinance` and `mcp` always on their own,
  since each needs the checks CLAUDE.md describes.
- A separate `publish` workflow runs when a GitHub release is published and does
  two independent things. It builds the sdist + wheel (`uv build`) and uploads
  them to **PyPI via Trusted Publishing (OIDC)**, and it builds the container
  image for `linux/amd64` and `linux/arm64` and pushes it to **ghcr.io** as
  `ghcr.io/benethos-hub/benethos-yahoo-finance-mcp`, authenticating with the
  automatic `GITHUB_TOKEN`. The image carries the distribution's name, and
  the PyPI job deploys to the environment `pypi-benethos-yahoo-finance-mcp`.
  Up to 0.7.1 they were `ghcr.io/benethos-hub/yahoo-finance-mcp` and `pypi`.
  Those releases were copied to the new name once, digest for digest, so the
  new name holds every release from 0.4.0 on. The 0.7 line was pushed
  under the old image name as well, the same index with the same digest,
  and 0.8.0 dropped it. `tests/test_packaging.py` refuses a version of 0.8.0
  or later should `publish.yml` name it again. Neither half stores a secret, and a failure
  in one does not withhold the other. Release tags become `X.Y.Z`, `X.Y` and `latest`, a
  pre-release its exact version only, so `latest` stays on the last full
  release. Both jobs stop first when the tag is not `v` plus the version in
  `pyproject.toml` (`.github/scripts/tag_matches_version.py`), since PyPI
  would refuse the upload while the image job pushed its tags with the old
  code. The workflow can also be started by hand, from `main` only, which
  pushes the image as `edge` and skips PyPI, because a version may only be
  uploaded there once. Note that a
  ghcr package is private when first created and has to be made public by an
  organisation owner, which is also gated by an organisation-level setting. A
  public package is still absent from the repository sidebar for a logged-out
  visitor, because that block is fed by an API with no anonymous access. That is
  not a misconfiguration and there is no setting for it, so the README badge row
  carries the image link instead.
  One name is used throughout: the PyPI
  distribution, the import package (`benethos_yahoo_finance_mcp`, underscores
  because a module name cannot contain hyphens), the console script, and the
  MCP server identity are all `benethos-yahoo-finance-mcp`. Only the GitHub
  repository keeps the plain `yahoo-finance-mcp`, deliberately, for
  discoverability.

## 11. Future work (not yet implemented)

Nothing. The roadmap in §12 is done or dropped. Serving an expired cache entry
while Yahoo rate-limits was considered and dropped: the cache is off by
default, a quote from hours ago is worse than the rate-limit message, and
every answer would need to carry its age.

(Multi-symbol batch quoting is implemented as `get_quotes` — see §7 and §12.)

## 12. Tool expansion plan

Goal: expose every **working** yfinance method as an MCP tool. "Working" was
verified empirically (probed live on a stock `AAPL`, an ETF `SPY`, and a crypto
pair `BTC-USD`). Only methods that return real data are in scope. Availability
is symbol-dependent (equity fields are empty for ETFs/crypto and vice versa) —
a tool answers that with a `SymbolNotFoundError` whose reason says Yahoo keeps
the data for single stocks only (`tickers.EQUITY_ONLY_REASON`), so the model
does not go looking for another ticker.

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
  are empty, so the equity-only tools answer crypto with that error.
- **Excluded — upstream empty for all probed symbols:** `sustainability` (ESG),
  `capital_gains`.
- **Out of scope (non-goals, §2):** `live`/`WebSocket` (streaming), and the SDK's
  OAuth `Auth` machinery, which presumes a user to authorize and an issuer.
- **Dependency note:** `get_earnings_dates` requires `lxml`. It was added to
  `dependencies` when Phase 1 landed.

### Proposed new tools (grouped, not one-per-method)

Grouping keeps the tool list legible for the LLM. Each takes a `Symbol`, is
wrapped via `tickers.upstream`, cached with a per-tool TTL, and row-capped.

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
Phase 4 (`get_sector` / `get_industry`), `Market` later as `get_market`, and
multi-symbol quotes as `get_quotes` (Phase 5), the screener as `screen`
(Phase 6). Bulk history (`download`) and `Lookup` were dropped, see the
roadmap below.

The sector/industry key set is sourced from yfinance's own constant
(`yfinance.const.SECTOR_INDUSTY_MAPPING_LC`, imported defensively in
`yahoo/browse.py`), so the validation, the tool descriptions, and the error messages
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
docs**. Each tool follows the established pattern (logic in the yahoo module +
`@cache.cached`, a thin function in the tools module of the same name, added
to its `register()`, with `Annotated` Fields, FakeTicker
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
  true batching, and neither is `yf.download`, see below).
- **Phase 6 — done:** `screen` (`yf.screen` / `EquityQuery`), see below.

### Roadmap after the per-symbol tools

All per-symbol `Ticker` methods that return real data are exposed. These were
the module-level candidates, each built or dropped:

- **`get_market`** (`yf.Market`) — **done.** Eight fixed market keys. Probed
  live: only `US` serves a trading status, every other key raises upstream when
  asked for one, so `status` is `null` there. The index summary works for all
  eight, which is why the tool leads with it and treats the status as optional.
- **Screener** (`yf.screen` / `EquityQuery`) — **done** as `screen`. The only
  candidate that added a capability rather than convenience. Yahoo knows 92
  fields with names no model guesses, so the description lists 31 aliases in
  groups and raw names stay accepted. The fields and category values come
  from `yfinance.const` (`EQUITY_SCREENER_FIELDS`, `EQUITY_SCREENER_EQ_MAP`),
  imported defensively like the sector keys: without them the server still
  starts and `screen` answers that it is unavailable. Filters are a flat
  list that must all hold. Yahoo's OR and nesting are not exposed, real
  screening questions are
  conjunctions, and two calls replace an OR. Every filter is checked before
  the call, each mistake with its own message. Category values are matched
  after lower-casing and turning every run of other characters into one
  hyphen, since the screener writes `Software—Infrastructure` with an em dash
  where get_sector hands out `software-infrastructure`. Probed live on
  2026-10-08 (yfinance 1.7.0): every alias filters and sorts, percentages
  are in percent, `region` is the listing country (`de` returns Nvidia on
  XETRA), a company comes back once per listing, and Yahoo serves offsets up
  to about 10,000. Each hit carries over 80 fields, the row keeps 13 named
  like the aliases, plus `total`. 25 rows are about 8 KB. Preferred shares
  are listings of their own (`JPM-PC`, `BAC-PE` under `region us`) and
  carry the common stock's `eps` and market cap, so their `pe_ratio` comes
  out between about 1.6 and 6 (checked 2026-10-10). The description warns
  about it rather than filtering them out, since Yahoo marks them by symbol
  only and a filter would make `total` disagree with the rows.
- **Bulk history** (`yf.download`) — **dropped.** It saves Yahoo no request:
  yfinance fetches each symbol with its own `Ticker.history` call, only in
  threads (`yfinance.multi._download_one`, checked in 1.7.0). What it adds is
  a **MultiIndex** over columns (`('Close', 'AAPL')`) that
  `dataframe_to_records` does not handle, a payload that grows with symbols ×
  rows, and no error on a bad symbol (silent NaN columns). The model loops
  over `get_history` with the same requests and a clear error per symbol.
- **`Lookup`** (`yf.Lookup`) — **dropped.** Probed live: 25 rows carrying
  `regularMarketPrice`, `industryName` and `rank`, so richer than `search`.
  But it answers the same question, and a near-duplicate tool makes the
  toolset harder for a model to navigate. A price is one `get_quotes` call
  away, and filtering by industry is what `screen` does.

A note on the ordering above: it is deliberately not "everything that is
technically possible". With 23 tools already registered, every additional
description competes for the model's attention on every single request. A tool
that only saves a loop is a net loss.

Decisions still apply: read-only only, native Yahoo tickers, grouped tools,
empirically probe each method live before building, one reviewable PR per phase,
keep responses row/symbol-capped for the token budget.
