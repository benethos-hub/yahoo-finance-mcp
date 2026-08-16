# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-08-16

### Changed
- Migrated to the **mcp 2.x SDK**. `mcp.server.fastmcp.FastMCP` was removed
  upstream and replaced by `mcp.server.mcpserver.MCPServer`. The requirement is
  now `mcp>=2.0.0,<3`, so the temporary cap from 0.3.1 is gone.
- Transport options are no longer written into mutable global settings. Host,
  port, URL path and the DNS-rebinding guard are passed to `MCPServer.run()` as
  explicit arguments, and stdio is handed none of them at all. This removes the
  cause of the HTTP 421 bug fixed in 0.3.0 rather than compensating for it.
  Tools, options and output shapes are unchanged by the migration itself.
- **Docker Compose now publishes the port on `127.0.0.1` only.** The server has
  no authentication of its own and has no business on the LAN. It stays reachable
  from the host, including from Windows when Compose runs in WSL. To expose it,
  remove the prefix from the `ports:` entry and put a reverse proxy with
  authentication in front.
- **The tool descriptions are roughly a third smaller**, from about 23,200 to
  16,400 characters. That is what an MCP client places in the model's context on
  every single request, so it is paid continuously. Almost none of it came from
  rewording: a quarter of the payload was one paragraph repeated 17 times,
  warning that a ticker is not an ISIN, and that warning no longer applies.
- The compose volume is declared as `cache` rather than
  `benethos-yahoo-finance-mcp-cache`, since Compose prefixes it with the project
  name anyway. An existing volume is not carried over.

### Added
- Tool **`get_market`** — trading status and headline index summary for a
  market, taking one of eight fixed market keys (`US`, `GB`, `ASIA`, `EUROPE`,
  `RATES`, `COMMODITIES`, `CURRENCIES`, `CRYPTOCURRENCIES`) rather than a
  ticker. Answers whether a market is open and when it next opens or closes,
  plus price, previous close and change for the headline indices. Only `US`
  serves a trading status upstream, so `status` is `null` for the other keys
  while the index summary works for all of them.
- The container image is **published to the GitHub Container Registry** on every
  release, as `ghcr.io/benethos-hub/yahoo-finance-mcp`, built for `linux/amd64`
  and `linux/arm64`. Tags follow the release: `0.4.0`, `0.4` and `latest`. Until
  now the image existed only for whoever cloned the repository and built it
  themselves. Authentication uses the automatic `GITHUB_TOKEN`, so the project
  stores no registry credentials. The workflow can also be triggered by hand,
  which builds and pushes `edge` from `main` without touching PyPI.
