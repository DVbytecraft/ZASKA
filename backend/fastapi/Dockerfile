FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app:/app/backend/fastapi

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
