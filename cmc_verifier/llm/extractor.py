"""LLM claim extraction (ARCHITECTURE.md §2.3).

Turns a dossier narrative into list[Claim]. Design:

  * Structured output via `client.messages.parse(output_format=...)` (schema-valid JSON).
  * Model is untrusted: every claim passes `validate_claims` (verbatim-quote provenance
    gate). Rejections are returned, and the node turns them into flags.
  * Reproducibility: current Claude models reject sampling parameters (no temperature=0),
    so determinism comes from an on-disk response cache keyed on
    (model, effort, prompt version, document text). Re-running the same dossier replays the
    exact model output, and the cache hit is recorded in the audit trail.
  * Never truncates: a document over `max_chars` is an error, not silently cut.
  * The client is injectable, so everything is testable offline.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from ..models import Claim
from .prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_content
from .schema import ExtractedClaim, ExtractionResult
from .validate import find_injection_phrases, validate_claims

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "high"
MAX_CHARS = 200_000


class ExtractionError(Exception):
    """Extraction could not produce a trustworthy result (API failure, refusal, truncation)."""


@dataclass
class ExtractionOutcome:
    claims: list[Claim]
    rejected: list[tuple[ExtractedClaim, str]] = field(default_factory=list)
    injection_phrases: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


class LLMClaimExtractor:
    def __init__(self, client=None, model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT,
                 cache_dir: str | Path | None = None, max_chars: int = MAX_CHARS, max_tokens: int = 16000):
        self._client = client
        self.model = model
        self.effort = effort
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.max_chars = max_chars
        self.max_tokens = max_tokens

    # -- client ---------------------------------------------------------------
    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise ExtractionError(
                    "LLM extraction needs the 'anthropic' package: pip install 'cmc-verifier[llm]'") from exc
            if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
                log.warning("ANTHROPIC_API_KEY is not set; relying on other SDK credential sources")
            self._client = anthropic.Anthropic(max_retries=4, timeout=300.0)
        return self._client

    # -- cache ----------------------------------------------------------------
    def _cache_key(self, text: str) -> str:
        blob = json.dumps({"m": self.model, "e": self.effort, "p": PROMPT_VERSION, "t": text}, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _cache_read(self, key: str) -> ExtractionResult | None:
        if not self.cache_dir:
            return None
        path = self.cache_dir / f"{key}.json"
        try:
            return ExtractionResult.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None            # missing or corrupt -> treat as a miss

    def _cache_write(self, key: str, result: ExtractionResult) -> None:
        if not self.cache_dir:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_dir / f"{key}.json.tmp"
        tmp.write_text(result.model_dump_json(), encoding="utf-8")
        os.replace(tmp, self.cache_dir / f"{key}.json")     # atomic: no half-written cache entries

    # -- extraction -----------------------------------------------------------
    def _call_model(self, text: str) -> tuple[ExtractionResult, dict]:
        import anthropic
        client = self._get_client()
        try:
            response = client.messages.parse(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_user_content(text)}],
                output_format=ExtractionResult,
                output_config={"effort": self.effort},
            )
        except anthropic.RateLimitError as exc:
            raise ExtractionError(f"rate limited after retries: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise ExtractionError(f"network error reaching the API: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise ExtractionError(f"API error {exc.status_code}: {exc.message}") from exc

        # Never read content before checking why the model stopped.
        if response.stop_reason == "refusal":
            category = getattr(getattr(response, "stop_details", None), "category", None)
            raise ExtractionError(f"model declined the request (category: {category})")
        if response.stop_reason == "max_tokens":
            raise ExtractionError("output hit max_tokens; extraction would be incomplete")
        if response.parsed_output is None:
            raise ExtractionError("model returned no parseable structured output")

        usage = getattr(response, "usage", None)
        meta = {
            "request_id": getattr(response, "_request_id", None),
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
        }
        return response.parsed_output, meta

    def extract(self, text: str) -> ExtractionOutcome:
        if not text.strip():
            raise ExtractionError("document is empty")
        if len(text) > self.max_chars:
            raise ExtractionError(
                f"document is {len(text)} chars (limit {self.max_chars}); split it rather than truncating")

        key = self._cache_key(text)
        result = self._cache_read(key)
        cache_hit = result is not None
        call_meta: dict = {}
        if result is None:
            result, call_meta = self._call_model(text)
            self._cache_write(key, result)

        accepted, rejected = validate_claims(result.claims, text)
        log.info("extracted %d claim(s), rejected %d (cache_hit=%s)", len(accepted), len(rejected), cache_hit)
        return ExtractionOutcome(
            claims=accepted,
            rejected=rejected,
            injection_phrases=find_injection_phrases(text),
            meta={
                "method": "llm",
                "model": self.model,
                "effort": self.effort,
                "prompt_version": PROMPT_VERSION,
                "cache_hit": cache_hit,
                "cache_key": key,
                "document_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "claims_proposed": len(result.claims),
                "claims_rejected": len(rejected),
                **call_meta,
            },
        )
