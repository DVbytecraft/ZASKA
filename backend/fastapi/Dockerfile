FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app:/app/backend/fastapi

# postgresql-client provides pg_dump for the automated backup task
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY backend/fastapi/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/fastapi /app/backend/fastapi
COPY backend/fastapi/alembic.ini /app/alembic.ini

COPY backend/fastapi/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

EXPOSE 6969

CMD ["/app/docker-entrypoint.sh"]
