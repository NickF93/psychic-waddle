FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml PLAN.md LICENSE ./
COPY src ./src
COPY migrations ./migrations

RUN python -m pip install --upgrade pip && python -m pip install .

USER app

EXPOSE 8000

CMD ["uvicorn", "portfolio_rag_assistant.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
