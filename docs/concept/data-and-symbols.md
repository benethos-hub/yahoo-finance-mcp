# Concept: data source and symbols

Part of the [concept](../CONCEPT.md): sections 5 and 6.

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
  must have the shape Yahoo uses: letters, digits and `. - ^ = &`, at least
  one letter or digit among them, as in `^GSPC`, `EURUSD=X`, `BRK-B`,
  `M&M.NS`. `yahoo.tickers.get_ticker` answers
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
