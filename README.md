# Unofficial Yahoo Finance MCP Server

[![CI](https://github.com/benethos-hub/yahoo-finance-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/benethos-hub/yahoo-finance-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/benethos-yahoo-finance-mcp)](https://pypi.org/project/benethos-yahoo-finance-mcp/)
[![Container](https://img.shields.io/badge/ghcr.io-yahoo--finance--mcp-2496ED?logo=docker&logoColor=white)](https://github.com/benethos-hub/yahoo-finance-mcp/pkgs/container/yahoo-finance-mcp)
[![Python](https://img.shields.io/pypi/pyversions/benethos-yahoo-finance-mcp)](https://pypi.org/project/benethos-yahoo-finance-mcp/)
[![Coverage](https://img.shields.io/badge/coverage-94%25-brightgreen)](https://github.com/benethos-hub/yahoo-finance-mcp/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue)](https://github.com/benethos-hub/yahoo-finance-mcp/blob/main/LICENSE)

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
>   use. You use it at your own risk. See [LICENSE](https://github.com/benethos-hub/yahoo-finance-mcp/blob/main/LICENSE).
> - For **commercial use**, review Yahoo's Terms of Service and consider a
>   properly licensed market-data provider instead of the unofficial endpoints.

## Tools

| Tool | Description |
|------|-------------|
| `search` | Find instruments by name, ticker, or ISIN, returning Yahoo symbols. |
| `get_quote` | Current price and key intraday figures for a symbol. |
| `get_quotes` | Compact current quotes for several symbols at once (per-symbol not-found list). |
| `get_history` | Historical OHLCV data (period/interval or explicit date range). |
| `get_company_info` | Company profile and key statistics (sector, market cap, P/E, …). |
| `get_financials` | Income statement, balance sheet, or cash flow (annual/quarterly/ttm). |
| `get_dividends` | Dividend and stock-split history. |
| `get_news` | Recent news headlines (title, summary, publisher, URL). |
| `get_recommendations` | Analyst recommendation trend and price targets. |
| `get_options` | Option expiration dates and the calls/puts chain for a date. |
| `get_earnings` | Upcoming and historical earnings (EPS estimate/actual, surprise). |
| `get_estimates` | Forward analyst estimates (earnings, revenue, EPS trend/revisions, growth). |
| `get_upgrades_downgrades` | Recent analyst rating changes (upgrades/downgrades). |
| `get_holders` | Ownership breakdown (insider/institutional %, top institutional and mutual-fund holders). |
| `get_insider_activity` | Insider transactions, 6-month purchases/sales summary, and current roster. |
| `get_sec_filings` | Recent SEC filings (type, date, title, EDGAR/exhibit links). |
| `get_calendar` | Upcoming earnings and dividend / ex-dividend dates with estimate ranges. |
| `get_shares` | Shares-outstanding history (date → shares). |
| `get_fund_data` | Fund/ETF profile: overview, asset-class & sector weightings, top holdings. |
| `get_sector` | Browse a market sector by key: overview, top companies/ETFs/funds, industries. |
| `get_industry` | Browse an industry by key: overview, parent sector, top/top-performing/top-growth companies. |
| `get_market` | Trading status and headline index summary for a market (US, EUROPE, ASIA, …). |

Most `get_*` tools take a Yahoo Finance **symbol** — either a ticker (`AAPL`,
`SAP.DE`) or a plain ISIN. Use `search` to turn a company name into one. Three
tools are exceptions: `get_sector` and `get_industry` take a sector or industry
**key** (e.g. `technology`, `semiconductors`), and `get_market` takes a market
key (e.g. `US`).

<details>
<summary><b>📊 Sector &amp; industry keys</b> — click to expand (11 sectors, 145 industries, generated)</summary>

<!-- Generated from yfinance.const.SECTOR_INDUSTY_MAPPING_LC. Regenerate after a yfinance bump (see SPECS §12). Some industry keys use an em-dash, not a hyphen — copy them from get_sector output. -->

**`basic-materials`** (14)
`agricultural-inputs`, `aluminum`, `building-materials`, `chemicals`, `coking-coal`, `copper`, `gold`, `lumber-wood-production`, `other-industrial-metals-mining`, `other-precious-metals-mining`, `paper-paper-products`, `silver`, `specialty-chemicals`, `steel`

**`communication-services`** (7)
`advertising-agencies`, `broadcasting`, `electronic-gaming-multimedia`, `entertainment`, `internet-content-information`, `publishing`, `telecom-services`

**`consumer-cyclical`** (23)
`apparel-manufacturing`, `apparel-retail`, `auto-manufacturers`, `auto-parts`, `auto-truck-dealerships`, `department-stores`, `footwear-accessories`, `furnishings-fixtures-appliances`, `gambling`, `home-improvement-retail`, `internet-retail`, `leisure`, `lodging`, `luxury-goods`, `packaging-containers`, `personal-services`, `recreational-vehicles`, `residential-construction`, `resorts-casinos`, `restaurants`, `specialty-retail`, `textile-manufacturing`, `travel-services`

**`consumer-defensive`** (12)
`beverages—brewers`, `beverages—non-alcoholic`, `beverages—wineries-distilleries`, `confectioners`, `discount-stores`, `education-training-services`, `farm-products`, `food-distribution`, `grocery-stores`, `household-personal-products`, `packaged-foods`, `tobacco`

**`energy`** (8)
`oil-gas-drilling`, `oil-gas-e&p`, `oil-gas-equipment-services`, `oil-gas-integrated`, `oil-gas-midstream`, `oil-gas-refining-marketing`, `thermal-coal`, `uranium`

**`financial-services`** (15)
`asset-management`, `banks—diversified`, `banks—regional`, `capital-markets`, `credit-services`, `financial-conglomerates`, `financial-data-stock-exchanges`, `insurance-brokers`, `insurance—diversified`, `insurance—life`, `insurance—property-casualty`, `insurance—reinsurance`, `insurance—specialty`, `mortgage-finance`, `shell-companies`

**`healthcare`** (11)
`biotechnology`, `diagnostics-research`, `drug-manufacturers—general`, `drug-manufacturers—specialty-generic`, `health-information-services`, `healthcare-plans`, `medical-care-facilities`, `medical-devices`, `medical-distribution`, `medical-instruments-supplies`, `pharmaceutical-retailers`

**`industrials`** (25)
`aerospace-defense`, `airlines`, `airports-air-services`, `building-products-equipment`, `business-equipment-supplies`, `conglomerates`, `consulting-services`, `electrical-equipment-parts`, `engineering-construction`, `farm-heavy-construction-machinery`, `industrial-distribution`, `infrastructure-operations`, `integrated-freight-logistics`, `marine-shipping`, `metal-fabrication`, `pollution-treatment-controls`, `railroads`, `rental-leasing-services`, `security-protection-services`, `specialty-business-services`, `specialty-industrial-machinery`, `staffing-employment-services`, `tools-accessories`, `trucking`, `waste-management`

**`real-estate`** (12)
`real-estate-services`, `real-estate—development`, `real-estate—diversified`, `reit—diversified`, `reit—healthcare-facilities`, `reit—hotel-motel`, `reit—industrial`, `reit—mortgage`, `reit—office`, `reit—residential`, `reit—retail`, `reit—specialty`

**`technology`** (12)
`communication-equipment`, `computer-hardware`, `consumer-electronics`, `electronic-components`, `electronics-computer-distribution`, `information-technology-services`, `scientific-technical-instruments`, `semiconductor-equipment-materials`, `semiconductors`, `software—application`, `software—infrastructure`, `solar`

**`utilities`** (6)
`utilities—diversified`, `utilities—independent-power-producers`, `utilities—regulated-electric`, `utilities—regulated-gas`, `utilities—regulated-water`, `utilities—renewable`

</details>

## Compatible clients

MCP is an open protocol, so this server is not tied to one application. Every
MCP client can use it. What differs is only which transport the client speaks,
and that decides how you start the server.

**Locally, over stdio.** The client launches the server as a subprocess and
talks to it over stdin and stdout. This is the default transport and needs no
network. Claude Desktop, Claude Code, Cursor, VS Code (Copilot agent mode), Zed,
Windsurf, the JetBrains AI assistants, Cline, Roo Code, Continue and Goose all
work this way. The configuration file differs per client, but the command is
always the one shown under [Quick start](#quick-start-uv--claude-desktop):

```json
{ "command": "uvx", "args": ["benethos-yahoo-finance-mcp"] }
```

**Over the network, streamable-HTTP.** The server runs once and clients connect
to `http://<host>:8000/mcp`. Start it with `--transport streamable-http`, or use
the Docker image, which serves this transport by default. Browser-based and
multi-user front ends need it — Open WebUI supports MCP natively over
streamable-HTTP and over no other transport, because a shared web front end
cannot hold one stdio process per user. LibreChat and Windsurf accept it
alongside stdio.

**Over the network, SSE.** The older HTTP transport, still expected by some
clients. Start it with `--transport sse` and point the client at
`http://<host>:8000/sse`. The **MCP Client Tool** node in n8n connects this way.

> Both HTTP transports ship without authentication of their own. Read the note
> under [Running as a standalone server](#running-as-a-standalone-server) before
> exposing either one.

**Not listed?** Client support moves quickly. Check which transport yours
speaks, then use the matching command above — the transports are stable even
when the list of names is not.

## Requirements

- [uv](https://docs.astral.sh/uv/) (recommended) — manages Python, the virtual
  environment, and dependencies in one tool.
- Or, without uv: Python 3.11+ with `pip` / `venv`.
- `git` is **only** needed for the optional install-from-source method.

## Installation

### Quick start: uv + Claude Desktop

The simplest way to run the server — no clone, no manual virtual environment,
no `git`. `uvx` fetches and runs it on demand from
[PyPI](https://pypi.org/project/benethos-yahoo-finance-mcp/) (published as
`benethos-yahoo-finance-mcp`).

1. **Install uv**, if you have not already — the
   [uv installation page](https://docs.astral.sh/uv/getting-started/installation/)
   covers every platform. It brings `uvx`, and that is the only thing needed
   here.

2. **Add the server** to `claude_desktop_config.json` (Claude Desktop →
   Settings → Developer → Edit Config):

   ```json
   {
     "mcpServers": {
       "benethos-yahoo-finance-mcp": {
         "command": "uvx",
         "args": ["benethos-yahoo-finance-mcp"]
       }
     }
   }
   ```

   Pin a version for stability with `benethos-yahoo-finance-mcp==0.5.0`. To
   enable the optional result cache, add an `env` block, e.g.
   `"env": { "YF_MCP_CACHE": "1" }` (see [Caching](#caching)).

3. **Restart Claude Desktop** (quit from the tray, not just close the window).
   The tools then appear in the client.

> **Installing from source instead?** You can run the unreleased `main` branch
> with `uvx --from "git+https://github.com/benethos-hub/yahoo-finance-mcp.git" benethos-yahoo-finance-mcp`.
> That path needs `git` on the `PATH` of the process the client spawns — some
> GUI clients don't pass a full `PATH`, so prefer the PyPI install above.

> `uvx` must be on the `PATH` the client uses. After installing uv, fully restart
> the app — or use the absolute path to `uvx` as `command`. The first launch
> downloads the package and its dependencies, so it takes a moment. Later
> launches use the cache.

### Other ways to install

**From PyPI with pip** (no uv, no clone). Install the published package into a
virtual environment and run it as a module. The only platform difference is the
venv interpreter path: Windows uses `.venv\Scripts\python.exe`, Linux/macOS use
`.venv/bin/python`.

```powershell
# Windows (PowerShell)
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install benethos-yahoo-finance-mcp
```

```bash
# Linux / macOS (bash)
python3 -m venv .venv
.venv/bin/python -m pip install benethos-yahoo-finance-mcp
```

Point Claude Desktop at the absolute path of the venv interpreter and run the
module (no generated console script involved):

```json
{
  "mcpServers": {
    "benethos-yahoo-finance-mcp": {
      "command": "/abs/path/to/.venv/bin/python",
      "args": ["-m", "benethos_yahoo_finance_mcp"]
    }
  }
}
```

(On Windows use `C:\\abs\\path\\to\\.venv\\Scripts\\python.exe` as `command`.)

**From source with uv** (for development or local changes):

```bash
git clone https://github.com/benethos-hub/yahoo-finance-mcp.git
cd yahoo-finance-mcp
uv sync --extra dev          # creates .venv + installs deps from uv.lock
uv run benethos-yahoo-finance-mcp     # run over stdio
```

Point Claude Desktop at the checkout:

```json
{
  "mcpServers": {
    "benethos-yahoo-finance-mcp": {
      "command": "uv",
      "args": ["run", "--project", "/abs/path/to/yahoo-finance-mcp", "benethos-yahoo-finance-mcp"]
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
    "benethos-yahoo-finance-mcp": {
      "command": "/abs/path/to/.venv/bin/python",
      "args": ["-m", "benethos_yahoo_finance_mcp"]
    }
  }
}
```

(On Windows use `C:\\abs\\path\\to\\.venv\\Scripts\\python.exe` as `command`.)

## Running as a standalone server

For use outside Claude Desktop — a network-reachable HTTP service — run an HTTP
transport (`streamable-http` or `sse`). **Docker is the simplest way.**

Every option has both a CLI flag and an environment variable (handy for
containers), with one deliberate exception noted below. Precedence is
**CLI > environment > default** (`--help` lists the flags):

| Flag | Env var | Default | Description |
|------|---------|---------|-------------|
| `--version` | — | — | Print the version and exit. Same value the server reports in the MCP handshake. |
| `--transport` | `YF_MCP_TRANSPORT` | `stdio` | `stdio`, `streamable-http`, or `sse`. |
| `--host` | `YF_MCP_HOST` | `127.0.0.1` | Bind host for HTTP transports (`0.0.0.0` for remote). |
| `--port` | `YF_MCP_PORT` | `8000` | Port for HTTP transports. |
| `--path` | `YF_MCP_PATH` | `/mcp` (`/sse` for sse) | URL path for HTTP transports. |
| _(none)_ | `YF_MCP_BEARER_TOKEN` | unset | Require this bearer token on every HTTP request. Environment only, deliberately: an argument is visible in the process list. |
| `--allowed-hosts` | `YF_MCP_ALLOWED_HOSTS` | see below | Comma-separated `Host` header allow-list for the DNS-rebinding guard. |
| `--allowed-origins` | `YF_MCP_ALLOWED_ORIGINS` | derived from hosts | Comma-separated `Origin` header allow-list. |
| `--log-level` | `YF_MCP_LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`. |
| `--cache` / `--no-cache` | `YF_MCP_CACHE` | off | Enable/disable the persistent result cache. |
| `--cache-dir` | `YF_MCP_CACHE_DIR` | OS cache dir | Directory for the cache file. |
| `--cache-ttl <NAME>=<SECONDS>` | `YF_MCP_CACHE_TTL_<NAME>` | per-tool defaults | Override one tool's TTL. |

Logging always goes to stderr, so under stdio stdout stays reserved for the
JSON-RPC protocol.

> **Bearer token (optional).** Set `YF_MCP_BEARER_TOKEN` and every HTTP request
> must carry `Authorization: Bearer <token>`. Anything else gets **HTTP 401**.
> It is off by default, because the ordinary case is a server on the loopback
> address of the machine that uses it, where a token guards against nothing. It
> is a single shared secret compared in constant time, not an OAuth flow — the
> question is only whether the caller is expected. stdio ignores it: the client
> owns that process and nothing else can reach it.
>
> A token does not make a port safe to publish. The data here is public and
> read-only, so the realistic damage is somebody spending your Yahoo rate limit,
> not reading something private. Beyond a trusted network, put a reverse proxy
> with real authentication in front.

> **`Host` header / DNS-rebinding guard.** The MCP HTTP transport validates the
> `Host` header. A **localhost** bind keeps a protective allow-list
> (`localhost`/`127.0.0.1`). An **exposed** bind (`0.0.0.0`) accepts any `Host`
> by default, so containers and other hosts can reach it out of the box. To lock
> it down again, set `--allowed-hosts` (e.g. `benethos-yahoo-finance-mcp:8000`) — clients
> whose `Host` is not on the list then get **HTTP 421**.

### Docker

The published image is the shortest path to a running server — no Python, no
clone, no build. Every release is pushed to the GitHub Container Registry for
`linux/amd64` and `linux/arm64`:

```bash
docker run --rm -p 8000:8000 ghcr.io/benethos-hub/yahoo-finance-mcp:latest
# Server is now reachable at http://localhost:8000/mcp
```

Pin a version for anything you depend on — `:0.5.0` for an exact release, `:0.5`
to follow its patch releases. `:latest` moves with every release, and `:edge` is
built from `main` on demand and is not a release at all.

The image hosts the server over the streamable-HTTP transport. The stdio
transport is for local subprocess use and is not what you containerize.
Dependencies are installed reproducibly from `uv.lock` via uv.

The image is **configured entirely through environment variables** (see the
options table above) — it carries no default command arguments, so overriding a
single setting with `-e` does not disturb the others.

```bash
# Build it yourself instead of pulling (e.g. to run an unreleased main)
docker build -t benethos-yahoo-finance-mcp .

# Run with the built-in defaults (streamable-HTTP on 0.0.0.0:8000)
docker run --rm -p 8000:8000 benethos-yahoo-finance-mcp
# Server is now reachable at http://localhost:8000/mcp

# Override settings via -e, opt into the cache and persist it in a named volume
docker run --rm -p 9000:9000 \
    -e YF_MCP_PORT=9000 \
    -e YF_MCP_LOG_LEVEL=DEBUG \
    -e YF_MCP_CACHE=1 \
    -v benethos-yahoo-finance-mcp-cache:/cache \
    benethos-yahoo-finance-mcp
```

The image runs as a non-root user and includes a healthcheck on the configured
HTTP port. The cache is off by default. Enable it with `-e YF_MCP_CACHE=1`, in
which case it is written to `/cache` (declared as a volume) — mount a named
volume there to keep it across container restarts. Pass `-e YF_MCP_BEARER_TOKEN=...`
to require a bearer token on every request. Beyond a trusted network, front it
with a reverse proxy that authenticates.

### Docker Compose

A `compose.yaml` is provided (settings under `environment:`, cache in a named
volume). As shipped it **builds** from this checkout, which is what you want
while developing and the only way to run an unreleased `main`. To **operate**
the released server instead, swap two commented lines at the top of the service
so it pulls `ghcr.io/benethos-hub/yahoo-finance-mcp` — the file is then all you
need, with no clone and no Dockerfile. The choice and the `pull_policy` values
are documented in the file itself.

```bash
docker compose up -d      # build (if needed) and start in the background
docker compose logs -f    # follow logs
docker compose down       # stop and remove
```

This requires Docker Compose v2 (the `compose` CLI plugin). The server is then
reachable at `http://localhost:8000/mcp`.

The port is published on **`127.0.0.1` only**, so the service is reachable from
the host but not from the rest of the network. That is deliberate, since the
server has no authentication of its own. To expose it, remove the `127.0.0.1:`
prefix from the `ports:` entry in `compose.yaml` — and put a reverse proxy with
authentication in front of it.

### Manual (uv or venv)

With uv (any OS):

```bash
# Streamable HTTP on http://127.0.0.1:8000/mcp
uv run benethos-yahoo-finance-mcp --transport streamable-http

# Bind all interfaces on a custom port / path
uv run benethos-yahoo-finance-mcp \
    --transport streamable-http --host 0.0.0.0 --port 9000 --path /yf
```

With the venv interpreter directly (Windows: `.venv\Scripts\python.exe`):

```bash
.venv/bin/python -m benethos_yahoo_finance_mcp --transport streamable-http
```

## Example prompts

Once the server is connected, ask the client in plain language and it will pick
the tools. Replace the bracketed placeholders with concrete values.

**Price & quote**

- "What's the current price of [Ticker], and how far is it from its 52-week high?"
- "Is [Ticker] trading above or below its 50- and 200-day moving averages?"
- "Get the daily closes of [Ticker] for the last 6 months and compute RSI and MACD."
- "What was the deepest drawdown of [Ticker] in the last 12 months?"
- "Compare [Ticker A] and [Ticker B] over the last 3 months and show which held up better."
- "Get current quotes for [Ticker A], [Ticker B] and [Ticker C] and compare them in a table."

**Company & valuation**

- "Give me P/E, beta, market cap and dividend yield for [Ticker]."
- "What does [Company name] actually do, and which sector and industry is it in?"
- "Show the last three annual income statements for [Ticker] and how revenue developed."
- "How has [Ticker]'s share count changed over the past years, and does that mean buybacks or dilution?"

**Analysts & news**

- "What's the analyst consensus for [Ticker], and how far is the average price target from the current price?"
- "Any upgrades or downgrades for [Ticker] in the last few weeks?"
- "What are the forward revenue and EPS estimates for [Ticker], and how were they revised recently?"
- "Summarize the recent news on [Ticker]."

**Earnings & calendar**

- "When does [Ticker] report next, and what EPS is expected?"
- "How did [Ticker] do against estimates in the last few quarters?"
- "When are [Ticker]'s next earnings and ex-dividend dates?"

**Dividends**

- "Show [Ticker]'s dividends over the last ten years and the current yield."
- "Has [Ticker] cut its dividend in the last 20 years, and did it split the stock?"

**Ownership & insiders**

- "Who are the largest institutional holders of [Ticker]?"
- "What share of [Ticker] is held by insiders versus institutions?"
- "Has there been notable insider buying or selling in [Ticker] recently?"

**Funds & ETFs**

- "What are the top holdings and sector weightings of the ETF [Ticker]?"
- "What's the asset-class split of [ETF Ticker], and which fund family runs it?"

**Filings**

- "Show the most recent SEC filings for [US Ticker] with links."

**Options**

- "Which option expiration dates are available for [US Ticker]?"
- "Show the calls and puts for [US Ticker] expiring [Date]."

**Sectors & markets**

- "What are the top companies and industries in the technology sector?"
- "Show the top-performing companies in the semiconductors industry."
- "Is the US market open right now, and when does it open next?"
- "How did the major indices in Europe and Asia close?"

**Finding a symbol**

- "Which Yahoo ticker belongs to [Company name] on [Exchange]?"
- "Resolve the ISIN [ISIN] to a Yahoo ticker."

**A daily round-up**

- "For [Ticker A], [Ticker B] and [Ticker C]: pull quote, six months of history,
  company info and analyst recommendations, then give me a short picture of each."

> **The server computes nothing itself.** It passes through what Yahoo returns,
> which already includes derived figures such as moving averages, P/E, beta and
> dividend yield. Anything Yahoo does not carry — RSI, MACD, drawdown,
> sentiment, total return — the model works out from the raw series.

## Symbol resolution

All `get_*` tools expect a Yahoo Finance **symbol**. Both a ticker (`AAPL`,
`SAP.DE`) and a plain ISIN (`US0378331005`) work, since Yahoo resolves ISINs
server-side. The server passes whatever it is given straight through and never
rewrites it.

To turn a **company name** into a symbol, call `search` first — the same Yahoo
search endpoint handles free text, tickers, and ISINs. A ticker is preferable to
an ISIN in any case, because the `symbol` reported back then stays consistent
across tools.

Two caveats. That ISINs work is **observed behaviour of an unofficial endpoint**,
not a guarantee: it did not work in earlier versions and it may stop again.
And German **WKNs resolve nowhere**, not through the tools and not through
`search` — Yahoo has no lookup for them, so ask for a ticker, an ISIN or the
company name instead.

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
| `quotes` | `get_quotes` | 30 s |
| `history` | `get_history` | 10 min |
| `news` | `get_news` | 10 min |
| `options` | `get_options` | 10 min |
| `search` | `search` | 1 h |
| `company_info` | `get_company_info` | 6 h |
| `dividends` | `get_dividends` | 6 h |
| `recommendations` | `get_recommendations` | 6 h |
| `earnings` | `get_earnings` | 6 h |
| `estimates` | `get_estimates` | 6 h |
| `upgrades_downgrades` | `get_upgrades_downgrades` | 6 h |
| `insider_activity` | `get_insider_activity` | 6 h |
| `sec_filings` | `get_sec_filings` | 6 h |
| `calendar` | `get_calendar` | 6 h |
| `financials` | `get_financials` | 24 h |
| `holders` | `get_holders` | 24 h |
| `shares` | `get_shares` | 24 h |
| `fund_data` | `get_fund_data` | 24 h |
| `sector` | `get_sector` | 24 h |
| `industry` | `get_industry` | 24 h |
| `market` | `get_market` | 60 s |

- Off by default. Enable with `--cache` or `YF_MCP_CACHE=1`.
- Location: the OS user cache directory, or `--cache-dir` / `YF_MCP_CACHE_DIR`.
- Override a TTL: `--cache-ttl quote=15` (repeatable) or the
  `YF_MCP_CACHE_TTL_<NAME>` env var (e.g. `YF_MCP_CACHE_TTL_QUOTE=15`).
  Set a TTL to `0` to bypass caching for that tool.

Precedence is CLI > environment > default. Errors are never cached.

### When to enable it

Enable the cache (`--cache` / `YF_MCP_CACHE=1`) if you:

- run the server as a long-running or **containerized HTTP service** that
  restarts periodically (the cache survives restarts → instant repeat results).
- **hit Yahoo rate limits** or make many repeated identical requests over time.
- mostly query **slow-changing data** (search, company info, financials), where
  staleness is irrelevant.

Leave it off (the default) if you:

- run it **locally over stdio** for interactive sessions — yfinance already
  reuses identical requests within a single process, so the cache adds little.
- need the **freshest possible** data.
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
uv run pytest --cov=benethos_yahoo_finance_mcp   # coverage
```

With the venv interpreter directly (replace `.venv/bin/python` with
`.venv\Scripts\python.exe` on Windows):

```bash
.venv/bin/python -m pip install -e ".[dev]"

.venv/bin/python -m pytest -q                 # unit tests (offline)
.venv/bin/python -m ruff check .              # lint
.venv/bin/python -m ruff format .             # format
.venv/bin/python -m mypy                      # type check
.venv/bin/python -m pytest --cov=benethos_yahoo_finance_mcp   # coverage
```

The unit tests mock `yfinance` and run fully offline. `tests/smoke.py` performs
an ad-hoc check against live Yahoo Finance and is not part of the unit suite.
CI also runs across Python 3.11–3.14 and enforces an 80% coverage floor.

## Trademarks

"Yahoo" and "Yahoo Finance" are trademarks of Yahoo Inc. This project is not
affiliated with, endorsed by, or sponsored by Yahoo, and it is not an official
Yahoo product.

The names are used here only to describe what the software does, namely read
market data from Yahoo Finance through the `yfinance` library. That is the only
accurate way to say it. All trademarks remain the property of their respective
owners.

The project itself is published as `benethos-yahoo-finance-mcp` and is
maintained independently under the [MIT licence](https://github.com/benethos-hub/yahoo-finance-mcp/blob/main/LICENSE).
