# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Every release from 0.4.0 on is available under the new image name
  `ghcr.io/benethos-hub/benethos-yahoo-finance-mcp`. The releases up to 0.7.1,
  published under `ghcr.io/benethos-hub/yahoo-finance-mcp`, were copied over
  with the same digest, minor-line tags included. Nothing changed under the
  old name.

## [0.7.2] - 2026-10-08

A release for running the server in a container. No tool, schema or API
changes, apart from one fix in `get_options`. Everything for containers moves
to `containers/`, with a compose file for production and one for
development, both on a read-only root file system. The image now carries the
name of the PyPI distribution, `ghcr.io/benethos-hub/benethos-yahoo-finance-mcp`.
The old name gets the rest of the 0.7 line as well, and 0.8.0 is the first
release without it.

### Added

- A security policy, `SECURITY.md`: how to report a vulnerability privately
  through GitHub (now switched on for this repository), that fixes go into
  the latest minor line only, and what counts as a finding.

### Changed

- Everything for containers moves to `containers/`. The `Dockerfile` is now
  `containers/images/yahoo-finance-mcp/Dockerfile`, built from the repository
  root with `-f`. The compose file at the root, which switched between
  building and pulling by swapping commented lines, is gone. Instead there
  are two, each in a folder of its own. `containers/production/` pulls the
  published image at the version `YAHOO_FINANCE_MCP_VERSION` in `.env` names,
  required and without a default, and needs no clone.
  `containers/development/` builds from the checkout on `127.0.0.1:8001` under
  a project name of its own, so both can run side by side.
  `containers/README.md` says which is for what. **To move a running setup**,
  take `containers/production/`, copy your old `.env` beside it and add
  `YAHOO_FINANCE_MCP_VERSION`. The project name is the same, so the cache
  volume stays.
- Both compose files run the container on a read-only root file system, with
  a tmpfs for `/tmp` and one for `yfinance`'s cookie and time zone cache in
  the home directory. Without the second, `yfinance` silently does without
  that cache. The README shows the same flags for `docker run`.
- CI checks both compose files: valid, every port on the loopback address,
  read-only, development builds and production pulls the published image.
- Locked dependency refresh of six packages, none of them direct:
  `opentelemetry-api` 1.45.1 under `mcp`, `peewee` 4.5.3 and `platformdirs`
  4.12.4 under `yfinance`, and `typer`, `iniconfig` and `tomli` for
  development only. The tool schemas are byte-identical before and after,
  stdio, streamable-http and sse answer alike, and the live smoke test
  differed only in the live market prices.
- **The container image is now `ghcr.io/benethos-hub/benethos-yahoo-finance-mcp`**,
  the name of the PyPI distribution. Up to 0.7.1 it was named after the
  repository, `ghcr.io/benethos-hub/yahoo-finance-mcp`. The whole 0.7 line is
  pushed under the old name as well, the same image with the same digest, so
  `:0.7` and `:latest` there keep getting updates. **0.8.0 is the first
  release without the old name**, switch before then. The production compose
  file and the README use the new name.
- The PyPI job deploys to the GitHub environment
  `pypi-benethos-yahoo-finance-mcp` instead of `pypi`, so the Deployments list
  names what was deployed. The README's PyPI and container badges name the
  distribution and the image.
- The container image's base `python:3.14-slim` is pinned to its rebuild of
  2026-10-06, for amd64 and arm64 alike. Python stays 3.14.8, the rebuild
  brings the Debian packages underneath up to date.
- The build backend is bounded, `hatchling>=1.27,<2` instead of any version.
  It was the one part of the release pipeline that `uv build` resolved fresh
  and without a limit at publish time. The package builds with 1.27.0 and
  with the newest release.
- Internal tidying, nothing a client sees (tool schemas byte-identical, the
  three transports answer alike): `tickers.upstream` takes `not_found=` for
  exceptions that mean a symbol has no such data, which `get_fund_data` used
  to spell out by hand. `get_quote` and `get_quotes` share the step from
  `fast_info` to a quote row. `cache.DEFAULT_TTLS`, an alias nobody imported,
  is gone. The 250-row defaults name `MAX_ROWS`, the caps on the small period
  and summary tables have names of their own, `http_app` types its transport
  settings, and six docstrings in `yahoo/` are wrapped as paragraphs again.

### Fixed

- `get_options` reads `expiration` like every other date: a stray space is
  dropped, and a value that is no date (`2024-02-30`) gets "Invalid
  expiration ... expected a date as YYYY-MM-DD" before Yahoo is asked. Until
  now both answered "not available" with the list of dates.

## [0.7.1] - 2026-10-05

A maintenance release for the container image and the PyPI page. No tool,
schema or API changes. The image moves to Python 3.14.8 and `mcp` 2.3.0,
where an index installation got the newest `mcp` already, and the README
the PyPI page shows opens with what the server is for.

### Changed
- The container image is built on Python 3.14.8 (was 3.14.7) and uv 0.12.23
  (was 0.12.19). The uv image is now a build stage of its own, pinned to its
  patch release. Dependabot reads `FROM` lines only and proposes only tags of
  the precision already written, so the old `COPY --from=…uv:0.12` reference
  never produced a pull request.
