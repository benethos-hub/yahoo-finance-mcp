"""Ad-hoc smoke test hitting live Yahoo Finance. Not part of the unit suite."""

import json

from yahoo_finance_mcp import client


def show(title, value):
    print(f"\n=== {title} ===")
    print(json.dumps(value, indent=2, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    show("search('Apple')", client.search("Apple", limit=3))
    show("search('US0378331005')  # AAPL ISIN", client.search("US0378331005", limit=3))
    show("get_quote('AAPL')", client.get_quote("AAPL"))

    hist = client.get_history("AAPL", period="5d", interval="1d")
    hist_preview = {**hist, "rows": hist["rows"][:2]}
    show("get_history('AAPL', 5d/1d) [first 2 rows]", hist_preview)

    show("get_company_info('AAPL')", client.get_company_info("AAPL"))
    show(
        "get_financials('AAPL', income/annual)",
        client.get_financials("AAPL", statement="income", freq="annual"),
    )

    divs = client.get_dividends("AAPL")
    divs_preview = {
        "symbol": divs["symbol"],
        "dividends": divs["dividends"][-3:],
        "splits": divs["splits"][-3:],
    }
    show("get_dividends('AAPL') [last 3]", divs_preview)

    show("get_news('AAPL', limit=3)", client.get_news("AAPL", limit=3))
    show("get_recommendations('AAPL')", client.get_recommendations("AAPL"))

    opts = client.get_options("AAPL")
    show("get_options('AAPL') [expirations]", opts)
    if opts.get("expirations"):
        first = opts["expirations"][0]
        chain = client.get_options("AAPL", expiration=first)
        chain_preview = {
            "symbol": chain["symbol"],
            "expiration": chain["expiration"],
            "calls": chain["calls"][:2],
            "puts": chain["puts"][:2],
        }
        show(f"get_options('AAPL', {first}) [first 2 each]", chain_preview)
