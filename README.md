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

```powershell
.\.venv\Scripts\python.exe -m yahoo_finance_mcp.server
```

The server speaks MCP over stdio. All logging goes to stderr so stdout stays
reserved for the JSON-RPC protocol.

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