- Locked dependency refresh of seven packages, none of them direct:
  `cryptography` 50.0.2 under `mcp`, `tzdata` 2026.5 and `websockets` 17.2
  under `yfinance`, `python-dotenv` for the `cli` extra, and `ruff`, `mypy`
  and `ast-serialize` for development only. The tool schemas are
  byte-identical before and after, stdio, streamable-http and sse answer
  alike, and the live smoke test returned the same data.
- **`mcp` 2.2.0 → 2.3.0**, kept out of the refresh above. The one change a
  client sees is that `initialize` no longer announces an empty
  `experimental` capability. The tool schemas are byte-identical, and the
  error text of a refused argument and a live quote arrive alike over all
  three transports.
- A second locked refresh of three packages, none of them direct:
  `platformdirs` 4.12.3 and `pytz` 2026.5 under `yfinance`, `rpds-py`
  2026.9.1 under `mcp`. Same checks, same result, and the smoke test
  differed only in the live market prices.
- The README opens with what the server is for. A new section right after
  the disclaimer names the purpose and the typical uses and holds the
  example prompts, and symbol resolution now follows the tool table it
  explains. The other sections are unchanged and keep their anchors.

## [0.7.0] - 2026-09-30

A review closed several security gaps, above all a DNS-rebinding guard that
Compose left off. The log follows written rules and has a new look,
`get_history` checks its arguments before asking Yahoo, the result cache
gets an entry limit, and many errors now name their real cause instead of
an unknown symbol. Underneath, the code is reorganised by subject. A client
sees the tools listed grouped by subject, a limit of 32 characters on
symbols, changed descriptions for `period`, `interval` and `end` and for
the six equity-only tools, and integer columns such as `Volume` as
integers again.

### Security
- `compose.yaml` sets `YF_MCP_ALLOWED_HOSTS` to the loopback names and its
  service name. The image binds `0.0.0.0`, and an exposed bind without an
  allow-list turns the DNS-rebinding guard off, while Compose publishes the
  port on the host's loopback: a web page whose domain an attacker points at
  127.0.0.1 could call every tool from a browser on that machine. The list
  was only a commented-out option.
- A symbol or key from the caller reached the log unfiltered. A line break
  in it forged a second line, an escape sequence reached the terminal, and
  nothing bounded its length. The line keeps printable characters only and
  cuts at 32.
- A symbol goes into the path of Yahoo's URLs, and a slash, a question mark
  or `..` went along unchecked. It now has at most 32 characters, which the
  schema says, and the shape Yahoo uses (letters, digits, `. - ^ = &`).
  Anything else is "not found" before yfinance is asked. 128 symbols from 25
  live searches all fit.
- A loopback bind was recognised by its exact spelling, and `YF_MCP_HOST` was
  not trimmed. `" 127.0.0.1"`, `LOCALHOST` or `127.0.0.2` counted as an
  exposed bind and turned the DNS-rebinding guard off. The decision is now
  made by address.
- The text of every exception inside a Yahoo call went to the model, a
  network error's full URL with Yahoo's crumb in it and a `KeyError` from
  code included. Only yfinance's own errors keep their text now. A network
  error is named by class, and anything unexpected by class too, with its
  traceback in the log.
- On Windows without `LOCALAPPDATA` the cache went to the system temp
  directory, which every user shares, so another user could leave a cache
  file there whose contents were served as tool results. It now goes under
  the home directory. Without a home directory either, the server refuses
  to start with the cache on and says to set `YF_MCP_CACHE_DIR`, instead of
  failing with a bare `RuntimeError`.
- yfinance logged an unknown symbol as up to four ERROR lines, one of them
  Yahoo's whole answer body, which no line of this server may carry. It is
  held at CRITICAL now, the tool's own line still says what failed.
- The Dockerfile's `# syntax=` line pulled a frontend image by a moving tag
  on every build, the one pull the digest pinning did not cover. Nothing
  needs it, and it is gone.

### Added
- The result cache keeps at most 10 000 entries, set with
  `--cache-max-entries` or `YF_MCP_CACHE_MAX_ENTRIES`. The TTLs bounded how
  long an entry lived, not how many there were, and over HTTP a caller
  decides how many distinct keys arrive within one TTL. Each sweep, the one
  at startup included, drops the oldest beyond the limit and gives the pages
  back to the file system, and the log says how many went. Oldest means
  written first, not closest to expiry, so a quote written a second ago is
  never pushed out by yesterday's financials.

### Fixed
- Publishing never compared the release tag with the package version. A tag
  `v0.7.0` on a commit that still said 0.6.1 would have had PyPI refuse the
  upload while the image job pushed `0.7.0`, `0.7` and `latest` with the old
  code. Both publish jobs now stop first when the two differ.
- A pre-release moved the `latest` image tag, and a manual run of the
  publish workflow pushed `edge` from whatever branch it was started on,
  although `edge` is documented as main's state. `latest` now follows full
  releases only, and a manual run builds from main only.
