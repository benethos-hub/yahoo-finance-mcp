# Concept: transport and runtime

Part of the [concept](../CONCEPT.md): section 4.

## 4. Transport & runtime

- **Transport:** selectable via `--transport`:
  - `stdio` (default) — local subprocess for Claude Desktop and similar.
  - `streamable-http` / `sse` — standalone, network-reachable HTTP service.
- **Logging:** always to stderr, one handler, installed by `cli.main` through
  `logbook.output.configure` and never at import, so under stdio stdout
  carries JSON-RPC only. `build_server` takes back the `RichHandler` the SDK's
  constructor installs, so a program that imports the package keeps its own
  logging. Every line is a function in `logbook/` (`lifecycle`, `calls`,
  `cache`, `upstream`), and nothing else imports `logging`, which
  `tests/test_logbook_catalog.py` checks along with the parameter vocabulary.
  - **How a line looks** (`logbook/formats.py`). Every line names its
    source short: `server`, `tools`, `yahoo`, `cache`, `uvicorn`, `http`, and
    any other library by its logger name. uvicorn calls its server log
    `uvicorn.error`, after the web servers' error log that holds everything
    a server says about itself, and written out a start read as a failure.
    Every line writes the time the same way, as ISO 8601 to the millisecond
    with its offset. Without a terminal, in a container log or the file
    Claude Desktop keeps, a line is plain:
    `2026-09-30T13:19:02.840+02:00 INFO     uvicorn: Started server process`.
    When stderr is a terminal and `NO_COLOR` is not set, the time is dim,
    the level in colour, the source in cyan and a request is method, path,
    status in colour and the client.
  - **Levels.** ERROR only from the SDK, with a traceback, for an exception
    that is not a `ToolError`. WARNING for a tool call that raised, a Yahoo
    rate limit, arguments a schema refused, a cache file that failed, an
    unguarded port, a token under stdio, an unusable setting. INFO for
    startup, the cache state, one line per tool call and a stop by Ctrl+C.
    DEBUG for every answered HTTP request.
  - **Ctrl+C.** uvicorn shuts down cleanly and then raises the interrupt
    again, so the process ends as interrupted. `cli.main` catches it, logs
    `Stopped by an interrupt` and exits with 130, stdio included. Uncaught it
    printed a traceback after `Finished server process`. SIGTERM, which
    `docker stop` sends, is not affected: Python turns only SIGINT into an
    exception.
  - **One line per call**, written by the wrapper `register_tool` puts around
    every tool: `get_history SAP.DE 250 rows, truncated, 412 ms`, with
    `cached` appended when the result cache answered (the cache notes that in
    a context variable). `server_status` is registered without the wrapper
    and writes none: a status question is not an activity.
  - **What a line may carry.** A symbol or a key, since both are public
    identifiers, with printable characters only and cut at 32, because the
    caller chose them and the line is written before Yahoo says whether they
    exist. A line break would forge a second line, an escape sequence would
    reach a terminal. Never the bearer token, a search query (free text a person
    typed, the line gives the number of matches), a URL's query string,
    anything from Yahoo's answer, the text of an error this server raised,
    which is written for the model, or a prompt's argument, which for the
    dividend calendar holds a portfolio. A line names the error's class
    instead, and a prompt writes no line at all (§7a).
    A line another library wrote, which may quote what a caller sent, is
    reduced to printable characters on its way to stderr, so it cannot forge
    a second line either.
  - **Other loggers.** The chosen level applies to this package and to
    uvicorn's request log only. The root logger stays at WARNING, so every
    other library, including one nobody thought of, says only what went
    wrong. `mcp`, `sse_starlette`, `curl_cffi`, `urllib3`,
    `peewee`, `httpx2` and `httpcore2` (the SDK's HTTP client) are also
    pinned at WARNING by name:
    `mcp` quotes every failed call's text at INFO and `sse_starlette` logs
    every tool result in full at DEBUG. A test fails on a pinned name no
    installed module logs under. uvicorn's server log is held at INFO
    for its startup lines. uvicorn gets no
    handlers of its own. Its request log reaches the same stderr handler
    without the query string, at INFO only for a refused request (status 400
    and up, with the address that tried) and at DEBUG for all. `yfinance` is
    held at CRITICAL, which is silent: it logs an unknown symbol as up to four
    ERROR lines, one of them Yahoo's whole answer body, after the tool has
    already said "not found" in its own line. What yfinance raises still
    reaches the log through that line, and an unexpected exception through
    `wrap_upstream` with its traceback. `wrap_upstream` hands the model the
    text of yfinance's own exceptions only. A network error is named by
    class, since its text can carry the URL with Yahoo's crumb, and anything
    else by class as well.
  - **Python warnings** go to stderr as Python prints them, outside the
    line format.
- **CLI flags:** `--version`, `--transport`, `--host` (default 127.0.0.1), `--port`
  (default 8000, 1-65535, checked once an HTTP transport binds it), `--path`
  (default `/mcp`, `/sse` for sse), `--allowed-hosts`, `--allowed-origins`,
  `--log-level`, and the cache flags `--cache`/`--no-cache`, `--cache-dir`,
  `--cache-max-entries <N>`, `--cache-ttl <NAME>=<SECONDS>` (see §8a).
  Host/port/path/allow-list apply to the HTTP transports only. For stdio they
  are ignored.
- **Environment:** every CLI flag has an env-var equivalent (CLI > env >
  default): `YF_MCP_TRANSPORT`, `YF_MCP_HOST`, `YF_MCP_PORT`, `YF_MCP_PATH`,
  `YF_MCP_ALLOWED_HOSTS`, `YF_MCP_ALLOWED_ORIGINS`, `YF_MCP_LOG_LEVEL`, and the
  cache vars `YF_MCP_CACHE`, `YF_MCP_CACHE_DIR`, `YF_MCP_CACHE_MAX_ENTRIES`,
  `YF_MCP_CACHE_TTL_<NAME>`.
  `YF_MCP_BEARER_TOKEN` is the one exception with no flag: an argument is
  visible in the process list to every other user on the machine. All of them
  are read once, by `settings.load_settings`. A value that cannot be used
  falls back to its default with a warning in the log, a flag value that
  cannot be used is a usage error. The port is the exception: a value
  outside 1 to 65535, from the flag or the environment, stops an HTTP start
  as a usage error, since a server that silently moved to 8000 would listen
  on the wrong port.
- **Entry points:** `python -m benethos_yahoo_finance_mcp` or the
  `benethos-yahoo-finance-mcp` console script.
- **Python:** 3.11-3.15, all covered by the CI matrix, 3.11 from 3.11.5 on,
  the first patch soupsieve 4 runs on.
- **HTTP security:** an **optional** bearer token. With
  `YF_MCP_BEARER_TOKEN` set, every HTTP request must carry
  `Authorization: Bearer <token>` or gets HTTP 401. A single shared secret
  compared in constant time, not an OAuth flow: this server speaks for nobody
  and has no user to authorize. Off by default, since the ordinary case is a
  loopback bind on the machine that uses it. stdio ignores it. A token does not
  make a port safe to publish - bind to `0.0.0.0` only on trusted networks and
  front it with a proxy that authenticates. The guard sits in front of the
  whole ASGI app and lets only the lifespan scope through unchecked. A
  WebSocket handshake is closed with 1008 before it is accepted, and any
  other scope type gets no answer, so a route the SDK adds later is not
  open by default.
  The MCP HTTP transport also runs a DNS-rebinding `Host`/`Origin` guard. It is
  derived from the actual bind host and passed to the SDK's app builder
  (`streamable_http_app` / `sse_app`, via `transport.http_app`) as an
  explicit argument: a localhost bind keeps the protective localhost allow-list
  (decided by address, so `LOCALHOST`, `127.0.0.2` and `[::1]` count, and
  `YF_MCP_HOST` is trimmed first),
  an exposed bind accepts any `Host` unless `--allowed-hosts` /
  `--allowed-origins` narrow it (mismatches get HTTP 421). Either list is
  derived from the other when only one is given. stdio has no HTTP
  surface and is handed no transport options at all. The image sets
  `YF_MCP_ALLOWED_HOSTS` to the loopback names and the compose service name,
  and both compose files set it again, because the image binds `0.0.0.0` and
  the guard would otherwise be off while the port sits on the host's
  loopback, reachable by a rebound browser page. A proxy's name or any other
  address the container is reached by has to be added, or it gets 421.
  Production appends `YAHOO_FINANCE_MCP_DOMAIN` when it is set, the name
  clients use through Caddy (see Deployment), which would otherwise get 421.
  `tests/test_cli.py` holds it to that.
  The SSE app answers each request once. The SDK's SSE endpoint returns an
  empty response after its stream ends, and when the server stops with a
  stream still open, uvicorn refused that second answer with a traceback
  in the log, the client unaffected. `transport.single_response` wraps the
  `sse_app` inside the bearer guard and drops a second response start and
  anything sent after the closing body, every other scope passed through.
  Streamable HTTP answers once and is not wrapped. The wrapper can go once
  the SDK's endpoint stops answering twice (modelcontextprotocol/python-sdk
  issue 883).
