# Concept of the Unofficial Yahoo Finance MCP Server

This file is the overview: what the server is for and what is in scope.
Each topic has a file of its own in [concept/](concept/), and they move with
the code. The sections keep their numbers: "CONCEPT §4" in the code or in
another document names section 4, and the table below leads to it.

## The topics

| Topic | Sections | In short |
|---|---|---|
| [Architecture](concept/architecture.md) | 3 | The path from a client to Yahoo, the packages and the layer table `tests/test_layers.py` enforces. |
| [Transport and runtime](concept/transport-and-runtime.md) | 4 | stdio and the HTTP transports, the log and what a line may carry, flags and settings, the bearer guard, containers. |
| [Data source and symbols](concept/data-and-symbols.md) | 5, 6 | How Yahoo is asked through yfinance, and how a ticker, an ISIN or a name becomes a symbol. |
| [Tools](concept/tools.md) | 7 | Every tool, its parameters and how their descriptions are written. |
| [Prompts](concept/prompts.md) | 7a | The six prompts, plain templates, and what Claude Desktop checks of them. |
| [Output and cache](concept/output-and-cache.md) | 8, 8a | Compact JSON, row caps, and the opt-in result cache with its TTLs. |
| [Error handling](concept/errors.md) | 9 | The errors a tool raises and what reaches the client. |
| [Testing](concept/testing.md) | 10 | The offline suite, the daily check, the live smoke test, what the gates cannot see, CI, Dependabot and publishing. |
| [Tool coverage](concept/tool-coverage.md) | 12 | What yfinance offers, what became a tool, the probe results and the decisions. |

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
sector/industry browsing, and symbol lookup by name / ticker / ISIN. Six
prompts chain these tools into recipes a person picks in the client (§7a).

**Out of scope (non-goals):** placing trades, real-time streaming, portfolio
persistence, authenticating to Yahoo or any paid data feed, write operations
of any kind. The share counts the dividend calendar takes go into its text
and are kept nowhere.

## 11. Future work (not yet implemented)

Nothing. The roadmap in §12 is done or dropped. Serving an expired cache entry
while Yahoo rate-limits was considered and dropped: the cache is off by
default, a quote from hours ago is worse than the rate-limit message, and
every answer would need to carry its age.

(Multi-symbol batch quoting is implemented as `get_quotes` — see §7 and §12.)
