"""Ad-hoc smoke test hitting live Yahoo Finance. Not part of the unit suite."""

import json

from benethos_yahoo_finance_mcp import yahoo


def show(title, value):
    print(f"\n=== {title} ===")
    print(json.dumps(value, indent=2, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    show("search('Apple')", yahoo.search("Apple", limit=3))
    show("search('US0378331005')  # AAPL ISIN", yahoo.search("US0378331005", limit=3))
    show("get_quote('AAPL')", yahoo.get_quote("AAPL"))
    show(
        "get_quotes(['AAPL','MSFT','SPY','NOTAREALSYMBOL'])",
        yahoo.get_quotes(["AAPL", "MSFT", "SPY", "NOTAREALSYMBOL"]),
    )

    hist = yahoo.get_history("AAPL", period="5d", interval="1d")
    hist_preview = {**hist, "rows": hist["rows"][:2]}
    show("get_history('AAPL', 5d/1d) [first 2 rows]", hist_preview)

    show("get_company_info('AAPL')", yahoo.get_company_info("AAPL"))
    show(
        "get_financials('AAPL', income/annual)",
        yahoo.get_financials("AAPL", statement="income", freq="annual"),
    )

    divs = yahoo.get_dividends("AAPL")
    divs_preview = {
        "symbol": divs["symbol"],
        "dividends": divs["dividends"][-3:],
        "splits": divs["splits"][-3:],
    }
    show("get_dividends('AAPL') [last 3]", divs_preview)

    show("get_news('AAPL', limit=3)", yahoo.get_news("AAPL", limit=3))
    show("get_recommendations('AAPL')", yahoo.get_recommendations("AAPL"))

    opts = yahoo.get_options("AAPL")
    show("get_options('AAPL') [expirations]", opts)
    if opts.get("expirations"):
        first = opts["expirations"][0]
        chain = yahoo.get_options("AAPL", expiration=first)
        chain_preview = {
            "symbol": chain["symbol"],
            "expiration": chain["expiration"],
            "calls": chain["calls"][:2],
            "puts": chain["puts"][:2],
        }
        show(f"get_options('AAPL', {first}) [first 2 each]", chain_preview)

    earnings = yahoo.get_earnings("AAPL", limit=4)
    show(
        "get_earnings('AAPL', limit=4)",
        {
            "symbol": earnings["symbol"],
            "earnings_dates": earnings["earnings_dates"][:2],
            "earnings_history": earnings["earnings_history"][:2],
        },
    )

    show("get_estimates('AAPL')", yahoo.get_estimates("AAPL"))

    ud = yahoo.get_upgrades_downgrades("AAPL", limit=3)
    show("get_upgrades_downgrades('AAPL', limit=3)", ud)

    holders = yahoo.get_holders("AAPL", limit=3)
    show(
        "get_holders('AAPL', limit=3)",
        {
            "symbol": holders["symbol"],
            "major_holders": holders["major_holders"],
            "institutional_holders": holders["institutional_holders"][:2],
            "mutualfund_holders": holders["mutualfund_holders"][:2],
        },
    )

    insider = yahoo.get_insider_activity("AAPL", limit=3)
    show(
        "get_insider_activity('AAPL', limit=3)",
        {
            "symbol": insider["symbol"],
            "transactions": insider["transactions"][:2],
            "purchases_summary": insider["purchases_summary"],
            "roster": insider["roster"][:2],
        },
    )

    show("get_sec_filings('AAPL', limit=3)", yahoo.get_sec_filings("AAPL", limit=3))
    show("get_calendar('AAPL')", yahoo.get_calendar("AAPL"))

    show(
        "get_financials('AAPL', income/ttm)",
        yahoo.get_financials("AAPL", statement="income", freq="ttm"),
    )

    shares = yahoo.get_shares("AAPL", limit=3)
    show("get_shares('AAPL', limit=3)", shares)

    # Fund data is ETF/fund-only; use SPY.
    fund = yahoo.get_fund_data("SPY", limit=3)
    show("get_fund_data('SPY', limit=3)", fund)

    sector = yahoo.get_sector("technology", limit=3)
    show(
        "get_sector('technology', limit=3)",
        {
            "key": sector["key"],
            "name": sector["name"],
            "overview": sector["overview"],
            "top_companies": sector["top_companies"],
            "industries": sector["industries"][:3],
        },
    )

    industry = yahoo.get_industry("semiconductors", limit=3)
    show(
        "get_industry('semiconductors', limit=3)",
        {
            "key": industry["key"],
            "name": industry["name"],
            "sector_key": industry["sector_key"],
            "top_companies": industry["top_companies"],
            "top_performing_companies": industry["top_performing_companies"],
        },
    )

    for market_key in ("US", "EUROPE"):
        market = yahoo.get_market(market_key)
        show(
            f"get_market({market_key!r})",
            {
                "key": market["key"],
                "status": market["status"],
                "count": market["count"],
                "indices": market["indices"][:3],
            },
        )

    # Two filters, a category and a range, the shape most screens take.
    screened = yahoo.screen(
        (("region", "eq", "us"), ("dividend_yield", "btwn", (3, 4))), limit=3
    )
    show("screen(region us, dividend_yield 3-4, limit=3)", screened)

    # get_sector's industry key, which the screener spells with an em dash.
    screened = yahoo.screen(
        (("industry", "eq", "software-infrastructure"), ("pe_ratio", "lt", 40)),
        sort_by="pe_ratio",
        sort_desc=False,
        limit=3,
    )
    show("screen(industry software-infrastructure, pe_ratio < 40, limit=3)", screened)
