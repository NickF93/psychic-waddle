FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml requirements.lock PLAN.md LICENSE ./
COPY src ./src
COPY migrations ./migrations
COPY config ./config

RUN python -m pip install --constraint requirements.lock .

USER app

EXPOSE 8000

CMD ["uvicorn", "portfolio_rag_assistant.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
