FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first for layer caching.
COPY pyproject.toml requirements.txt ./
RUN pip install -r requirements.txt
# Optional LLM claim extraction: docker build --build-arg WITH_LLM=1 ...
ARG WITH_LLM=0
RUN if [ "$WITH_LLM" = "1" ]; then pip install "anthropic>=2.8"; fi

COPY cmc_verifier ./cmc_verifier
COPY data ./data
COPY run.py README.md ./
# Editable install so the bundled sample data path (relative to the package) resolves.
RUN pip install --no-deps -e .

# Run as an unprivileged user; /work is where callers mount their own data and outputs.
RUN useradd --create-home --uid 10001 cmc && mkdir /work && chown cmc /work
USER cmc
WORKDIR /work
ENV CMC_AUDIT_PATH=/work/audit_log.jsonl

ENTRYPOINT ["cmc-verify"]
CMD []
