# Backend image. Build context: the repository root (it needs config.yaml and content/ too).
#   docker build -f backend/Dockerfile -t tutor-api .
#   docker build -f backend/Dockerfile --build-arg SPACY_MODEL=en_core_web_sm -t tutor-api .   # smaller, for tests
FROM python:3.12-slim

ARG SPACY_MODEL=en_core_web_lg
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # the privacy filter refuses to start unless this model is installed, so image and config always match
    PRIVACY__SPACY_MODEL=${SPACY_MODEL} \
    DATABASE_URL=sqlite:////app/data/app.db

# The repository layout is kept (/app/backend, /app/content, /app/config.yaml), so app.core.config finds
# the repository root, and the package is installed in editable mode from /app/backend.
WORKDIR /app

# 1) dependencies and the spaCy model: cached unless pyproject.toml or the model changes
COPY backend/pyproject.toml backend/pyproject.toml
RUN mkdir -p backend/app && touch backend/app/__init__.py \
    && pip install -e ./backend \
    && python -m spacy download ${SPACY_MODEL}

# 2) application code, configuration and course content
COPY backend/app backend/app
COPY config.yaml ./config.yaml
COPY content ./content

RUN useradd --create-home --uid 10001 tutor && mkdir -p /app/data && chown tutor /app/data
USER tutor
WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
