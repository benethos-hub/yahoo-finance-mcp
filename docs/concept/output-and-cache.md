# Concept: output and cache

Part of the [concept](../CONCEPT.md): sections 8 and 8a.

## 8. Output format

- Default output is **compact JSON** (JSON-safe dicts/lists). The one
  exception is `server_status`, which answers in plain text without a
  structured copy (§7). A result travels twice, as `structuredContent` and
  as one text block holding the same JSON without indentation
  (`tools/_base.py`, `_packed`). Left to the SDK the text block is indented
  by two spaces, two fifths more bytes for what Claude Desktop hands the
  model. The `search` list is wrapped as `{"result": [...]}` in the
  structured copy, as its output schema says.
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
  bypasses the cache for that tool, reading included, so an entry stored
  under an earlier TTL is not served.
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
