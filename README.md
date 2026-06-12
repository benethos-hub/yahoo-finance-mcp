# Yahoo Finance MCP Server

An [MCP](https://modelcontextprotocol.io) server that exposes Yahoo Finance
data to MCP clients (such as Claude Desktop). It runs over **stdio** (default,
for local clients) or an **HTTP** transport (for standalone / containerized
hosting). Market data is sourced through the
[`yfinance`](https://github.com/ranaroussi/yfinance) library, which uses
Yahoo's unofficial endpoints.

> **Disclaimer**
>
> - This project is **not affiliated with, endorsed by, or sponsored by Yahoo**.
>   "Yahoo" and "Yahoo Finance" are trademarks of their respective owners.
> - It relies on **unofficial** Yahoo Finance endpoints via `yfinance`. Those
>   endpoints can change or break at any time, and Yahoo may rate limit or block
>   requests. Review Yahoo's Terms of Service before use.
> - Data may be delayed, incomplete, or inaccurate. **Nothing here is financial
>   advice.** Do not rely on it for trading or investment decisions.
> - Provided "as is", without warranty. Intended for personal and educational
>   use. You use it at your own risk. See [LICENSE](LICENSE).
> - For **commercial use**, review Yahoo's Terms of Service and consider a
>   properly licensed market-data provider instead of the unofficial endpoints.

## Tools

| Tool | Description |
|------|-------------|
| `search` | Find instruments by name, ticker, or ISIN; returns Yahoo symbols. |
| `get_quote` | Current price and key intraday figures for a symbol. |
| `get_history` | Historical OHLCV data (period/interval or explicit date range). |
| `get_company_info` | Company profile and key statistics (sector, market cap, P/E, …). |
| `get_financials` | Income statement, balance sheet, or cash flow (annual/quarterly). |
| `get_dividends` | Dividend and stock-split history. |
| `get_news` | Recent news headlines (title, summary, publisher, URL). |
| `get_recommendations` | Analyst recommendation trend and price targets. |
| `get_options` | Option expiration dates and the calls/puts chain for a date. |

All `get_*` tools take a Yahoo Finance **symbol**. Use `search` to resolve a
name or ISIN into a symbol first.

## Requirements

- Python 3.11+
- A virtual environment (all work is done inside `.venv`)

## Setup

The only platform difference is the venv interpreter path: Windows uses
`.venv\Scripts\python.exe`, Linux/macOS use `.venv/bin/python`.

Windows (PowerShell):

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

Linux / macOS (bash):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

## Running

The transport is chosen on the command line. **stdio** is the default (used by
Claude Desktop and other local clients):

Windows (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m yahoo_finance_mcp
```

Linux / macOS (bash):

```bash
.venv/bin/python -m yahoo_finance_mcp
```

To run it as a standalone, network-reachable service, use an HTTP transport
(same flags on every OS, only the interpreter path differs):

```bash
# Streamable HTTP on http://127.0.0.1:8000/mcp
.venv/bin/python -m yahoo_finance_mcp --transport streamable-http

# Bind all interfaces on a custom port / path
.venv/bin/python -m yahoo_finance_mcp \
    --transport streamable-http --host 0.0.0.0 --port 9000 --path /yf
```

Every option has both a CLI flag and an environment variable (handy for
containers). Precedence is **CLI > environment > default** (`--help` for the
full list):

| Flag | Env var | Default | Description |
|------|---------|---------|-------------|
| `--transport` | `YF_MCP_TRANSPORT` | `stdio` | `stdio`, `streamable-http`, or `sse`. |
| `--host` | `YF_MCP_HOST` | `127.0.0.1` | Bind host for HTTP transports (`0.0.0.0` for remote). |
| `--port` | `YF_MCP_PORT` | `8000` | Port for HTTP transports. |
| `--path` | `YF_MCP_PATH` | `/mcp` (`/sse` for sse) | URL path for HTTP transports. |
| `--log-level` | `YF_MCP_LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`. |
| `--cache` / `--no-cache` | `YF_MCP_CACHE` | off | Enable/disable the persistent result cache. |
| `--cache-dir` | `YF_MCP_CACHE_DIR` | OS cache dir | Directory for the cache file. |
| `--cache-ttl <NAME>=<SECONDS>` | `YF_MCP_CACHE_TTL_<NAME>` | per-tool defaults | Override one tool's TTL. |

Logging always goes to stderr, so under stdio stdout stays reserved for the
JSON-RPC protocol.

> **Note:** The HTTP transports expose the server over the network without
> built-in authentication. Only bind to `0.0.0.0` on trusted networks, and put
> a reverse proxy / auth layer in front for any real deployment.

## Caching

An **opt-in** persistent cache. When enabled, successful tool results are
cached in a small SQLite file with a per-tool time-to-live (TTL) to reduce load
on Yahoo's endpoints and survive restarts. Fast-moving data has a short TTL,
stable data a long one.

Within a single running process yfinance already reuses identical requests, so
the cache mainly helps **across restarts** and as **rate-limit protection** —
that is why it is off by default.

Cache names (used for `--cache-ttl <NAME>=<SECONDS>` and
`YF_MCP_CACHE_TTL_<NAME>`) and their default TTLs:

| Name | Tool | Default TTL |
|------|------|-------------|
| `quote` | `get_quote` | 30 s |
| `history` | `get_history` | 10 min |
| `news` | `get_news` | 10 min |
| `options` | `get_options` | 10 min |
| `search` | `search` | 1 h |
| `company_info` | `get_company_info` | 6 h |
| `dividends` | `get_dividends` | 6 h |
| `recommendations` | `get_recommendations` | 6 h |
| `financials` | `get_financials` | 24 h |

- Off by default; enable with `--cache` or `YF_MCP_CACHE=1`.
- Location: the OS user cache directory, or `--cache-dir` / `YF_MCP_CACHE_DIR`.
- Override a TTL: `--cache-ttl quote=15` (repeatable) or the
  `YF_MCP_CACHE_TTL_<NAME>` env var (e.g. `YF_MCP_CACHE_TTL_QUOTE=15`).
  Set a TTL to `0` to bypass caching for that tool.

Precedence is CLI > environment > default. Errors are never cached.

## Docker

A `Dockerfile` builds a small image that hosts the server over the
streamable-HTTP transport (the stdio transport is for local subprocess use and
is not what you containerize).

The image is **configured entirely through environment variables** (see the
options table above) — it carries no default command arguments, so overriding a
single setting with `-e` does not disturb the others.

```bash
# Build
docker build -t yahoo-finance-mcp .

# Run with the built-in defaults (streamable-HTTP on 0.0.0.0:8000)
docker run --rm -p 8000:8000 yahoo-finance-mcp
# Server is now reachable at http://localhost:8000/mcp

# Override settings via -e; opt into the cache and persist it in a named volume
docker run --rm -p 9000:9000 \
    -e YF_MCP_PORT=9000 \
    -e YF_MCP_LOG_LEVEL=DEBUG \
    -e YF_MCP_CACHE=1 \
    -v yahoo-finance-cache:/cache \
    yahoo-finance-mcp
```

The image runs as a non-root user and includes a healthcheck on the configured
HTTP port. The cache is off by default; enable it with `-e YF_MCP_CACHE=1`, in
which case it is written to `/cache` (declared as a volume) — mount a named
volume there to keep it across container restarts. As with any
HTTP deployment, there is no built-in authentication — front it with a reverse
proxy / auth layer before exposing it publicly.

### Docker Compose

A `compose.yaml` is provided (settings under `environment:`, cache in a named
volume):

```bash
docker compose up -d      # build (if needed) and start in the background
docker compose logs -f    # follow logs
docker compose down       # stop and remove
```

This requires Docker Compose v2 (the `compose` CLI plugin). The server is then
reachable at `http://localhost:8000/mcp`.

## Claude Desktop configuration

Add the server to your `claude_desktop_config.json`, using the absolute path to
the venv interpreter.

Windows:

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "C:\\path\\to\\xt-yahoo-finance-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "yahoo_finance_mcp"]
    }
  }
}
```

Linux / macOS:

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "/path/to/xt-yahoo-finance-mcp/.venv/bin/python",
      "args": ["-m", "yahoo_finance_mcp"]
    }
  }
}
```

## Symbol resolution

All `get_*` tools expect a Yahoo Finance **symbol** (e.g. `AAPL`, `SAP.DE`).
To resolve a company name or an ISIN to a symbol, call `search` first — the
same Yahoo search endpoint handles free text, tickers, and ISINs.

## Development

Install the dev extras, then run the test, lint, and type-check steps (the same
ones CI runs). Replace `.venv/bin/python` with `.venv\Scripts\python.exe` on
Windows:

```bash
.venv/bin/python -m pip install -e ".[dev]"

.venv/bin/python -m pytest -q                 # unit tests (offline)
.venv/bin/python -m ruff check .              # lint
.venv/bin/python -m ruff format .             # format
.venv/bin/python -m mypy                      # type check
.venv/bin/python -m pytest --cov=yahoo_finance_mcp   # coverage
```

The unit tests mock `yfinance` and run fully offline. `tests/smoke.py` performs
an ad-hoc check against live Yahoo Finance and is not part of the unit suite.
CI also runs across Python 3.11–3.13 and enforces an 80% coverage floor.
