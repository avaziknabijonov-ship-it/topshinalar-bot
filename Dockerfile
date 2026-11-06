# syntax=docker/dockerfile:1
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core poppler-utils tesseract-ocr tesseract-ocr-rus tesseract-ocr-uzb && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir -r requirements.txt; else pip install --no-cache-dir -r requirements.txt; fi
COPY *.py ./
COPY assets/ ./assets/
COPY web/ ./web/
COPY locales/ ./locales/
RUN chmod -R a+rX /app && useradd --create-home botuser && mkdir -m 700 /app/data && chown botuser:botuser /app/data
USER botuser
ENV DB_PATH=/app/data/topshinalar.sqlite3
CMD ["python", "bot.py"]
