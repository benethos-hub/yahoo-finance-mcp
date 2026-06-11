# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `python -m yahoo_finance_mcp` entry point (alias for the server).
- `YF_MCP_LOG_LEVEL` environment variable to set the default log level.
- `compose.yaml` for hosting the server over streamable-HTTP via Docker Compose.
- Tooling: ruff (lint + format), mypy type checking, and pytest coverage,
  wired into CI; Dependabot for pip and GitHub Actions updates.
- Expanded test coverage: `get_company_info`, ticker caching, search limit
  clamping, history truncation, options row capping, and tool
  registration/schema checks.

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

[Unreleased]: https://github.com/<OWNER>/yahoo-finance-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/<OWNER>/yahoo-finance-mcp/releases/tag/v0.1.0