- Six tools describe themselves as empty for ETFs, funds and crypto, then
  answered a correct `SPY` with "No data found, use the search tool":
  `get_earnings`, `get_estimates`, `get_upgrades_downgrades`, `get_holders`,
  `get_insider_activity` and `get_calendar`. They now say that Yahoo keeps
  this data for single stocks only, as `get_options` and `get_sec_filings`
  already did for their cases, and their descriptions and the server
  instructions say an ETF gets that error instead of promising an empty
  answer.
- `get_quote` answered an unreachable Yahoo with "symbol not found": every
  field came back empty and that read as an unknown symbol. It now says
  Yahoo could not be reached. Measured with a dead proxy, an unknown symbol
  and a network failure differ in exactly that `ConnectionError`.
- `get_quotes` threw the whole batch away when looking up one ISIN failed
  in any way other than "not found", against its description. That symbol
  is now listed under `not_found`, and only a rate limit stops the batch.
- A valid sector, industry or market key with nothing from Yahoo answered
  "No data found for symbol 'technology'. Use the search tool". It now says
  Yahoo returned nothing for that key.
- Integer columns came back as floats whenever the frame also held floats,
  every history row's `Volume` as `56123400.0`. They stay integers now.
- The result cache kept a found-nothing answer that is a non-empty dict,
  `get_news` with `count: 0` say, for the whole TTL. A dict whose `count`
  is 0 now counts as empty, like an empty list.
- `--path mcp` without a leading slash passed the start line and then ended
  the server with an `AssertionError` from Starlette. It is a usage error
  now, from the flag and from `YF_MCP_PATH` alike.
- An allowed origin without a scheme left the derived host list empty while
  the guard stayed on, so every client got HTTP 421, and one with a final
  slash never matched, so every browser got 403. A final slash is dropped,
  and an origin without scheme or host stops the start with a message
  naming the expected form.
- Cache TTLs took `nan`, `inf` and negative values. `nan` made every write
  fail with an `IntegrityError`, `inf` never expired. A TTL is a finite
  number of seconds, 0 or more: from the environment anything else is
  reported and ignored, from `--cache-ttl` it is a usage error.
- A failed write to the cache file left its transaction open, holding the
  file's lock until the next write committed it along with its own. Every
  write now commits or rolls back on its own.
- The container's healthcheck reads the port from `YF_MCP_PORT`, while the
  Dockerfile suggested appending CLI flags. With `--port 9000` appended the
  container stayed unhealthy for good. The Dockerfile and the README now
  say to set the port through the variable.
- `get_history` and `get_shares` answered `end` before or on `start` with
  "No data found for symbol", the same wrong lead the argument checks were
  meant to remove. yfinance's `end` is exclusive, so a single day asked as
  the same date twice came back empty too, and the description did not say
  so. Both now require `end` after `start`, the error says why, and the
  `get_history` description calls `end` exclusive. `get_shares` also checks
  the date format first: a wrong one used to bring Python's `strptime` text
  to the model.
- A damaged or locked cache file stopped the server at startup with
  `DatabaseError: file is not a database`, although the cache is only an
  optimisation and a failing cache never fails a call. The server now logs a
  warning and runs without the cache.
- Ctrl+C printed a traceback that read as a crash. The shutdown itself was
  clean: uvicorn finishes and then raises the interrupt again on purpose, so
  the process ends as interrupted, and nothing caught it. The server now
  logs `Stopped by an interrupt` and exits with 130, stdio included.
- The server instructions said Yahoo resolves an ISIN server-side. It does
  so only in its search: asked for `US0378331005` on 2026-09-30, the search
  endpoint answered `AAPL`, while the quote, quoteSummary and chart
  endpoints answered with nothing or 404. yfinance's `Ticker` looks the ISIN
  up through that search and uses the ticker it finds. The instructions now
  say so, and so do the code comments, SPECS and the bug report template.
  The tool schemas are unchanged.
- `get_history` answered an unknown `period` or `interval` with "No data found
  for symbol", because Yahoo answers such a value with no rows, and the model
  went looking for a ticker that was right all along. Both are now checked
  before Yahoo is asked, and so are `start` and `end`, which must be real
  dates written `YYYY-MM-DD`. The error lists what is accepted. `interval`
  comes from a fixed set, which gained `4h`: Yahoo serves it, while `3h`,
  `2d` and `2wk` come back empty. `period` takes the listed values or any
  count of days, weeks, months or years, since `7mo`, `3y` and `2wk` answer
  with data and a strict list would have refused them. Both parameter
  descriptions are now built from the same constants as the check.
- Valid arguments can still find nothing: Yahoo keeps 1m bars for 8 days,
  2m to 90m for 60 and hourly bars for 730, measured on 2026-09-30, so `1m`
  over `1y` came back empty and was reported as an unknown symbol as well.
  No intraday rows now says how far back that interval reaches, and names the
  symbol only as the other possibility.

### Changed
- Locked dependency refresh of seven packages, none of them direct:
  `sse-starlette` 3.4 → 3.5, `pyjwt`, `peewee`, `platformdirs`,
  `charset-normalizer`, and `coverage` and `librt` for development only. The
  tool schemas are byte-identical before and after, stdio, streamable-http
  and sse answer alike, and the live smoke test returned the same data.
