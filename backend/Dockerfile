# Backend image. Build context: the repository root (it needs config.yaml, content/, data/routing/models and
# data/medical_rag too).
#   docker build -f backend/Dockerfile -t tutor-api .
#   docker build -f backend/Dockerfile --build-arg SPACY_MODEL=en_core_web_sm -t tutor-api .   # smaller, for tests
# The image carries every local model the app needs (spaCy, the routing encoder and LR/SVM weights, the two
# evidence models): it runs offline and never downloads a model while a student is asking.
FROM python:3.12-slim

ARG SPACY_MODEL=en_core_web_lg
# must match routing.* in config.yaml; the build fails below (prepare --check) if they do not
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ARG RELEVANCE_MODEL=cross-encoder/ms-marco-MiniLM-L6-v2
ARG ANSWERABILITY_MODEL=cross-encoder/qnli-electra-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # the privacy filter refuses to start unless this model is installed, so image and config always match
    PRIVACY__SPACY_MODEL=${SPACY_MODEL} \
    # what the app writes (database, instructor uploads) lives in /app/var, the only volume; what ships with the
    # image (course sources in /app/data, models) stays outside it, so a rebuild is never hidden by an old volume
    DATABASE_URL=sqlite:////app/var/app.db \
    RAG__MATERIALS_DIR=/app/var/topics \
    HF_HOME=/opt/hf \
    ROUTING__MODEL_DIR=/app/models/routing

# The repository layout is kept (/app/backend, /app/content, /app/config.yaml), so app.core.config finds
# the repository root, and the package is installed in editable mode from /app/backend.
WORKDIR /app

# 1) dependencies and the spaCy model: cached unless pyproject.toml or the model changes.
#    CPU-only torch first: the default wheel bundles CUDA (several GB) that the encoders do not need.
COPY backend/pyproject.toml backend/pyproject.toml
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && mkdir -p backend/app && touch backend/app/__init__.py \
    && pip install -e ./backend \
    && python -m spacy download ${SPACY_MODEL}

# 2) routing encoder and evidence models into the Hugging Face cache (only the files the loaders use)
RUN python -c "import sys; from sentence_transformers import CrossEncoder, SentenceTransformer; \
SentenceTransformer(sys.argv[1], device='cpu'); [CrossEncoder(m, device='cpu') for m in sys.argv[2:]]" \
    "${EMBEDDING_MODEL}" "${RELEVANCE_MODEL}" "${ANSWERABILITY_MODEL}" \
    && chmod -R a+rX /opt/hf

# 3) trained routing weights, the bundled medical sources (MedlinePlus pages for RAG), application code,
#    configuration, course content and the demo seed script
COPY data/routing/models /app/models/routing
COPY data/medical_rag /app/data/medical_rag
COPY backend/app backend/app
COPY config.yaml ./config.yaml
COPY content ./content
COPY scripts/demo_seed.py ./scripts/demo_seed.py

# from here on nothing may be downloaded; fail the build if a configured model is not in the image
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1
# and the retriever must load its bundled sources (a missing one stops the API at startup)
RUN cd backend && python -m app.routing.prepare --check \
    && python -c "from app.core.config import get_settings; from app.rag import load_retriever; \
load_retriever(get_settings().rag.impl)"

RUN useradd --create-home --uid 10001 tutor && mkdir -p /app/var && chown tutor /app/var
USER tutor
WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
