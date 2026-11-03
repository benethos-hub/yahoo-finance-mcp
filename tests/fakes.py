"""Stand-ins for yfinance objects, shared by the tests."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd


class FakeTicker:
    """Stand-in for ``yf.Ticker`` exposing only what the yahoo functions touch."""

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
        if "news_error" in self._attrs:
            raise self._attrs["news_error"]
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

    # The EPS tables take a methodology since yfinance 1.8.0. Each request
    # is kept, (table, methodology), and the table is the attribute of the
    # same name, as the properties before them.
    def _eps_table(self, name, methodology):
        self.__dict__.setdefault("eps_requests", []).append((name, methodology))
        return self._attrs.get(name)

    def get_earnings_estimate(self, methodology=None):
        return self._eps_table("earnings_estimate", methodology)

    def get_eps_trend(self, methodology=None):
        return self._eps_table("eps_trend", methodology)

    def get_eps_revisions(self, methodology=None):
        return self._eps_table("eps_revisions", methodology)

    def get_earnings_history(self, methodology=None):
        return self._eps_table("earnings_history", methodology)

    def get_revenue_estimate(self):
        return self._attrs.get("revenue_estimate")

    def get_growth_estimates(self):
        return self._attrs.get("growth_estimates")

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


class FakeSearch:
    """Stand-in for the ``yf.Search`` class: called like it, answers with
    ``news`` and no quotes, and keeps the arguments of every call."""

    def __init__(self, news=()):
        self.news = list(news)
        self.calls = []

    def __call__(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return SimpleNamespace(news=self.news, quotes=[])