- The result cache's key carries the package version, so a release never
  serves a result shape from before it, and keeps the type of every value
  that is not text: `True` and `"true"` were one key. Existing cache entries
  are not read again and expire on their own.
- The cache waits at most half a second for another process holding its
  file, not five. The wait blocked every tool call, and past it the call
  runs without the cache as before.
- Compose drops every Linux capability and sets `no-new-privileges`. The
  server runs as a non-root user on a high port and needs none.
- Every CI and publish job has a `timeout-minutes`, well above what it
  takes today.
- Dependabot groups minor and patch updates per ecosystem into one pull
  request. Major updates still come alone, and so do `yfinance` and `mcp`,
  which need their own checks.
- `.dockerignore` keeps `dist`, `build`, coverage and tool caches and
  `.claude` out of the build context.
- The bearer token no longer appears in the `repr` of the settings.
- Every log line names its source short: `server`, `tools`, `yahoo`,
  `cache`, `uvicorn`, `http`, instead of the full logger name.
  `uvicorn.error` read as if something had failed while it is only
  uvicorn's server log, and shows as `uvicorn`. At a terminal the log comes
  in colour: the time dim, the level in colour, the source in cyan and a
  request as method, path, status and client. `NO_COLOR` turns the colours
  off. Every line, at a terminal or in a container log, pads the level and
  writes the time the same way, as ISO 8601
  `2026-09-30T13:19:02.840+02:00`: a `T` instead of the space, a point
  before the milliseconds instead of a comma, and the offset added. The time
  is local, which in a container is UTC unless `TZ` is set, now shown
  commented out in `compose.yaml` and `.env.example`.
- Every call builds its own `yf.Ticker`. They used to be shared for 60
  seconds, and the SDK runs the tools in worker threads, so two calls on one
  symbol could fill the same object's lazily loaded fields at once, which
  yfinance promises nothing about. Nothing was observed, and nothing in the
  answers or the schemas changes. Building one takes about 0.01 ms and no
  request, and an ISIN's lookup is kept by yfinance itself. A lock per
  symbol was the alternative and was dropped: it would have to be held for
  the whole use of the object, so in all eighteen functions that build one
  or through a symbol argument to `upstream()`, and it would have made calls
  on one symbol wait for each other.
- The log follows written rules. Every tool call leaves one line: an INFO
  with the tool, its symbol or key, how many rows came back, whether the
  result was cut, how long it took and whether the result cache answered,
  or a WARNING naming the error's class. Before, a call left no line at all
  unless it failed, and then only the SDK's INFO line quoting the message
  written for the model. A Yahoo rate limit is now a WARNING of its own, and
  so are arguments a tool's schema refused, by field name.
  A line may carry a symbol or a key. It never carries the bearer token, a
  search query, a URL's query string, anything from Yahoo's answer or the
  text of an error. The SDK's `mcp` logger and `sse_starlette` are held at
  WARNING whatever the level: the first quoted every failed call's text at
  INFO, the second logged every tool result in full at DEBUG. yfinance,
  curl_cffi, urllib3, peewee, httpx and httpcore are held there too. The
  log level applies to this server's own lines and the request log only.
  Every other library stays at WARNING, where `--log-level DEBUG` used to
  open all of them, asyncio's line about its event loop included.
  uvicorn's request log goes to stderr with everything else instead of to
  stdout, without the query string. At INFO it shows only refused requests,
  status 400 and above, 401 and 421 included, with the address that tried.
  At DEBUG it shows every request.
  Logging is set up by the command line, no longer at import, and a server
  built by a program that imports the package leaves its logging alone. The
  SDK's Rich handler, which its constructor installs, is taken back.
- The compose file caps the log Docker keeps of the container at 5 files
  of 10 MB, the oldest dropped first. Before, the log grew for as long as
  the container ran, and uvicorn adds a line per request to it. The README
  says how to keep more, hand the log to `journald`, or set the same cap on
  a plain `docker run`.
- The result cache file shrinks after a sweep. SQLite reuses the pages a
  deletion frees but never hands them back on its own, so the file stayed
  at its largest size for good: 2000 expired entries purged left a 1.4 MB
  file holding nothing. `auto_vacuum` in its incremental mode gives the
  pages back after every sweep, at startup, every hundredth write and on
  `clear`. A file made by an earlier version is rewritten once when the
  server opens it, which takes a moment for a large one, and the log says
  so.
- An unusable `YF_MCP_TRANSPORT`, `YF_MCP_PORT` or `YF_MCP_LOG_LEVEL` is
  reported with a warning at startup, as an unusable `YF_MCP_CACHE_TTL_*`
  already was. The server still falls back to the default. Before, a typo
  such as `YF_MCP_TRANSPORT=streamable_http` started a stdio server that
  nobody could reach, and nothing said why.
- The console script now points at `benethos_yahoo_finance_mcp.cli:main`.
  The command line is unchanged. The configuration is resolved once, flag
  over environment over default, in the new `settings` module, and no module
  reads the environment on its own any more.
- `client.py` is now the `yahoo` package, one module per subject: quotes,
  company, analysts, ownership, options, funds and browse, with the `Ticker`
  construction and error mapping in `yahoo.tickers`. The functions are
  unchanged and importable from `benethos_yahoo_finance_mcp.yahoo`.
