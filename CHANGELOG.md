# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Migrated to the **mcp 2.x SDK**. `mcp.server.fastmcp.FastMCP` was removed
  upstream and replaced by `mcp.server.mcpserver.MCPServer`. The requirement is
  now `mcp[cli]>=2.0.0,<3`, so the temporary cap from 0.3.1 is gone.
- Transport options are no longer written into mutable global settings. Host,
  port, URL path and the DNS-rebinding guard are passed to `MCPServer.run()` as
  explicit arguments, and stdio is handed none of them at all. This removes the
  cause of the HTTP 421 bug fixed in 0.3.0 rather than compensating for it.

### Added
- The server now reports a human-readable `title` ("Unofficial Yahoo Finance
  MCP Server") next to its programmatic `name`. The 1.x SDK defined the field
  but never passed it through, so clients had only the name to display.
- The server now reports its own package version in the handshake instead of an
  empty string.
- Two tests covering gaps found during the migration: the default URL path of
  each HTTP transport, and that stdio receives no transport security settings.

Tools, options, output shapes and behaviour are unchanged.

### Maintenance
- Refreshed the lockfile: 29 packages moved to current releases, among them
  ruff 0.16.3, mypy 2.3.1, pandas 3.0.5, numpy 2.5.2, starlette 1.6.0 and
  uvicorn 0.52.3.
- **yfinance 1.4.1 → 1.6.0**, upgraded separately because the unit tests mock it
  completely and cannot detect a behavioural change in it. Verified three ways:
  the API surface this project uses is byte-for-byte identical between the two
  versions, the upstream changelog for 1.5.1 through 1.6.0 contains only fixes
  with no removals or renames, and a live run of `tests/smoke.py` returned real
  data for all 21 tools before and after the bump.

## [0.3.1] - 2026-08-16

### Fixed
- A fresh installation of 0.3.0 failed on startup with `ModuleNotFoundError: No
  module named 'mcp.server.fastmcp'`. The dependency was declared as
  `mcp[cli]>=1.28.0` with no upper bound, so a new install resolved to mcp 2.0,
  which removed `mcp.server.fastmcp` entirely. The requirement is now
  `mcp[cli]>=1.28.0,<2`. Support for mcp 2.x needs a real migration to its
  `MCPServer` API and is tracked separately.

### Added
- A `fresh-install` CI job that installs the built wheel into a clean
  environment **without** the lockfile and starts it. Every other job installs
  from `uv.lock`, which pins mcp to a working version and therefore hid this
  break from the entire test suite.

## [0.3.0] - 2026-08-16

Version 0.2.3 was prepared but never published, so its entries are folded in
here.

### Changed
- **Breaking:** the import package is now `benethos_yahoo_finance_mcp` (was
  `yahoo_finance_mcp`). Update any client configuration that runs the module
  directly, for example `"args": ["-m", "benethos_yahoo_finance_mcp"]`.
- **Breaking:** the `yahoo-finance-mcp` console script was removed. The single
  entry point is now `benethos-yahoo-finance-mcp`, identical to the PyPI
  distribution name.
- The server identity reported to MCP clients is now
  `benethos-yahoo-finance-mcp` (was `yahoo-finance`).
- The Docker image, the compose project, service, container and volume names,
  and the default cache directory all carry the `benethos-` prefix now. An
  existing cache directory is not migrated, so the first run after upgrading
  starts with an empty cache.
- The README title, the specification title, and the package description now
  lead with "Unofficial", making the absence of any affiliation with Yahoo
  explicit at first glance.

### Fixed
- HTTP transports bound to a non-localhost host (e.g. `0.0.0.0` in Docker) no
  longer reject remote clients with **HTTP 421** ("Invalid Host header"). The
  DNS-rebinding guard was locked to `localhost` at import time and never
  recomputed for the actual bind host, so containers, gateways, and any remote
  caller were refused. It is now derived from the real bind host: localhost
  keeps its protective allow-list, an exposed bind accepts any `Host` by default.

### Added
- `--allowed-hosts` / `YF_MCP_ALLOWED_HOSTS` and `--allowed-origins` /
  `YF_MCP_ALLOWED_ORIGINS` to explicitly lock down the `Host`/`Origin`
  allow-list on an exposed HTTP bind.

## [0.2.2] - 2026-06-25

### Fixed
- `__version__` now resolves correctly. It looked up the old distribution name
  (`yahoo-finance-mcp`), so the published 0.2.1 package reported
  `0.0.0+unknown`. It now queries the actual distribution name
  (`benethos-yahoo-finance-mcp`).

## [0.2.1] - 2026-06-25

### Added
- Published to **PyPI** as `benethos-yahoo-finance-mcp` (the `yahoo-finance-mcp`
  name was already taken by an unrelated project). Install with
  `uvx benethos-yahoo-finance-mcp` — no `git` required.

### Changed
- README install instructions now lead with the PyPI install; the git-URL
  (from-source) method is documented as a fallback.

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

[Unreleased]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.2.2...v0.3.0
[0.2.2]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/benethos-hub/yahoo-finance-mcp/releases/tag/v0.1.0
