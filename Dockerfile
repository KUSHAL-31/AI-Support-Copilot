FROM python:3.12-slim AS base

ENV PDM_CHECK_UPDATE=false \
    PDM_USE_VENV=false \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN pip install --no-cache-dir pdm==2.26.8

COPY pyproject.toml pdm.lock README.md ./
COPY src ./src
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

RUN pdm install --prod --no-editable

EXPOSE 8000

CMD ["pdm", "run", "copilot-api"]