- The tools moved from `server.py` into the `tools` package, which mirrors
  `yahoo` module for module. Their names, parameters, descriptions and
  annotations were byte for byte the same at the move, and what this release
  changes in them is listed above. The order a client lists them in
  now follows the subjects: search and quotes first, then company data,
  analysts, ownership, options, funds and browsing by key. `search` stays
  first, and `get_calendar` and `get_shares` now sit with the other company
  tools, ahead of the analyst ones.

## [0.6.1] - 2026-09-27

A maintenance release for the container image and Compose. No tool, schema
or API changes.

### Added
- A `.env.example` and an optional `env_file: .env` in `compose.yaml`, so the
  bearer token no longer has to be written into the tracked `compose.yaml`.
  Copy the example to `.env` and set `YF_MCP_BEARER_TOKEN` there. Without a
  `.env` the service runs exactly as before. `.env` is now ignored by git and
  left out of the Docker build context. Only Compose reads the file, the
  server itself still takes its settings from the environment and the
  command line. The optional `env_file` needs Docker Compose 2.24 or newer.
  The ignore rules also keep a local `.env` and Claude Code's
  `.claude/settings.local.json` out of a locally built sdist, since hatchling
  packs every file `.gitignore` does not exclude. The published sdists were
  never affected, CI builds them from a clean checkout.

### Changed
- Locked `platformdirs` 4.11.14 → 4.12.0, the one package that had moved
  since 0.6.0. `yfinance` asks it where to keep its own cache of time zones,
  cookies and resolved ISINs. The paths are unchanged on Windows and, in the
  container, for root, for `appuser` and for an arbitrary UID, which Docker
  gives `HOME=/`. One thing does change: with no passwd entry **and** no
  `HOME` at all, 4.12.0 raises where 4.11.14 quietly returned the relative
  path `~/.cache`. `yfinance` asks at import time, so the server then stops
  at startup, before any tool could catch anything. The message says what to
  set, the traceback goes to stderr, and stdout stays clean. Docker and
  Kubernetes always set `HOME`, so reaching that takes removing it on
  purpose, and the README now says what to set if you do. A live smoke run
  before and after returned the same data in all 26 sections.

## [0.6.0] - 2026-09-25

A minor release rather than a patch, because several tools answer
differently now. `get_news` rejects a `limit` above 10, `get_options` returns
different strikes for a wide chain and carries a `truncated` flag, statement
columns and option rows have new keys, and `get_dividends` raises for a
symbol it used to answer with empty lists. A caller that stored or parsed
those shapes should look at the entries below.

### Added
- Every tool now carries the MCP annotations `readOnlyHint: true` and
  `openWorldHint: true`. The server only reads, and every tool asks Yahoo, but
  a client had no way to know either and had to treat each tool as one that
  might change something. A client that honours the hints can call them
  without a confirmation prompt. `destructiveHint` and `idempotentHint` are
  left out, since the spec gives them meaning only for tools that are not
  read-only. The tool list grows by about 1.4 KB.

### Changed
- `get_financials` names its period columns with a plain date,
  `2025-09-30`, where it used to print `2025-09-30 00:00:00`. The time was
  always midnight and said nothing, and every row repeats every column name.
- Locked dependency refresh of fourteen packages, none of them direct
  except the linter: `starlette` 1.6 → 1.7, `uvicorn` 0.53 → 0.54,
  `httpx2` and `httpcore2` 2.12 → 2.13, `pandas` 3.0.5 → 3.0.6, `urllib3`
  2.7 → 2.8, `pyjwt`, `protobuf`, `soupsieve`, `opentelemetry-api`, `idna`,
  `platformdirs`, `pytz` and `ruff` 0.16.8 → 0.16.9. `urllib3` 2.8.0 closes
  two high-severity advisories, an HTTPS proxy's TLS settings being
  overridden and an unbounded chunk-size line, which had no CVE at release
  and so no Dependabot alert. It sits under `yfinance`'s fallback through
  `requests`, not the `curl_cffi` path used by default, but it ships in the
  image. The packages sit under `mcp` and `yfinance`, so both got their
  checks: the tool schemas are byte-identical, stdio stays clean, a tool
  error's text arrives over stdio and streamable-http alike, the bearer guard
  still answers 401 and 200, and a live smoke run before and after returned
  data in all 26 sections, each of them byte-identical.
- The descriptions of `get_history` and `get_financials` no longer repeat the
  allowed values their parameters already list. Every client pays for each
  tool description on every request, and these two said everything twice.
- For anyone calling the `client` module from Python rather than through
  MCP: the row cap is a keyword named `limit` in every function now. It used
  to be `max_rows` in eleven of them and `limit` in the rest, and
  `get_quotes` called its symbol cap `max_symbols`. The tools were always
  `limit` and are unchanged. `formatting.dataframe_to_records` accepts
  `None` and a `head=True` flag for frames ranked from the top, and the
  cache decorator takes an optional `worth_keeping` predicate.

### Fixed
- `--allowed-origins` on its own (or `YF_MCP_ALLOWED_ORIGINS`) locked every
  client out with HTTP 421. It switched the DNS-rebinding guard on with an
  empty `Host` allow-list, and the SDK matches every request's `Host` against
  that list, so nothing ever matched. The hosts are now derived from the
  origins, the same way the origins were already derived from
  `--allowed-hosts`.
