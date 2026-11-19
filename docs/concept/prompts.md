# Concept: prompts

Part of the [concept](../CONCEPT.md): section 7a.

## 7a. Prompts

Six prompts in `prompts/` are recipes a person picks in the client, Claude
Desktop under "+", Connectors, Add from and the server's name, Claude Code as
a slash command. Each returns one user message that names the tools to call,
in which order, and the traps of the data to mind. A prompt asks Yahoo
nothing and writes no log line, the tool calls it leads to write theirs. The
four data recipes end with the same rules: currencies are never converted,
London prices are in pence, the data may be delayed, a missing figure is
named, and no buy, sell or hold recommendation is given. Judging an
instrument is left to the person, in line with the read-only scope of §2.

`dividend_calendar` is the one recipe that calculates. It converts every
amount to one currency and forecasts the coming months by fixed rules: the
pay date from the gap `get_calendar` reports or else 14 days and marked
estimated, the payments of the last 365 days recurring without growth,
gross amounts, and every gap listed. It is the only prompt that takes
personal data, the share count of each position. **The share counts reach
this server** as part of the `positions` argument, and with the HTTP
transports that means the machine that hosts it. The server puts them into
the text and nowhere else: no tool receives them, Yahoo never sees them, and
no log line carries them (a test renders the prompt with a count and looks
for it in every log record). The text tells the model to pass them to no
tool. `positions` takes any form a model can read, `SAP.DE:50`, `50x
IE00B4L5Y983` or rows pasted from a bank export with columns of their own,
decimal commas included. Whatever else such rows carry, an account number
for one, reaches the server the same way, so the text tells the model to
ignore every column but the instrument and the count, and the README asks
the person to leave the account number out.

| Prompt | Arguments | Tools it chains |
|--------|-----------|-----------------|
| `asset_analysis` | `symbol` | `get_quote`, then by `quoteType` for a stock `get_company_info`, `get_recommendations`, `get_calendar`, `get_shares`, `get_financials` (annual income), `get_news` and `get_history` 1y in one block, for a fund `get_fund_data` and `get_history`, for crypto `get_history` only. Own calculations: distance to every target, share count implied by the market cap against the diluted average shares of the last annual report, a multi-year table, price to sales for a loss |
| `compare` | `symbols` (comma-separated), `period` (empty: 1y) | `get_quotes`, `get_history` and `get_company_info` for each |
| `earnings_preview` | `symbol` | `get_calendar`, `get_earnings`, `get_estimates` (one `methodology` for both), `get_upgrades_downgrades` |
| `etf_profile` | `symbol` | `get_fund_data`, `get_quote`, `get_history` 5y monthly when a return is missing |
| `dividend_calendar` | `positions` (any form, symbol and share count each), `year` (empty: the current one), `currency` (empty: EUR) | `get_dividends` each, `get_calendar` for single stocks, `get_quote` for each listing's currency and each exchange rate |
| `find_symbol` | `query`, `exchange` (empty: the home exchange) | `search` with limit 25, a WKN named as unresolvable |

Each recipe resolves a company name through `search` first. Every argument is
a string, as MCP prompt arguments are. `tests/test_prompts.py` checks every
tool and field a recipe names against what the server registers and returns,
and the bundle manifest lists the prompts with their text (see
`tests/test_mcpb.py`).

**Every prompt is a plain template.** Each argument goes into the text as it
came, an optional one defaults to `""`, and the text says in words what an
empty one means (`Period:  (one year, 1y, when empty)`). No condition picks
another sentence and no default stands in for an empty value, so the
manifest's text with the arguments put in, an empty one as `""`, is exactly
what the server sends. `tests/test_prompts.py` renders every prompt with its
optional arguments left out, empty and filled in, and compares each with its
template.

**Both bundles set `prompts_generated` and `tools_generated`,** because of
how Claude Desktop treats the manifest's prompts. Measured on 2026-11-11 with
Claude Desktop 5.1231.2 on Windows from its logs, first on another MCP server
with three bundles that differed only in the manifest, then on this server's
pinned bundle:

- The "+" menu lists every prompt the server offers, declared or not.
- Without `prompts_generated`, a prompt the manifest does not declare is
  refused when it is attached ("Failed to attach prompt").
- A declared prompt is checked against its text in the manifest, with the
  arguments put in, and a text that differs is refused "to prevent potential
  prompt injection". An optional argument left empty in Desktop's form is
  not sent, and its placeholder stays in the text Desktop expects. On this
  bundle `dividend_calendar` with `year` and `currency` empty was refused:
  expected 3382 characters, got 3344, the 38 of `${arguments.year}` and
  `${arguments.currency}`. No text a server sends can match that, so every
  prompt with an optional argument fails the check whenever one stays empty.
- With `prompts_generated: true` nothing is checked, declared or not. Desktop
  logs "skipping prompt verification" when the extension starts, and on
  this bundle the same `dividend_calendar` with `year` and `currency` empty
  was attached.

The pinned bundle therefore lists its prompts, for display, and sets the
flag. Its code ships in the same file as its manifest, and no prompt carries
data from Yahoo, so the check would guard little here. It sets
`tools_generated` too, which changes nothing measured for a bundle whose
tools ship with its code, so that both bundles carry the same flags.
Running the server from a checkout carries no manifest and shows none of
this.

`asset_analysis` takes from a careful analysis what checks and calculates
and leaves out what judges: an outlook by horizon and a case for or
against. Its share count check compares the count behind the market cap
with the diluted average shares of the last annual report, since every other
count the tools return is the same one (§12). A year of buybacks or issues
moves the two a few percent apart, so it speaks up past ten percent only.

A prompt is started by the person. The model cannot call one and does not
see the list, so nothing a recipe says reaches a conversation in which it
was not picked. That is why the rules that must always hold stay in the tool
descriptions and parameters (§7), and a recipe only adds an order and a
check on top. The texts are English, the answer follows the language the
person adds to the message.
