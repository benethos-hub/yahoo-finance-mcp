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