- `get_financials` returned at most 60 line items and kept the last ones, so
  a longer statement lost its top without saying so. Apple's annual balance
  sheet has 69 rows, and Net Debt, Total Debt, Working Capital and Tangible
  Book Value were among the nine that went missing. Every line item is
  returned now, in the order Yahoo reports them.
- The in-memory ticker cache grew without bound. Every distinct symbol left a
  `yf.Ticker` behind, with whatever it had loaded, and nothing ever removed
  one. Over HTTP a caller decides how many symbols that is. Expired entries
  are now dropped on every insert and the cache holds at most 256, least
  recently used first out.
- A symbol shaped like an ISIN that Yahoo cannot resolve, say one with a wrong
  check digit, reached the model as a bare `Error executing tool`. yfinance
  resolves ISINs in the `Ticker` constructor and raises there, and the
  constructor was the one upstream call outside every `try`. It now answers
  as an unknown symbol, and a rate limit during the lookup as a rate limit.
  In `get_quotes` such a symbol used to fail the whole batch, and it is now
  listed under `not_found` like any other miss. The lookup no longer runs
  under the ticker cache's lock either, where one slow search held up every
  other tool call.
- A failing result cache failed the tool with it. Two processes sharing one
  cache directory can hold the database locked, and a damaged file raises on
  every read, and either error reached the model as `Error executing tool`.
  The cache now steps aside on its own errors: the data is fetched and
  returned as if caching were off, with a warning in the log.
- `get_news` offered up to 30 headlines and never delivered more than 10. It
  read yfinance's `.news`, which always asks for its default of ten, and
  Yahoo serves no more than ten per symbol anyway, whatever the request says.
  The count now goes upstream, and the ceiling is 10, the most that can ever
  arrive.
- `get_options` cut a wide chain to its 60 highest strikes. Chains come sorted
  by strike, and SPY carries some 300 per expiry, so the strikes around the
  current price, the ones most questions are about, were exactly the ones
  left out. The 60 per side are now centred where the contracts switch
  between in and out of the money, and a new `truncated` flag says when a
  chain was cut.
- `get_dividends` answered an unknown symbol with two empty lists, the same
  answer a real company that never paid a dividend gets, while every other
  tool says the symbol was not found. yfinance does tell the two apart, with
  `None` for an unknown symbol and an empty series for a real one, and the
  tool now does too.
- `get_shares` described its default as the full history. Without `start`,
  yfinance looks back 18 months and no further, so a question about share
  counts five years ago got a series that silently began 18 months back. The
  description now says so and tells the caller to pass `start` for anything
  older.
- `get_recommendations` carried a meaningless `index` of 0 to 3 on every row
  of the trend table, the frame's row counter. The rows are now keyed by
  `period` alone, which is what the counter stood next to. Option contracts
  from `get_options` carried the same counter and are now keyed by
  `contractSymbol`.
- With the result cache on, a `get_quotes` call in which every symbol missed
  was stored like any other answer, and repeating it within 30 seconds
  returned the same empty result without asking Yahoo again. The cache
  skipped empty results, but this one is a dict with a `count` of zero and
  never looked empty. Such an answer is no longer stored.
- The result cache swept expired entries at startup only, so a long-running
  HTTP server kept every answer nobody asked for again. Every hundredth write
  now sweeps as well.
- A port outside 1 to 65535, from `--port` or `YF_MCP_PORT`, got as far as
  uvicorn and ended in a traceback. It is a usage error now, with a message
  saying what the range is.

### Security
- Every action in the workflows is pinned to a full commit SHA, with the
  version in a comment, and both base images in the `Dockerfile` by digest
  next to their tag. A tag is a pointer its owner can move, and the publish
  workflow holds the credentials that push to PyPI and ghcr. Dependabot keeps
  SHAs and digests current, one pull request per release.
- The bearer guard checked HTTP requests and waved every other ASGI scope
  through unchecked. The SDK serves no WebSocket route today, so nothing was
  reachable that way, but the day one appears it would have been open. Only
  the lifespan scope passes now. A WebSocket handshake is closed with 1008
  before it is accepted, and any other scope type is not answered.

## [0.5.2] - 2026-09-14

