# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-06-25

### Added
- Tool `get_quotes` — compact current quotes for several symbols in one call,
  with a per-symbol `not_found` list instead of failing the whole request.
- Tools `get_earnings` (upcoming + historical earnings with EPS estimate/actual
  and surprise), `get_estimates` (forward analyst earnings/revenue/EPS/growth
  estimates), and `get_upgrades_downgrades` (analyst rating changes). All are
  equity-only and return empty for ETFs/funds/crypto.
- `lxml` dependency (required by yfinance to scrape the earnings calendar).
- Tools `get_holders` (insider/institutional ownership breakdown with top
  institutional and mutual-fund holders), `get_insider_activity` (insider
  transactions, a 6-month purchases/sales summary, and the current roster),
  `get_sec_filings` (recent SEC filings with EDGAR/exhibit links), and
  `get_calendar` (upcoming earnings and dividend / ex-dividend dates). All are
  equity-only and return empty for ETFs/funds/crypto.
- Tools `get_shares` (shares-outstanding history) and `get_fund_data` (fund/ETF
  profile: overview, asset-class and sector weightings, top holdings;
  fund/ETF-only).
- Module-level browsing tools `get_sector` and `get_industry`, which take a
  sector/industry key (e.g. `technology`, `semiconductors`) instead of a ticker
  and return the overview, top companies, and (for sectors) ETFs/funds and the
  constituent industries.

### Changed
- `get_financials` now accepts `freq="ttm"` (trailing twelve months) for the
  income and cash-flow statements.

## [0.1.1] - 2026-06-25

### Added
- `uv.lock` and a uv-based development workflow (`uv sync`, `uv run`) as the
  recommended setup; the `venv` + `pip` path remains documented as an
  alternative.

### Changed
- Docker image now installs dependencies reproducibly from `uv.lock` via uv
  (instead of `pip`); runtime behavior is unchanged.
- README reorganized: a uv + Claude Desktop quick start is now the primary
  install example, followed by the other install methods; the standalone-server
  section leads with Docker.
- CI now installs via uv against the lockfile (`astral-sh/setup-uv` +
  `uv sync --frozen`) instead of `pip`; the `lint`/`test` job names are
  unchanged.
- CI builds the Docker image and smoke-tests that the container serves the
  HTTP endpoint (`docker` job).

## [0.1.0] - 2026-06-24

First public release.

### Added
- MCP server exposing Yahoo Finance data via `yfinance`.
- Tools: `search`, `get_quote`, `get_history`, `get_company_info`,
  `get_financials`, `get_dividends`, `get_news`, `get_recommendations`,
  `get_options`.
- `search` resolves company names, tickers, and ISINs to Yahoo symbols.
- Selectable transport via CLI: `stdio` (default), `streamable-http`, `sse`,
  with `--host` / `--port` / `--path` / `--log-level` options.
- Environment-variable equivalents for every CLI option
  (`YF_MCP_TRANSPORT`/`HOST`/`PORT`/`PATH`/`LOG_LEVEL`), with CLI > env >
  default precedence.
- `python -m yahoo_finance_mcp` entry point (alias for the server).
- Dedicated rate-limit handling (`RateLimitError`) and compact, JSON-safe
  output with row caps.
- Optional persistent result cache (SQLite) with per-tool TTLs — **opt-in, off
  by default** (it mainly helps across restarts; yfinance already reuses
  identical requests within a process). Configurable via `--cache`/`--no-cache`,
  `--cache-dir`, `--cache-ttl <NAME>=<SECONDS>`, and the `YF_MCP_CACHE` /
  `YF_MCP_CACHE_DIR` / `YF_MCP_CACHE_TTL_<NAME>` env vars.
- Dockerfile and `compose.yaml` to host the server over the streamable-HTTP
  transport. The image is configured entirely via environment variables (no
  default command args) and persists its result cache to a `/cache` volume.
- README "Example prompts" section with sample natural-language queries
  grouped by tool.
- Tooling: ruff (lint + format), mypy type checking, and pytest coverage
  (~90%), wired into CI; Dependabot for pip and GitHub Actions updates.
- Unit test suite (yfinance mocked, offline) and GitHub Actions CI.

[0.2.0]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/benethos-hub/yahoo-finance-mcp/releases/tag/v0.1.0
