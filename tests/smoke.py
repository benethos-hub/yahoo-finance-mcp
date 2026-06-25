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
    show(
        "get_quotes(['AAPL','MSFT','SPY','NOTAREALSYMBOL'])",
        client.get_quotes(["AAPL", "MSFT", "SPY", "NOTAREALSYMBOL"]),
    )

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

    earnings = client.get_earnings("AAPL", limit=4)
    show(
        "get_earnings('AAPL', limit=4)",
        {
            "symbol": earnings["symbol"],
            "earnings_dates": earnings["earnings_dates"][:2],
            "earnings_history": earnings["earnings_history"][:2],
        },
    )

    show("get_estimates('AAPL')", client.get_estimates("AAPL"))

    ud = client.get_upgrades_downgrades("AAPL", max_rows=3)
    show("get_upgrades_downgrades('AAPL', max_rows=3)", ud)

    holders = client.get_holders("AAPL", max_rows=3)
    show(
        "get_holders('AAPL', max_rows=3)",
        {
            "symbol": holders["symbol"],
            "major_holders": holders["major_holders"],
            "institutional_holders": holders["institutional_holders"][:2],
            "mutualfund_holders": holders["mutualfund_holders"][:2],
        },
    )

    insider = client.get_insider_activity("AAPL", max_rows=3)
    show(
        "get_insider_activity('AAPL', max_rows=3)",
        {
            "symbol": insider["symbol"],
            "transactions": insider["transactions"][:2],
            "purchases_summary": insider["purchases_summary"],
            "roster": insider["roster"][:2],
        },
    )

    show("get_sec_filings('AAPL', limit=3)", client.get_sec_filings("AAPL", limit=3))
    show("get_calendar('AAPL')", client.get_calendar("AAPL"))

    show(
        "get_financials('AAPL', income/ttm)",
        client.get_financials("AAPL", statement="income", freq="ttm"),
    )

    shares = client.get_shares("AAPL", max_rows=3)
    show("get_shares('AAPL', max_rows=3)", shares)

    # Fund data is ETF/fund-only; use SPY.
    fund = client.get_fund_data("SPY", max_rows=3)
    show("get_fund_data('SPY', max_rows=3)", fund)

    sector = client.get_sector("technology", max_rows=3)
    show(
        "get_sector('technology', max_rows=3)",
        {
            "key": sector["key"],
            "name": sector["name"],
            "overview": sector["overview"],
            "top_companies": sector["top_companies"],
            "industries": sector["industries"][:3],
        },
    )

    industry = client.get_industry("semiconductors", max_rows=3)
    show(
        "get_industry('semiconductors', max_rows=3)",
        {
            "key": industry["key"],
            "name": industry["name"],
            "sector_key": industry["sector_key"],
            "top_companies": industry["top_companies"],
            "top_performing_companies": industry["top_performing_companies"],
        },
    )
