FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home --uid 10001 catalog && mkdir /var/lib/catalog && chown catalog:catalog /var/lib/catalog
COPY . .
USER catalog
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app CATALOG_DB_PATH=/var/lib/catalog/catalog.sqlite3
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "logging.json"]