"""What Yahoo, or the yfinance library in front of it, did to us."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from . import _describe

_log = logging.getLogger(f"{_describe.PACKAGE}.yahoo")


def rate_limited(tool: str, arguments: Mapping[str, Any]) -> None:
    """Yahoo refused a call for going too fast, e.g. ``get_news for AAPL``.

    The model is told to wait and retry. Without this line the operator, the
    one who could spread the load or move the server, would never know.
    """
    subject = _describe.subject(arguments)
    _log.warning("Yahoo rate limited %s", f"{tool} for {subject}" if subject else tool)


def sector_keys_unavailable() -> None:
    _log.warning(
        "yfinance.const sector mapping unavailable; "
        "falling back to a static sector list."
    )
