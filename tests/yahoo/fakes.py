"""Stand-ins for yfinance objects, shared by the tests in this directory."""

from __future__ import annotations

import pandas as pd


class FakeTicker:
    """Stand-in for ``yf.Ticker`` exposing only what the client touches."""

    def __init__(self, **attrs):
        self._attrs = attrs

    def __getattr__(self, name):
        # Fallback for statement attrs (income_stmt, balance_sheet, ...) that
        # the client reads via getattr; defined properties take precedence.
        attrs = self.__dict__.get("_attrs", {})
        if name in attrs:
            return attrs[name]
        raise AttributeError(name)

    @property
    def fast_info(self):
        return self._attrs.get("fast_info", {})

    def history(self, **kwargs):
        self.history_kwargs = kwargs
        return self._attrs.get("history", pd.DataFrame())

    @property
    def info(self):
        return self._attrs.get("info", {})

    @property
    def dividends(self):
        return self._attrs.get("dividends")

    @property
    def splits(self):
        return self._attrs.get("splits")

    def get_news(self, **kwargs):
        self.news_kwargs = kwargs
        return self._attrs.get("news", [])

    @property
    def recommendations(self):
        return self._attrs.get("recommendations")

    @property
    def analyst_price_targets(self):
        return self._attrs.get("analyst_price_targets")

    @property
    def options(self):
        return self._attrs.get("options", ())

    def option_chain(self, expiration):
        self.requested_expiration = expiration
        return self._attrs.get("option_chain")

    def get_earnings_dates(self, **kwargs):
        self.earnings_dates_kwargs = kwargs
        return self._attrs.get("earnings_dates")

    def get_shares_full(self, **kwargs):
        self.shares_full_kwargs = kwargs
        return self._attrs.get("shares_full")

    @property
    def funds_data(self):
        fd = self._attrs.get("funds_data")
        if isinstance(fd, Exception):
            raise fd
        return fd
