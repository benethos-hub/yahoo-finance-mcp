# Yahoo Finance MCP Server

An [MCP](https://modelcontextprotocol.io) server that exposes Yahoo Finance
data to MCP clients (such as Claude Desktop) over the stdio transport. Market
data is sourced through the [`yfinance`](https://github.com/ranaroussi/yfinance)
library, which uses Yahoo's unofficial endpoints.

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

```powershell
# Create and populate the virtual environment
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

## Running

The transport is chosen on the command line. **stdio** is the default (used by
Claude Desktop and other local clients):

```powershell
.\.venv\Scripts\python.exe -m yahoo_finance_mcp.server
```

To run it as a standalone, network-reachable service, use an HTTP transport:

```powershell
# Streamable HTTP on http://127.0.0.1:8000/mcp
.\.venv\Scripts\python.exe -m yahoo_finance_mcp.server --transport streamable-http

# Bind all interfaces on a custom port / path
.\.venv\Scripts\python.exe -m yahoo_finance_mcp.server `
    --transport streamable-http --host 0.0.0.0 --port 9000 --path /yf
```

Options (`--help` for the full list):

| Flag | Default | Description |
|------|---------|-------------|
| `--transport` | `stdio` | `stdio`, `streamable-http`, or `sse`. |
| `--host` | `127.0.0.1` | Bind host for HTTP transports (`0.0.0.0` for remote). |
| `--port` | `8000` | Port for HTTP transports. |
| `--path` | `/mcp` (`/sse` for sse) | URL path for HTTP transports. |
| `--log-level` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`. |

Logging always goes to stderr, so under stdio stdout stays reserved for the
JSON-RPC protocol.

> **Note:** The HTTP transports expose the server over the network without
> built-in authentication. Only bind to `0.0.0.0` on trusted networks, and put
> a reverse proxy / auth layer in front for any real deployment.

## Docker

A `Dockerfile` builds a small image that hosts the server over the
streamable-HTTP transport (the stdio transport is for local subprocess use and
is not what you containerize).

```bash
# Build
docker build -t yahoo-finance-mcp .

# Run: container port 8000 -> host port 8000
docker run --rm -p 8000:8000 yahoo-finance-mcp
# Server is now reachable at http://localhost:8000/mcp

# Override transport options by appending args (they replace the default CMD):
docker run --rm -p 9000:9000 yahoo-finance-mcp \
    --transport streamable-http --host 0.0.0.0 --port 9000 --path /yf
```

The image runs as a non-root user and includes a basic healthcheck on the HTTP
port. As with any HTTP deployment, there is no built-in authentication — front
it with a reverse proxy / auth layer before exposing it publicly.

## Claude Desktop configuration

Add the server to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "d:\\projects\\xt-yahoo-finance-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "yahoo_finance_mcp.server"]
    }
  }
}
```

## Symbol resolution

All `get_*` tools expect a Yahoo Finance **symbol** (e.g. `AAPL`, `SAP.DE`).
To resolve a company name or an ISIN to a symbol, call `search` first — the
same Yahoo search endpoint handles free text, tickers, and ISINs.

## Testing

Unit tests mock `yfinance` and run offline:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

`tests/smoke.py` performs an ad-hoc check against live Yahoo Finance and is
not part of the unit suite.
