FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir "torch>=2.3,<3.0" \
    --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Apply migrations, then start the API. Port defaults to 8000 (docker-compose /
# local dev) and falls back to Render's $PORT when set, so no Start Command
# override is required on Render. Uses one worker on purpose: the embedding and
# reranker models are in-process singletons, and extra workers would duplicate
# their memory.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]