### Changed
- Locked dependency updates: `mcp` and `mcp-types` 2.1.1 → 2.2.0, `lxml`
  6.1.2 → 6.1.3 and the linter `ruff` 0.16.5 → 0.16.7, plus the eleven
  transitive packages that had moved underneath them since the last refresh,
  among them `uvicorn` 0.52 → 0.53, `sse-starlette`, `anyio`, `curl-cffi`,
  `numpy` and `peewee`. Dependabot raises direct dependencies only, so the
  rest moves when someone asks. Only `uv.lock` moved, so the declared ranges
  in `pyproject.toml` are untouched and an installation from PyPI resolves
  the same way it did before. The container image builds against the
  lockfile and is therefore the one place the new versions actually land,
  which is what this release is for: the `:latest` image still carried the
  lockfile of 0.5.1.

  `lxml` 6.1.3 stops parsing external parameter entities when only internal
  ones were asked for, the XXE class of problem. It sits under the HTML table
  scraping in `yfinance`, so reaching it would take control of Yahoo's
  response, but an image without a known hardening is an image to rebuild.

  The `mcp` step is the one that needed a look, since the unit tests never
  travel through the SDK. The tool schemas are byte-identical across the two
  versions, and a tool error's text still reaches the caller, in-process and
  over streamable-http alike. One server default did change: an idle stateful
  streamable-http session now expires after 30 minutes, and a server holds at
  most 10 000 of them. A client that keeps the GET stream open, as the SDK's
  own does, never notices. Any other client gets a 404 after half an hour of
  silence and initialises again.

  The packages under `yfinance` got the treatment a `yfinance` bump gets: a
  live smoke run before and after, 26 sections with data both times, 24 of
  them byte-identical, and the two that differ are the market overviews,
  which carry live prices.

  The formatter is the part of a `ruff` bump that can change a repository
  without anyone asking for it, and `ruff format --check` reports every file
  unchanged on both steps.

## [0.5.1] - 2026-09-02

### Changed
- Refreshed the locked dependencies. Fourteen packages moved, all of them patch
  or minor: `mcp` and `mcp-types` 2.0.0 → 2.1.1, the linter `ruff`, and eleven
  transitive ones, among them `cryptography`, `pydantic`, `curl-cffi`,
  `protobuf`, `peewee` and `websockets`. The declared ranges in
  `pyproject.toml` are unchanged, so this reaches an installation from PyPI not
  at all and the container image by way of its locked build.

  `yfinance` stays where it is and gets its own change. The unit tests mock it
  completely, so they stay green through any shift in its behaviour and cannot
  say whether an upgrade broke something.

  The drift is what made the size of this refresh possible. Dependabot was
  watching the `pip` ecosystem, which does not read `uv.lock`, and every
  requirement in `pyproject.toml` is a `>=`, so there was never a constraint to
  raise either. The entry now names `uv`.
- **`yfinance` 1.6.0 → 1.7.0**, kept out of the refresh above and upgraded on
  its own. The unit tests mock yfinance completely, so they stay green through
  any change in its behaviour, field names or response shapes and say nothing
  about an upgrade at all. `tests/smoke.py` does, run against Yahoo once on
  either side of the bump: all 26 sections returned data both times and no
  field went missing. The two runs differ only where they must, in the market
  overviews, whose futures and European indices kept moving between them.

### Fixed
- **Tool error messages reach the model again.** `ToolError` derived from
  plain `Exception`, and since `mcp` 2.1.0 the SDK forwards the text only for
  errors deriving from its own `ToolError`. Everything else counts as
  unexpected: it is logged with a traceback and the caller is told
  `Error executing tool <name>` and nothing more.

  What went missing is the part that tells the model what to do next. The
  advice to look a symbol up with the `search` tool, the distinction between a
  wrong symbol and data that does not exist for that class of instrument at
  all, and the note that a rate limit simply needs a retry later. All of it was
  replaced by a bare statement that something failed, which leaves the model to
  guess.

  The mocked suite could not see it, because it stops at the client layer and
  never travels through the SDK. A test now makes that trip and asserts the
  text arrives.

## [0.5.0] - 2026-08-23

### Added
- **An optional bearer token for the HTTP transports.** Set
  `YF_MCP_BEARER_TOKEN` and every HTTP request must carry
  `Authorization: Bearer <token>`, or it gets HTTP 401 with
  `WWW-Authenticate: Bearer` and a body that reveals nothing about why. Until
  now anything that could route to the port could call every tool, and the only
  thing standing in front of it was the choice to bind to the loopback address.

  It stays **off by default**, because the ordinary case is a server on the
  machine that uses it, where a token guards against nothing. It is a single
  shared secret compared in constant time, not an OAuth flow — this server
  speaks for nobody and has no user to authorize. stdio ignores it and says so
  in the log: the client owns that process and nothing else can reach it.
  Serving HTTP without one now logs a warning naming the address anyone could
  reach.

  There is deliberately no command-line flag. An argument is visible in the
  process list to every other user on the machine and lands in shell history.

  A token does not make a port safe to publish. The data here is public and
  read-only, so the realistic damage is somebody spending your Yahoo rate
  limit. Beyond a trusted network, a reverse proxy that authenticates is still
  the answer.
- **`--version`.** The version was published in two places already, in the
  package metadata and in the MCP handshake, and neither is reachable from a
  shell: one needs an import, the other needs an open session. Anyone running
  the server from a container had no way to answer "which version is this?" at
  all. `benethos-yahoo-finance-mcp --version` now prints it, and
  `docker run --rm <image> --version` works the same way. The bug report
  template asks for exactly that, which is what brought the gap to light.
- A test keeps the README's tool list in step with the registry, in both
  directions. Adding a tool and forgetting its row leaves it working, tested and
  invisible to anyone reading the documentation, and a row left behind after a
  rename sends readers after something that does not exist.
- A test keeps the version examples in the documentation honest. The README
  install pin, the image tags in README and Compose file, and the placeholder in
  the bug report template must all name the current version, or the suite goes
  red. Three of them were missed during a release and caught only by sweeping
  the repository a second time.

