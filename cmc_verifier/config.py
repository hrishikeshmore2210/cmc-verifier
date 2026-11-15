"""Runtime configuration, overridable via environment variables (12-factor style).

    CMC_NUMERIC_TOLERANCE   absolute tolerance for claim-vs-source value match (default 0.01)
    CMC_AUDIT_PATH          audit ledger path (default audit_log.jsonl)
    CMC_LOG_LEVEL           DEBUG|INFO|WARNING|ERROR (default INFO)
    CMC_LOG_JSON            "1" to emit one JSON object per log line
    CMC_LLM_MODEL           model for narrative claim extraction (default claude-opus-5-5)
    CMC_LLM_EFFORT          low|medium|high|xhigh|max (default high)
    CMC_LLM_CACHE_DIR       response cache dir (default .cmc_cache/llm; "" disables)
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
    llm_model: str = "claude-opus-5-5"
    llm_effort: str = "high"
    llm_cache_dir: str | None = ".cmc_cache/llm"

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
        if "CMC_LLM_MODEL" in env:
            kwargs["llm_model"] = env["CMC_LLM_MODEL"]
        if "CMC_LLM_EFFORT" in env:
            kwargs["llm_effort"] = env["CMC_LLM_EFFORT"]
        if "CMC_LLM_CACHE_DIR" in env:
            kwargs["llm_cache_dir"] = env["CMC_LLM_CACHE_DIR"] or None
        return cls(**kwargs)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
