"""Structured logging with a per-run correlation id.

Library code logs through `logging.getLogger(__name__)` and never prints. The CLI
(or any host app) calls `configure_logging(run_id=...)` once. Every record then
carries the run_id, matching the `run_id` written to the audit ledger, so a log
line can be tied back to the exact audited run.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar

_run_id: ContextVar[str] = ContextVar("cmc_run_id", default="-")


class _RunIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = _run_id.get()
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "run_id": getattr(record, "run_id", "-"),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(run_id: str | None = None, level: str = "INFO", json_logs: bool = False,
                      stream=None) -> None:
    if run_id:
        _run_id.set(run_id)
    root = logging.getLogger("cmc_verifier")
    root.setLevel(level.upper())
    root.handlers.clear()
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.addFilter(_RunIdFilter())
    handler.setFormatter(_JsonFormatter() if json_logs else logging.Formatter(
        "%(asctime)s %(levelname)-7s [%(run_id)s] %(message)s"))
    root.addHandler(handler)
    root.propagate = False
