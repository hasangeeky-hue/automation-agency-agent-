# Content Engine image. Build context is the repo ROOT (see docker-compose.yml).
FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal; psycopg[binary] ships its own libpq.
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY deploy/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# The engine modules + runner (all live at the repo root).
COPY content_engine_prompts.py \
     content_engine_schemas.py \
     content_engine_providers.py \
     content_engine_learning.py \
     content_engine_prep.py \
     content_engine_code_skills.py \
     content_engine_orchestrator.py \
     content_engine_store_pg.py \
     content_engine_health.py \
     content_engine_api.py \
     main.py \
     ./

EXPOSE 8000

# Default = the API. The worker service overrides CMD (see compose).
CMD ["uvicorn", "content_engine_api:app", "--host", "0.0.0.0", "--port", "8000"]
