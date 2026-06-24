# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `python -m yahoo_finance_mcp` entry point (alias for the server).
- Environment-variable equivalents for every CLI option
  (`YF_MCP_TRANSPORT`/`HOST`/`PORT`/`PATH`/`LOG_LEVEL`), with CLI > env >
  default precedence.
- The Docker image is now configured entirely via environment variables (no
  default command args) and persists its result cache to a `/cache` volume.
- Optional persistent result cache (SQLite) with per-tool TTLs — **opt-in, off
  by default** (it mainly helps across restarts; yfinance already reuses
  identical requests within a process). Configurable via `--cache`/`--no-cache`,
  `--cache-dir`, `--cache-ttl <NAME>=<SECONDS>`, and the `YF_MCP_CACHE` /
  `YF_MCP_CACHE_DIR` / `YF_MCP_CACHE_TTL_<NAME>` env vars.
- `compose.yaml` for hosting the server over streamable-HTTP via Docker Compose.
- README "Example prompts" section with sample natural-language queries
  grouped by tool.
- Tooling: ruff (lint + format), mypy type checking, and pytest coverage,
  wired into CI; Dependabot for pip and GitHub Actions updates.
- Expanded test coverage: `get_company_info`, ticker caching, search limit
  clamping, history truncation, options row capping, tool registration/schema
  checks, cache key building, and upstream error normalization (~90% overall).

## [0.1.0] - 2026-06-11

### Added
- Initial release: MCP server exposing Yahoo Finance data via `yfinance`.
- Tools: `search`, `get_quote`, `get_history`, `get_company_info`,
  `get_financials`, `get_dividends`, `get_news`, `get_recommendations`,
  `get_options`.
- `search` resolves company names, tickers, and ISINs to Yahoo symbols.
- Selectable transport via CLI: `stdio` (default), `streamable-http`, `sse`,
  with `--host` / `--port` / `--path` / `--log-level` options.
- Dedicated rate-limit handling (`RateLimitError`) and compact, JSON-safe
  output with row caps.
- Dockerfile to host the server over the streamable-HTTP transport.
- Unit test suite (yfinance mocked, offline) and GitHub Actions CI.

[Unreleased]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/benethos-hub/yahoo-finance-mcp/releases/tag/v0.1.0
