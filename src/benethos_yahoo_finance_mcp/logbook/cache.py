"""The result cache: whether it is on, what a sweep drops, when its file lets it down.

The cache is an optimisation, so none of its failures fails a call. They are
WARNINGs because the operator is the only one who can do anything about a
locked or damaged file.
"""

from __future__ import annotations

import logging
from pathlib import Path

from . import _describe

_log = logging.getLogger(f"{_describe.PACKAGE}.cache")


def enabled(directory: Path) -> None:
    _log.info("Result cache enabled at %s", directory)


def disabled() -> None:
    _log.info("Result cache disabled")


def unusable(directory: Path, error: BaseException) -> None:
    _log.warning(
        "Result cache at %s unusable, running without it: %s",
        directory,
        _describe.fault(error),
    )


def file_rewritten() -> None:
    _log.info("Result cache file rewritten once so it can shrink after a sweep")


def capped(dropped: int, limit: int) -> None:
    _log.info(
        "Result cache over its limit of %d entries, dropped the %d oldest",
        limit,
        dropped,
    )


def not_serializable() -> None:
    _log.debug("Skipping cache for a value that is not JSON-serializable")


def read_failed(error: BaseException) -> None:
    _log.warning(
        "Result cache read failed, fetching directly: %s", _describe.fault(error)
    )


def write_failed(error: BaseException) -> None:
    _log.warning("Result cache write failed, not cached: %s", _describe.fault(error))
