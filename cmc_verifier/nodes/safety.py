"""Failure isolation for parallel check nodes.

A check that raises would abort the whole `app.invoke` and lose every other
check's findings. `isolate` converts an exception into a MAJOR flag so the human
reviewer sees "this check did not run" rather than a crash or, worse, silence.
"""

from __future__ import annotations

import logging

import functools
from typing import Callable

from ..models import Flag, Severity

log = logging.getLogger(__name__)


def isolate(name: str, fn: Callable) -> Callable:
    @functools.wraps(fn)
    def wrapper(state):
        try:
            return fn(state)
        except Exception as exc:  # noqa: BLE001 - deliberate catch-all boundary
            log.error("check %s FAILED: %s: %s", name, type(exc).__name__, exc)
            return {"flags": [Flag(
                check_name=name,
                severity=Severity.MAJOR,
                message=f"Check '{name}' crashed and did not complete: {type(exc).__name__}: {exc}",
                confidence=1.0,
                rationale="Internal error; results for this check are missing and must not be assumed clean.",
            )]}
    return wrapper
