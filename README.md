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

- [uv](https://docs.astral.sh/uv/) (recommended) — manages Python, the virtual
  environment, and dependencies in one tool.
- `git` — required for the `uvx` git-URL install below.
- Or, without uv: Python 3.11+ with `pip` / `venv`.

## Installation

### Quick start: uv + Claude Desktop

The simplest way to use the server with Claude Desktop — no clone, no manual
virtual environment. `uvx` fetches, builds, and runs it on demand straight from
GitHub.

1. **Install uv** (see the [uv install docs](https://docs.astral.sh/uv/getting-started/installation/)):

   ```bash
   # macOS / Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   ```powershell
   # Windows (PowerShell)
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **Add the server** to `claude_desktop_config.json` (Claude Desktop →
   Settings → Developer → Edit Config):

   ```json
   {
     "mcpServers": {
       "yahoo-finance": {
         "command": "uvx",
         "args": [
           "--from",
           "git+https://github.com/benethos-hub/yahoo-finance-mcp.git@v0.1.1",
           "yahoo-finance-mcp"
         ]
       }
     }
   }
   ```

   Pin a release tag (`@v0.1.1`) for stability, or use `@main` for the latest.
   To enable the optional result cache, add an `env` block, e.g.
   `"env": { "YF_MCP_CACHE": "1" }` (see [Caching](#caching)).

3. **Restart Claude Desktop** (quit from the tray, not just close the window).
   The tools then appear in the client.

> `uvx` must be on `PATH` for Claude Desktop. After installing uv, fully restart
> the app — or use the absolute path to `uvx` as `command`. `git` must be
> installed for the git-URL install. The first launch builds from source (clone
> + dependencies), so it takes a moment; subsequent launches use the cache.

### Other ways to install

**From source with uv** (for development or local changes):

```bash
git clone https://github.com/benethos-hub/yahoo-finance-mcp.git
cd yahoo-finance-mcp
uv sync --extra dev          # creates .venv + installs deps from uv.lock
uv run yahoo-finance-mcp     # run over stdio
```

Point Claude Desktop at the checkout:

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "uv",
      "args": ["run", "--project", "/abs/path/to/yahoo-finance-mcp", "yahoo-finance-mcp"]
    }
  }
}
```

**From source with venv + pip** (no uv). The only platform difference is the
venv interpreter path: Windows uses `.venv\Scripts\python.exe`, Linux/macOS use
`.venv/bin/python`.

```powershell
# Windows (PowerShell)
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

```bash
# Linux / macOS (bash)
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Claude Desktop config uses the absolute path to the venv interpreter:

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "/abs/path/to/.venv/bin/python",
      "args": ["-m", "yahoo_finance_mcp"]
    }
  }
}
```

(On Windows use `C:\\abs\\path\\to\\.venv\\Scripts\\python.exe` as `command`.)

## Running as a standalone server

For use outside Claude Desktop — a network-reachable HTTP service — run an HTTP
transport (`streamable-http` or `sse`). **Docker is the simplest way.**

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

### Docker

A `Dockerfile` builds a small image (dependencies installed reproducibly from
`uv.lock` via uv) that hosts the server over the streamable-HTTP transport (the
stdio transport is for local subprocess use and is not what you containerize).

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
volume there to keep it across container restarts. As with any HTTP deployment,
there is no built-in authentication — front it with a reverse proxy / auth layer
before exposing it publicly.

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

### Manual (uv or venv)

With uv (any OS):

```bash
# Streamable HTTP on http://127.0.0.1:8000/mcp
uv run yahoo-finance-mcp --transport streamable-http

# Bind all interfaces on a custom port / path
uv run yahoo-finance-mcp \
    --transport streamable-http --host 0.0.0.0 --port 9000 --path /yf
```

With the venv interpreter directly (Windows: `.venv\Scripts\python.exe`):

```bash
.venv/bin/python -m yahoo_finance_mcp --transport streamable-http
```

## Example prompts

Once the server is connected, you can ask the client natural-language
questions and it will pick the right tools. Replace the bracketed placeholders
(e.g. `[Ticker]`, `[ISIN]`) with concrete values.

**Price & quote** (`get_quote`, `get_history`)

- "What's the current price of [Ticker] and how has it moved over the last 24h?"
- "Get the daily closing prices of [Ticker] for the last 6 months and compute
  RSI, MACD, and the 50/200-day moving averages."
- "What was the max drawdown of [Ticker] since inception, and how long was it
  underwater?"
- "Compare the performance of [Ticker A] against [Index] over 1, 3, and 6
  months (relative strength)."
- "How far is [Ticker] currently from its 52-week high?"

**Company data & valuation** (`get_company_info`, `get_financials`)

- "Give me P/E, beta, market cap, and dividend yield for [Ticker]."
- "Are the fundamentals (ROE, leverage, margins) for [Ticker] available via
  Yahoo? If not, flag the metric as unavailable."
- "How liquid is [Ticker]? Average daily volume and market cap."

**Analysts & sentiment** (`get_recommendations`, `get_news`)

- "What's the current analyst consensus for [Ticker], and any up-/downgrades
  from the last few weeks?"
- "How far is the average price target for [Ticker] above/below the current
  price?"
- "Any recent news on [Ticker], and is the sentiment positive or negative?"

**Dividends** (`get_dividends`)

- "List the distribution history of [Ticker] and compute the total-return
  recovery including reinvested dividends from [year]."
- "From which year does Yahoo cover dividends for [Ticker]?"

**Search / resolution** (`search`)

- "Resolve the ISIN [ISIN] to a Yahoo ticker."
- "Which Yahoo ticker belongs to [security name] on [exchange]?"

**Combined daily update** (multiple tools)

- "For the asset list [Ticker, Ticker, …]: for each name, pull the price history
  (6 months), quote, company info, and analyst recommendations, then summarize
  the current technical and sentiment picture per asset."

> The server only returns raw market data; any derived metrics (RSI, MACD,
> drawdown, sentiment, total return) are computed by the client/model from that
> data, not by the tools themselves.

## Symbol resolution

All `get_*` tools expect a Yahoo Finance **symbol** (e.g. `AAPL`, `SAP.DE`).
To resolve a company name or an ISIN to a symbol, call `search` first — the
same Yahoo search endpoint handles free text, tickers, and ISINs.

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

### When to enable it

Enable the cache (`--cache` / `YF_MCP_CACHE=1`) if you:

- run the server as a long-running or **containerized HTTP service** that
  restarts periodically (the cache survives restarts → instant repeat results);
- **hit Yahoo rate limits** or make many repeated identical requests over time;
- mostly query **slow-changing data** (search, company info, financials), where
  staleness is irrelevant.

Leave it off (the default) if you:

- run it **locally over stdio** for interactive sessions — yfinance already
  reuses identical requests within a single process, so the cache adds little;
- need the **freshest possible** data;
- use it only occasionally.

## Development

Install the dev extras, then run the test, lint, and type-check steps (the same
ones CI runs).

With uv (any OS):

```bash
uv sync --extra dev

uv run pytest -q                 # unit tests (offline)
uv run ruff check .              # lint
uv run ruff format .             # format
uv run mypy                      # type check
uv run pytest --cov=yahoo_finance_mcp   # coverage
```

With the venv interpreter directly (replace `.venv/bin/python` with
`.venv\Scripts\python.exe` on Windows):

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