## [0.4.1] - 2026-08-23

### Changed
- Refreshed the locked dependencies. Ten packages moved, all of them patch or
  minor and all of them transitive — `curl-cffi`, `httpx2`/`httpcore2`, `lxml`,
  `protobuf`, `idna`, `python-dotenv`, `pygments`, `ruff` and `uvicorn`. The
  declared ranges in `pyproject.toml` are unchanged, so this reaches an
  installation from PyPI not at all and the container image by way of its
  locked build. `mcp`, `yfinance` and `pandas` were already current.

### Added
- **The package now ships a PEP 561 `py.typed` marker.** Every module here is
  annotated and mypy runs as a CI gate, but none of that reached anyone who
  installed the package: a type checker treats an installed package without the
  marker as untyped and skips it entirely, however complete the annotations are.
  Checking a file that calls `client.get_quote(123)` against the installed
  wheel now reports `Argument 1 to "get_quote" has incompatible type "int"`
  where it previously reported only `module is installed, but missing library
  stubs or py.typed marker` and looked no further.

  Two separate guards, because a file that exists is not a file that ships. A
  test asserts the marker sits beside the code and is empty, and the release
  workflow opens the built wheel and refuses to upload one that does not contain
  it. Losing the marker breaks downstream type checking without failing a test,
  an import or the build, and a version once on PyPI cannot be replaced.

### Fixed
- **The licence links on the PyPI project page led nowhere.** The README is
  shipped verbatim as the package description, and PyPI renders that text
  without the repository around it, so the three relative `](LICENSE)` targets
  resolved to `pypi.org/project/benethos-yahoo-finance-mcp/LICENSE`. They now
  point at the file on GitHub. Anchor links are unaffected, PyPI rewrites those
  to `#user-content-…` and they work.

  A unit test now rejects any relative link target in the README, because this
  class of mistake cannot be repaired after the fact: PyPI re-renders the
  description only when a new distribution is uploaded.
- The container package page on GitHub said "No description provided". The
  description was never missing — `metadata-action` writes the OCI labels into
  the image configuration, and 0.4.0 carries all of them, but for a multi-arch
  image the package page reads the annotations on the **index**, the manifest
  list above the per-architecture manifests. Those were empty, because
  annotations default to the manifest level only. The release workflow now sets
  `DOCKER_METADATA_ANNOTATIONS_LEVELS: index,manifest` and passes the
  annotations to the build, so description, source, licence and version appear
  where GitHub looks for them. This takes effect with the next published
  release.
- The already-published 0.4.0 index was repaired in place with a one-shot
  `workflow_dispatch` job that rewrote it through `docker buildx imagetools
  create`. Nothing was rebuilt and no layer was re-uploaded — the
  per-architecture manifests kept their digests, the `created` label still reads
  `2026-08-16T20:56:00.877Z`, and only the index itself was written anew.

  **The `0.4.0`, `0.4` and `latest` tags therefore resolve to a new index
  digest**, `sha256:284e11e5…` instead of `sha256:8b184a89…`. Anyone who pinned
  the old digest has to repin. The description picked up on the way is the
  current repository description, which has grown since the release, so the
  image now advertises "read-only, stdio or HTTP".

  The job was removed again once it had run, since every release from here on
  annotates the index by itself.

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
- **The example prompts were rewritten.** Several asked for things the tools do
  not deliver as written — the 50/200-day moving averages, which `get_quote`
  returns ready-made, an average daily volume that no tool reports, and a
  drawdown "since inception" that the 250-row cap silently reduces to the last
  year at the default daily interval. They now ask questions that hold, and the
  two options and filings examples say `[US Ticker]`, since Yahoo carries
  neither outside the United States.
- The closing note claimed the server returns "only raw market data". It does
  not compute anything itself, but it passes Yahoo's derived figures straight
  through — moving averages, P/E, beta, dividend yield, yearly change. The note
  now says what it meant.
- **`get_company_info` answered with a different symbol than it was asked
  about.** `"symbol"` sat first in the curated field list, so the copy loop
  overwrote the echoed input with Yahoo's resolved ticker. Asking about
  `US0378331005` returned `AAPL` while every other tool echoed the ISIN, which
  made results from different tools impossible to line up. The input is echoed
  now, and the resolved ticker is reported as `resolved_symbol` when it differs
  — so an ISIN gains the information instead of losing it. A plain ticker
  resolves to itself and the extra field is omitted, which is why this was
  invisible unless you passed an ISIN.
- Semicolons are gone from everything a reader or the model sees — nine tool
  descriptions, three parameter descriptions, seven CLI help texts, four error
  messages, the README and the specification. A house style rule the text had
  drifted away from. What remains sits inside code blocks, where a semicolon is
  Python rather than prose.
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

[Unreleased]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.7.2...HEAD
[0.7.2]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.6.1...v0.7.0
[0.6.1]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.5.2...v0.6.0
[0.5.2]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.2.2...v0.3.0
[0.2.2]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/benethos-hub/yahoo-finance-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/benethos-hub/yahoo-finance-mcp/releases/tag/v0.1.0
