# Concept: error handling

Part of the [concept](../CONCEPT.md): section 9.

## 9. Error handling

- Expected failures raise a `ToolError` subclass with a concise message
  (surfaced to the client, never a raw traceback).
  - `SymbolNotFoundError` — unknown symbol / empty result. It names the
    symbol trimmed and upper-cased, as every answer echoes it, whatever form
    the caller passed.
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
  `start`/`end` as real dates written `YYYY-MM-DD`, with `end` after `start`
  and `start` not after today.
  yfinance's `end` is exclusive, so the same day twice is no day at all, and
  the description says so. `get_shares` takes its dates through the same
  check, `tickers.checked_range`, and `get_options` its `expiration` through
  `tickers.checked_date` before it is looked for among the listed dates. Each
  is checked only when it is used, so `period` is not checked next to
  `start`.
  Valid arguments can still come back empty: Yahoo keeps 1m bars for 8 days,
  2m to 90m for 60 and the hourly bars for 730. No intraday rows is therefore
  a `ToolError` naming that reach and the symbol as the other possibility,
  not a `SymbolNotFoundError`. The same goes for a range with a `start` that
  comes back empty from daily or longer bars, or from `get_shares`: the
  message (`tickers.empty_range`) names the range first, which may lie after
  the symbol's last data point, and an unknown symbol second. Without a
  `start` an empty answer is still an unknown symbol.
- `ToolError` derives from the SDK's own `ToolError`, and that is what carries
  the text. Since `mcp` 2.1.0 anything else raised from a tool is treated as
  unexpected: logged with a traceback, and reported to the client as
  `Error executing tool <name>` with the message dropped. A plain `Exception`
  base therefore silences every message in `errors.py`, which is what happened
  in 0.5.0 and is fixed in 0.5.1.