- **Deployment:** everything for containers sits in `containers/`. The
  `Dockerfile` in `containers/images/yahoo-finance-mcp/` (multi-stage,
  non-root, healthcheck, dependencies installed reproducibly from `uv.lock`
  via uv, build context the repository root) hosts the server over
  streamable-HTTP on port 8000. The image is configured entirely via env vars
  (no default CMD args) and persists its cache to a `/cache` volume. Two
  compose files run it: `containers/production/` pulls the published image at
  the version `.env` names, required and without a default, and needs no
  clone, `containers/development/` builds from the checkout under a project
  name and host port of its own (8001), so both run side by side. Both fix
  the port inside the container at 8000 under `environment:`, where it wins
  over `.env`, since the port mapping and Caddy forward to that number and
  the health check reads the same variable. The port on the host is
  `YAHOO_FINANCE_MCP_PORT`. Secrets such
  as the bearer token go in an optional `.env` beside the compose file, read
  through `env_file` and ignored by git and the build context, with
  `containers/production/.env.example` as the tracked template. Only Compose
  (or `docker run --env-file`) reads it, the server itself loads no file.
  Both publish the port on **127.0.0.1 only**, drop every Linux capability
  and set `no-new-privileges`, since the server runs as a non-root user on a
  high port and needs none, run on a read-only root file system with a tmpfs
  for `/tmp` and for `yfinance`'s cookie and time zone cache in the home
  directory, and cap the log Docker keeps of the container at 5 files of
  10 MB, since uvicorn writes a line per request and Docker's default keeps
  everything. CI asserts the loopback port, the read-only root, that
  development builds and that production pulls the published image.
  Drop the loopback prefix only behind a reverse proxy that authenticates, or
  at the very least with `YF_MCP_BEARER_TOKEN` set.
  Production brings that proxy along under the compose profile `https`
  (`COMPOSE_PROFILES=https` in `.env`): Caddy, configured by the `Caddyfile`
  beside the compose file, on port 443 of every address, TCP and, for
  HTTP/3, UDP. Port 80 is not published and Caddy redirects nothing, so a
  client set up with `http://` fails at once instead of sending its token in
  the clear first. `YAHOO_FINANCE_MCP_HTTPS_PORT` moves the host side of
  both mappings when 443 is taken, and the domain stands in the allow-list
  alone and with any port, since Caddy hands on the client's `Host`. It
  forwards to the server by service name over the
  compose network, so the server's port stays on 127.0.0.1. The domain comes
  from `YAHOO_FINANCE_MCP_DOMAIN`, the certificate from one of three
  snippets picked by `YAHOO_FINANCE_MCP_TLS`: `internal` (default, Caddy's
  own CA, for a private network), `files` (`secrets/tls/cert.pem` and
  `key.pem`, ignored by git) or `acme` (a public CA, which needs the name in
  public DNS and port 443 reachable from the internet, whatever port Caddy
  has on the host). A request without an `Authorization` header
  gets 401 from Caddy and never reaches the server, which checks the token
  of every other. Set the token with the profile, since nothing in the stack
  enforces it: without one Caddy still starts, and a request with any
  `Authorization` header reaches a server that has no token to compare. The
  server trusts no forwarded header, so its log names Caddy's address for a
  refused request, not the client's. Compose cannot require the domain for
  one profile only, since `:?` fails every start without it, so Caddy's
  command checks it first and stops with a message naming it. Caddy runs
  read-only with a tmpfs for `/tmp`, every capability dropped except
  `NET_BIND_SERVICE`, `no-new-privileges` and the same log cap, and keeps
  certificates and the ACME account in the volumes `caddy-data` and
  `caddy-config`. It starts once the server reports healthy.
