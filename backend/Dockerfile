FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
# Install CPU-only torch first so the default index does not pull CUDA wheels
# (hundreds of MB of NVIDIA runtime bloat in a dev container).
RUN pip install --no-cache-dir "torch>=2.3,<3.0" --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
