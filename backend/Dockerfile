FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

# Install dependencies as a separate layer so rebuilds are fast when only app code changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Pre-download the cross-encoder re-ranker (~85 MB) at build time so the first
# request doesn't hit a cold download delay in production
RUN uv run python -c \
    "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

COPY app/ ./app/

EXPOSE 8000

# Railway injects $PORT at runtime; fall back to 8000 for local docker run
CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
