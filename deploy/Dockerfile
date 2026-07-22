# Content Engine image. Build context is the repo ROOT (see docker-compose.yml).
FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal; psycopg[binary] ships its own libpq.
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY deploy/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# The engine modules + runner (all live at the repo root). Copy ALL root-level
# Python files so a newly added module is never accidentally left out of the
# image (this previously caused a 500 when content_engine_dashboard.py, the
# connectors and the reply agent were missing).
COPY *.py ./

EXPOSE 8000

# Default = the API. The worker service overrides CMD (see compose).
CMD ["uvicorn", "content_engine_api:app", "--host", "0.0.0.0", "--port", "8000"]
