# syntax=docker/dockerfile:1.7

# ---------- builder ----------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=600 \
    PIP_RETRIES=10

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Single venv that the runtime stage can copy verbatim. Avoids the
# wheel-cache pattern, which trips on packages that the two install passes
# resolve to different versions.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 1) CPU-only torch from PyTorch's wheel index. The CUDA bundle on PyPI is
#    ~500 MB and the only thing we use torch for is sentence-transformers
#    on CPU.
RUN pip install --upgrade pip wheel setuptools \
    && pip install --index-url https://download.pytorch.org/whl/cpu \
       'torch>=2.2,<2.6'

# 2) Remaining deps from PyPI. Torch is already satisfied so pip skips it.
RUN pip install \
       fastapi 'uvicorn[standard]' pydantic pydantic-settings httpx python-multipart \
       'psycopg[binary,pool]' pgvector \
       rank-bm25 sentence-transformers 'numpy<2.2.0' scipy scikit-learn \
       pypdf pdfplumber \
       anthropic openai tiktoken \
       structlog tenacity orjson

# ---------- runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the prebuilt venv. Keeps build tooling out of the runtime image.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY app ./app
COPY scripts ./scripts
COPY eval ./eval

RUN useradd --create-home --shell /bin/bash regrag \
    && chown -R regrag:regrag /app
USER regrag

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
