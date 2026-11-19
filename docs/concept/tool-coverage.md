# Concept: tool coverage

Part of the [concept](../CONCEPT.md): section 12.

## 12. Tool coverage: what yfinance offers and what became a tool

Every **working** yfinance method is exposed as an MCP tool, grouped by
subject rather than one tool per method. "Working" was verified empirically
(probed live on a stock `AAPL`, an ETF `SPY`, and a crypto pair `BTC-USD`),
and only methods that return real data were taken. Availability is
symbol-dependent (equity fields are empty for ETFs/crypto and vice versa) —
a tool answers that with a `SymbolNotFoundError` whose reason says Yahoo keeps
the data for single stocks only (`tickers.EQUITY_ONLY_REASON`), so the model
does not go looking for another ticker. This section keeps the probe results
and the decisions, so a yfinance bump or a new idea can be checked against
them.

### Verified data sources (probe results)

- **Equity-only (data for AAPL, empty for SPY):** `upgrades_downgrades`,
  `recommendations_summary`, `analyst_price_targets`, `earnings_estimate`,
  `revenue_estimate`, `eps_trend`, `eps_revisions`, `growth_estimates`,
  `earnings_history`, `get_earnings_dates`, `major_holders`,
  `institutional_holders`, `mutualfund_holders`, `insider_purchases`,
  `insider_roster_holders`, `insider_transactions`, `sec_filings`, `calendar`,
  `ttm_income_stmt`, `ttm_cashflow`, `valuation`, `get_shares_full`, and
  `income_stmt`, empty for SPY and EUNL.DE as well (measured 2026-11-09). The
  four EPS tables among them (`earnings_estimate`, `eps_trend`,
  `eps_revisions`, `earnings_history`) are read through their `get_*`
  methods, which take a `methodology` since yfinance 1.8.0, GAAP or
  normalized, and answer in Yahoo's default for the symbol without one.
- **Fund/ETF:** `funds_data`, its `fund_operations` included, and from
  `info` the size and returns (`totalAssets`, `ytdReturn`, the three- and
  five-year average returns), probed 2026-11-03 for SPY, QQQ and FFOJX.
- **Share counts:** `fast_info`'s and `info`'s market cap and the last point
  of `get_shares_full` rest on one count, market cap divided by price gives
  exactly that count, so comparing them finds nothing. The income
  statement's "Diluted Average Shares" come from the report and are the one
  independent count, 0 to 2 percent apart for SAP.DE, AAPL, ALV.DE, VOW3.DE
  and RHM.DE (measured 2026-11-11). `asset_analysis` checks against it and
  speaks up past ten percent (§7a).