- The server now reports a human-readable `title` ("Unofficial Yahoo Finance
  MCP Server") next to its programmatic `name`. The 1.x SDK defined the field
  but never passed it through, so clients had only the name to display.
- The server now reports its own package version in the handshake instead of an
  empty string.
- Two tests covering gaps found during the migration: the default URL path of
  each HTTP transport, and that stdio receives no transport security settings.
- Server-level `instructions`, sent once at handshake rather than per request.
  They collect what holds across the whole server: the symbol rules, that empty
  results are normal for the wrong instrument type, that rate limits are
  temporary, that **currencies are never converted**, and that most tools cap
  their results **silently** — only `get_history` and `get_quotes` report a
  `truncated` flag. Note that not every client surfaces this field.
- **Python 3.14** in the CI matrix and the package classifiers. Both had stopped
  at 3.13 while the documentation claimed the project was verified on 3.14.
- README badges for CI status, PyPI version, supported Python versions, test
  coverage and licence.
- A bug report issue form. Most reports this project can expect are not defects,
  so it asks up front to rule out rate limiting, fields that are empty by design
  for the instrument type, and symbols that are neither a ticker nor an ISIN.
- A `## Trademarks` section in the README. The disclaimer already named them,
  buried among five other bullet points.
- `compose.yaml` now states the build-or-pull choice instead of only supporting
  one of them. It still builds as shipped, and swapping two commented lines
  makes it pull the published image, at which point the file is all an operator
  needs. A single file was kept deliberately: there is one service and exactly
  one thing that differs between developing and operating, so a second file
  would duplicate ports, volumes and environment for the sake of two lines.
- A `docker run ghcr.io/...` example in the README. Pulling the published image
  is now the shortest path to a running server, so it leads the Docker section
  and building it yourself follows as the alternative.
- A `## Compatible clients` section in the README, grouped by transport rather
  than by product name. MCP is not tied to one application, and the question a
  reader actually has is which start command their client needs. Naming clients
  alone would also age badly, while the three transports do not.

### Fixed
- **`get_company_info` answered with a different symbol than it was asked
  about.** `"symbol"` sat first in the curated field list, so the copy loop
  overwrote the echoed input with Yahoo's resolved ticker. Asking about
  `US0378331005` returned `AAPL` while every other tool echoed the ISIN, which
  made results from different tools impossible to line up. The input is echoed
  now, and the resolved ticker is reported as `resolved_symbol` when it differs
  — so an ISIN gains the information instead of losing it. A plain ticker
  resolves to itself and the extra field is omitted, which is why this was
  invisible unless you passed an ISIN.
- Semicolons are gone from everything the user or the model reads — nine tool
  descriptions, three parameter descriptions, seven CLI help texts and four
  error messages. A house style rule that the text had drifted away from.
- The `get_options` and `get_sec_filings` descriptions now name the restriction
  that makes their results empty, so a model knows before calling rather than
  only from the error. `get_sec_filings` had said "equity-only", which is true
  but misses the larger limit — a non-US equity is an equity and still has no
  filings.
- **`get_options` and `get_sec_filings` claimed that valid symbols do not
  exist.** Both raised the standard "No data found for symbol X, use the
  'search' tool to look it up" whenever a result was empty, but for these two
  an empty result is the normal case for everything outside the United States.
  Yahoo lists option chains for US instruments only, and only SEC registrants
  file with the SEC. Probed live: `SAP.DE`, `NESN.SW` and `7203.T` — SAP, Nestlé
  and Toyota — were all reported as not found by both tools. A model asking
  about options on Toyota was told its ticker was wrong and sent to look up a
  symbol that was already correct. The message now names the reason and states
  that an empty result does not show the symbol is wrong. Telling the two cases
  apart for certain would need a second upstream request per failure, which is
  not spent here — the message stays accurate either way, just not decisive.
- The README's install-from-source example invoked `yahoo-finance-mcp`, a console
  script that was removed in 0.3.0 when the package was renamed, so the command
  as printed could only fail. It now uses `benethos-yahoo-finance-mcp`, verified
  by running it.
- Three statements in the documentation were false and are corrected. **WKNs**
  were described as something `search` resolves — it resolves none of them, so
  the advice led into a guaranteed-empty call. **Plain ISINs** were declared
  invalid as symbols, while all 18 symbol-taking tools return correct data for
  one, because Yahoo resolves them server-side. This is new upstream behaviour,
  so the claim was accurate when written. The bug report form repeated the ISIN
  claim, asking reporters to rule out a call that works.
- The specification claimed all CI jobs install from `uv.lock`, which stopped
  being true when the `fresh-install` job was added, and that Dependabot keeps
  the Python dependencies current, which it cannot do while every requirement is
  an open `>=` range.

### Removed
- `TODO.md`. Untouched since June, referenced by nothing, and its "Future
  features" section duplicated SPECS §11 under a heading pointing at SPECS §11.
  The two had already drifted apart.

### Maintenance
- **The container base image moves from `python:3.12-slim` to
  `python:3.14-slim`**, and the pinned uv image from 0.11 to 0.12. The image had
  been two Python releases behind the version the project is developed and
  tested on. The three slim images are the same size to within a megabyte, so
  nothing is traded here. Verified by building it, importing the full stack
  (pandas 3.0.5, numpy 2.5.2, lxml, curl_cffi), registering all 22 tools and
  serving HTTP from the running container.
- The `docker` CI job now also builds for **linux/arm64**. The release workflow
  publishes both architectures while CI only ever built amd64, so an
  arm64-specific break would have surfaced during a release rather than in the
  pull request that caused it.
- **The runtime dependency is plain `mcp` instead of `mcp[cli]`.** The extra
  exists for the `mcp` command (`dev`, `run`, `install`) and drags typer, rich,
  pygments, markdown-it-py, mdurl, shellingham and python-dotenv along with it.
  None of them is imported anywhere in this package, which brings its own
  argparse entry point, so a clean install drops from 59 packages to 51 and the
  container image loses roughly 14 MB. `mcp[cli]` moved to the `dev` extra, so
  `mcp dev` and the MCP Inspector stay available while working on the project.
  Verified with a full stdio round trip — handshake, tool listing and a live
  `get_market` call — against a fresh install of the built wheel.
- Broadened the package keywords from five to ten, adding `mcp-server`,
  `model-context-protocol`, `financial-data`, `market-data` and `stock-market`.
  They now mirror the GitHub repository topics, minus `python`, which says
  nothing on a Python index. Four classifiers were added alongside them —
  `Environment :: Console`, `Financial :: Investment`, `Artificial Intelligence`
  and `Information Analysis` — because PyPI lets visitors filter by classifier
  but not by keyword.
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

[Unreleased]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.2.2...v0.3.0
[0.2.2]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/benethos-hub/yahoo-finance-mcp/releases/tag/v0.1.0
