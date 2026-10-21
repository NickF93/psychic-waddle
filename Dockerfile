FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app \
    && install -d -m 0755 /opt/tokenizers

COPY pyproject.toml requirements.lock PLAN.md LICENSE ./
COPY src ./src
COPY migrations ./migrations
COPY config ./config

# Tokenizer only, pinned to the fallback's immutable upstream artifact.
ADD --chmod=0444 --checksum=sha256:c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539 https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/resolve/aa8e72537993ba99e69dfaafa59ed015b17504d1/tokenizer.json /opt/tokenizers/qwen-tokenizer.json

ARG RELEASE_VERSION=0.3.0
ARG SOURCE_REVISION=unknown
LABEL org.opencontainers.image.version=$RELEASE_VERSION \
      org.opencontainers.image.revision=$SOURCE_REVISION \
      org.opencontainers.image.source="https://github.com/NickF93/psychic-waddle"

RUN python -m pip install --constraint requirements.lock .

USER app

# Exercise installed resources as the actual runtime user before shipping.
RUN python -c "from portfolio_rag_assistant.provider.parameters import ParameterProfile; ParameterProfile.load('openai'); open('/opt/tokenizers/qwen-tokenizer.json', 'rb').read(1)"

EXPOSE 8000

CMD ["uvicorn", "portfolio_rag_assistant.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
