"""Runtime configuration, overridable via environment variables (12-factor style).

    CMC_NUMERIC_TOLERANCE   absolute tolerance for claim-vs-source value match (default 0.01)
    CMC_AUDIT_PATH          audit ledger path (default audit_log.jsonl)
    CMC_LOG_LEVEL           DEBUG|INFO|WARNING|ERROR (default INFO)
    CMC_LOG_JSON            "1" to emit one JSON object per log line
    AUDIT_HMAC_KEY          see audit.py (read there, never logged)
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, Field


class Settings(BaseModel):
    numeric_tolerance: float = Field(default=0.01, ge=0.0)
    audit_path: str = "audit_log.jsonl"
    log_level: str = "INFO"
    log_json: bool = False

    @classmethod
    def from_env(cls, env=None) -> "Settings":
        env = os.environ if env is None else env
        kwargs = {}
        if "CMC_NUMERIC_TOLERANCE" in env:
            kwargs["numeric_tolerance"] = float(env["CMC_NUMERIC_TOLERANCE"])
        if "CMC_AUDIT_PATH" in env:
            kwargs["audit_path"] = env["CMC_AUDIT_PATH"]
        if "CMC_LOG_LEVEL" in env:
            kwargs["log_level"] = env["CMC_LOG_LEVEL"].upper()
        if "CMC_LOG_JSON" in env:
            kwargs["log_json"] = env["CMC_LOG_JSON"] == "1"
        return cls(**kwargs)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
