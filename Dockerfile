FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-wqy-zenhei \
        fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-deps .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn sales_agent.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
