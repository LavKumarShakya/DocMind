FROM python:3.13-slim

# Production self-hosted backend image for DocMind.
#
# The embedding (BGE) and reranker models are in-process singletons loaded
# lazily on first use, so this image intentionally runs a single uvicorn
# worker (extra workers would duplicate model memory). Data paths are
# overridable via environment; Compose mounts persistent volumes on /data so
# uploaded PDFs, PostgreSQL-facing files and the Hugging Face model cache
# survive container recreation.

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Root directory for uploaded documents (persistent volume).
    STORAGE_DIR=/data/storage \
    # Hugging Face / sentence-transformers model cache (persistent volume).
    HF_HOME=/data/huggingface

WORKDIR /app

# Install CPU-only PyTorch wheels first so `pip install -r` never pulls the
# CUDA build (saves several GB and avoids GPU-specific wheels on host-only use).
COPY requirements.txt ./
RUN pip install --no-cache-dir "torch>=2.3,<3.0" \
    --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create the persistent data directories and a non-root runtime user.
# The /data volume (mounted by Compose) is chowned so the app can write.
RUN mkdir -p /data/storage /data/huggingface \
    && useradd --create-home --uid 10001 docmind \
    && chown -R docmind:docmind /app /data

USER docmind

EXPOSE 8000

# Apply migrations, then start the API with a single worker. Listens on
# 0.0.0.0; port defaults to 8000 and respects $PORT when supplied. One worker
# is intentional: the embedding/reranker models are process-local singletons.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
