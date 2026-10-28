FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY excel_import.py staff.py catalog.py core.py i18n.py bot.py usability.py miniapp.py quotation.py reports.py payments.py storage.py backup.py ./
COPY assets/ ./assets/
COPY web/ ./web/
RUN useradd --create-home botuser && mkdir /app/data && chown botuser:botuser /app/data
USER botuser
ENV DB_PATH=/app/data/topshinalar.sqlite3
CMD ["python", "bot.py"]
