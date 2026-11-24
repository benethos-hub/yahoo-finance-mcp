# Concept: tools

Part of the [concept](../CONCEPT.md): section 7.

## 7. Tools

All tools are read-only, and each one carries the MCP annotations
`readOnlyHint: true` and `openWorldHint: true` (one shared `ToolAnnotations`
in `tools/_base.py`, set by `register_tool`), except `server_status`, which
asks Yahoo nothing and carries `openWorldHint: false`. `destructiveHint` and
`idempotentHint` are omitted because the spec defines them only for tools
that are not read-only. Each tool also has a short `title` (e.g. "Stock
screener" for `screen`), which a client shows a person in place of the name.
The model reads the name and the description, not the title. `symbol`
always means a Yahoo ticker or an ISIN (see §6). The four exceptions among
the data tools are `get_sector` / `get_industry`, which take a
sector/industry **key** (e.g. `technology`, `semiconductors`), `get_market`,
which takes a market key (e.g. `US`), rather than a symbol, and `screen`,
which takes filters and returns symbols. `server_status` takes none of
these, it describes the server (see the end of the table).

| Tool | Inputs | Output (shape) |
|------|--------|----------------|
| `search` | `query` (name/ticker/ISIN, at most 200 characters), `limit` 1-25 (=8) | list of `{symbol, name, exchange, type, sector, industry}` |
| `get_quote` | `symbol` | `{symbol, currency, exchange, quoteType, lastPrice, previousClose, open, dayHigh, dayLow, lastVolume, marketCap, 50/200d avg, yearHigh/Low, yearChange}` |
| `get_quotes` | `symbols[]` (≤50) | `{count, quotes[{symbol, currency, lastPrice, previousClose, open, dayHigh, dayLow, marketCap}], not_found[], truncated}` |
| `get_history` | `symbol`, `period` (=1mo), `interval` (=1d), `start?`, `end?` | `{symbol, interval, period, start, end, count, truncated, rows[]}` (OHLCV, ≤250 rows, tail kept) |
| `get_company_info` | `symbol` | curated profile + key statistics, plus `resolved_symbol` when the input resolves to a different ticker (i.e. for an ISIN, see §6) |
| `get_financials` | `symbol`, `statement` (income/balance/cashflow), `freq` (annual/quarterly/ttm — ttm income/cashflow only) | `{symbol, statement, freq, rows[]}` (every line item, columns = period-end dates as `YYYY-MM-DD`, equity-only) |
| `get_dividends` | `symbol` | `{symbol, dividends[], splits[]}` (both empty for an instrument that never paid or split, an unknown symbol raises) |
| `get_news` | `symbol`, `limit` 1-50 (=10) | `{symbol, count, source, articles[{title, summary, publisher, published, url}]}` (`source` `ticker`, or `search` when the ticker has none: the articles Yahoo's search tags with the symbol, `summary` null) |
| `get_recommendations` | `symbol` | `{symbol, price_targets, recommendation_trend[]}` (trend rows keyed by `period`) |
| `get_options` | `symbol`, `expiration?` | without `expiration`: `{symbol, expirations[]}`, with it: `{symbol, expiration, truncated, calls[], puts[]}` (≤60 strikes per side, centred on the money, rows keyed by `contractSymbol`) |
| `get_earnings` | `symbol`, `limit` 1-50 (=12), `methodology` `gaap`/`normalized` (=Yahoo's default) | `{symbol, earnings_dates[], earnings_history[]}` (equity-only, `methodology` applies to the history and each row names it) |
| `get_estimates` | `symbol`, `methodology` `gaap`/`normalized` (=Yahoo's default) | `{symbol, earnings_estimate[], revenue_estimate[], eps_trend[], eps_revisions[], growth_estimates[]}` (equity-only, `methodology` applies to the three EPS tables and each row names it) |
| `get_upgrades_downgrades` | `symbol`, `limit` 1-100 (=50) | `{symbol, changes[]}` (rating changes, newest first, equity-only) |
| `get_holders` | `symbol`, `limit` 1-100 (=25) | `{symbol, major_holders[], institutional_holders[], mutualfund_holders[]}` (top holders first, equity-only) |
| `get_insider_activity` | `symbol`, `limit` 1-100 (=50) | `{symbol, transactions[], purchases_summary[], roster[]}` (transactions newest first, equity-only) |
| `get_sec_filings` | `symbol`, `limit` 1-100 (=25) | `{symbol, count, filings[{date, type, title, url, exhibits}]}` (equity-only) |
| `get_calendar` | `symbol` | `{symbol, calendar{}}` (next earnings/dividend dates + estimate ranges, equity-only) |
| `get_shares` | `symbol`, `start?`, `end?`, `limit` 1-250 (=50) | `{symbol, count, shares[{date, shares}]}` (most recent kept, last 18 months unless `start` is given) |
| `get_fund_data` | `symbol`, `limit` 1-100 (=25) | `{symbol, description, fund_overview, key_figures{expense_ratio, category_expense_ratio, holdings_turnover, total_assets, ytd_return, three_year_average_return, five_year_average_return}, asset_classes, sector_weightings, top_holdings[]}` (fund/ETF-only, ratios and returns as fractions, a figure Yahoo lacks left out) |
| `get_sector` | `key` (sector key), `limit` 1-100 (=25) | `{key, name, index_symbol, overview, top_companies[], top_etfs, top_mutual_funds, industries[]}` (module-level, not a symbol) |
| `get_industry` | `key` (industry key), `limit` 1-100 (=25) | `{key, name, index_symbol, sector_key, sector_name, overview, top_companies[], top_performing_companies[], top_growth_companies[]}` (module-level, not a symbol) |
| `get_market` | `key` (market key, =US) | `{key, status, count, indices[{symbol, shortName, fullExchangeName, marketState, regularMarketPrice, regularMarketPreviousClose, regularMarketChange, regularMarketChangePercent}]}` (module-level, `status` only for `US`, null elsewhere) |
| `screen` | `filters[{field, op, value}]` (up to 10, all must hold), `sort_by` (=market_cap), `sort_desc` (=true), `limit` 1-100 (=25), `offset` 0-9900 (=0) | `{total, count, offset, matches[{symbol, name, exchange, currency, price, change_percent, market_cap, pe_ratio, price_to_book, eps, dividend_yield, change_52w_percent, avg_volume_3m}]}` (empty columns left out, module-level, see §12) |
| `server_status` | `details` (=false) | plain text, one `key: value` per line: `name`, `version`, `transport`, `python`, `mcp`, `uptime_seconds`, and with `details` the lines `details:`, `yfinance` (the installed version, which can differ between two installations of one server version) and `upstream:` with `reachable` (yes/no/unknown), `checked_seconds_ago` (or `never`) and `rate_limited` (yes/no/unknown), no `token_set`, since Yahoo is a public API and takes no key |

`server_status` never asks Yahoo. Its upstream lines say how the last
request ended, which `yahoo/tickers.py` remembers (`last_answer`): reached
when an upstream block ran through, ended in `not_found`, yfinance raised
about the data, Yahoo answered with an HTTP status or held the server off
with a rate limit, not reached on a network error. `rate_limited` is `yes`
when that last answer was a rate limit (yfinance's `YFRateLimitError`, or an
HTTP 429 that passed it unconverted) and `no` for any other ending, so the
next answer that comes through sets it back. Yahoo's own text never appears,
only these values. A cached result asks nobody and changes nothing, and
after a restart all three read `unknown` and `never` until the first
request. The tool's description says that an
answer holds for the moment it was given, so a model asks again after a
restart or an update rather than quote an earlier version.

### Parameter descriptions

Every tool parameter carries a human-readable description and constraints via
`Annotated[..., Field(description=..., ge=..., le=...)]` so the client receives
a precise input schema. Closed sets such as the valid `interval` or
`statement` values are listed in the parameter's description, not as a schema
`enum`, and a value outside the set is refused by the tool with a message that
names the set. The listing goes out without the `title` keys pydantic puts on
every argument model and field (`_Server.list_tools` strips them), since a
client shows the tool's own title and the model reads descriptions.