- **Dividend pay dates:** `calendar` gives a German stock's `Ex-Dividend
  Date` but no `Dividend Date`, SAP.DE and ALV.DE alike (measured
  2026-11-11), so `dividend_calendar` estimates their pay dates at the
  ex-date plus 14 days (§7a).
- **Any symbol:** `history_metadata`, `isin`.
- **Crypto (`BTC-USD`):** the existing core paths work — `history`,
  `fast_info`/`info` (rich), `history_metadata`, `isin` — so `get_quote`,
  `get_history`, and `get_company_info` already cover crypto. All
  equity-specific methods (analysts, holders, earnings, financials, calendar)
  are empty, so the equity-only tools answer crypto with that error.
- **News:** `Ticker.get_news` goes through Yahoo's GraphQL news route
  since yfinance 1.8.0 (ranaroussi/yfinance#3018) and serves US and other
  markets alike, SAP.DE, ALV.DE, NESN.SW and 7203.T included, about 50
  articles for most symbols (probed 2026-11-03). Yahoo dropped the route
  before it in October 2026 (yfinance issue #3004), and `get_news` lived on
  the search fallback until 1.8.0. That fallback stays for a symbol without
  news of its own (VWCE.DE) and for the next route Yahoo drops. A dropped
  route answers with an HTML page yfinance reads as an outage, so its
  `YFDataException`, and an `OSError` when that page breaks off, count as
  no articles, as an empty list does.
  `Search(<symbol>).news`, kept to the articles whose `relatedTickers` name
  the symbol, serves US equities, ETFs, indices, crypto, FX and futures, and
  nothing for SAP.DE, ALV.DE, NESN.SW or 7203.T (probed 2026-10-22). A
  query by company name tags the wrong listings and was not taken.
- **Excluded — upstream empty for all probed symbols:** `sustainability` (ESG),
  `capital_gains`.
- **Out of scope (non-goals, §2):** `live`/`WebSocket` (streaming), and the SDK's
  OAuth `Auth` machinery, which presumes a user to authorize and an issuer.
- **Dependency note:** `get_earnings_dates` requires `lxml`, which is why it
  is a runtime dependency.

### The grouped tools and the methods behind them

Each takes a `Symbol`, runs under `tickers.upstream`, is cached with a
per-tool TTL and row-capped.

| Tool | Backed by | Notes |
|------|-----------|-------|
| `get_earnings` | `get_earnings_dates`, `get_earnings_history` | upcoming + historical EPS estimate/actual/surprise, **needs `lxml`** |
| `get_estimates` | `get_earnings_estimate`, `get_revenue_estimate`, `get_eps_trend`, `get_eps_revisions`, `get_growth_estimates` | forward analyst estimates |
| `get_upgrades_downgrades` | `upgrades_downgrades` | analyst rating changes (large, row-capped) |
| `get_holders` | `major_holders`, `institutional_holders`, `mutualfund_holders` | ownership breakdown |
| `get_insider_activity` | `insider_transactions`, `insider_purchases`, `insider_roster_holders` | insider trading |
| `get_sec_filings` | `sec_filings` | recent filings |
| `get_calendar` | `calendar` | next earnings/ex-div dates |
| `get_shares` | `get_shares_full` | shares outstanding over time |
| `get_fund_data` | `funds_data` (with `fund_operations`), `info` | holdings/sector weights, costs, size and returns — ETFs & funds. Yahoo gives `info`'s ytdReturn and netExpenseRatio in percent and the rest as fractions, the answer has fractions throughout. US funds carry every figure, European ETFs mostly the expense ratio and turnover only (probed 2026-11-03: SPY, QQQ, FFOJX full, EUNL.DE, CSPX.L, XDWD.DE costs only, VWCE.DE size without costs) |
| `get_financials` with `freq=ttm` | `ttm_income_stmt`, `ttm_cashflow` | income/cashflow only, there is no `ttm_balance_sheet` upstream |

Not exposed: `sustainability` and `capital_gains` (empty upstream), `isin`
and `history_metadata` (minor, `get_company_info` reports the resolved
symbol instead), and `recommendations_summary`, which is identical to
`recommendations`, already returned by `get_recommendations` as
`recommendation_trend`.

### Module-level (no per-symbol `Ticker`)

`Sector` and `Industry` browsing are `get_sector` and `get_industry`,
`Market` is `get_market`, multi-symbol quotes are `get_quotes`, and the
screener is `screen`. Bulk history (`download`) and `Lookup` were dropped,
see the decisions below.

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

### Decisions on the module-level candidates

- **`get_market`** (`yf.Market`) — **built.** Eight fixed market keys. Only
  `US` serves a trading status: Yahoo's markettime endpoint ignores the
  market parameter and always answers with US data, which yfinance 1.7.0
  detects for another key and reports as no status (older versions raised),
  so `status` is `null` there. The index summary works for all eight, which
  is why the tool leads with it and treats the status as optional.
  `get_quotes` is backed by per-symbol `fast_info`, since yfinance's
  `Tickers` is a convenience wrapper over single tickers, not batching, and
  neither is `yf.download`, see below.
- **Screener** (`yf.screen` / `EquityQuery`) — **built** as `screen`. The only
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

The set is deliberately not "everything that is technically possible". With
24 tools registered, `server_status` among them, every additional
description competes for the model's attention on every single request, and
a tool that only saves a loop is a net loss. What still applies to a new
tool: read-only only, native Yahoo tickers, grouped by subject, probed live
before it is built, built the way CLAUDE.md describes under "How to add or
change a tool" with an entry in `tests/smoke.py`, one reviewable pull
request, and responses row- or symbol-capped for the token budget.
