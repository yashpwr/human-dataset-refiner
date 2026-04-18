# ==============================================================================
#  Human Dataset Refiner — Dockerfile
#
#  Multi-stage build:
#    Stage 1: System dependencies + Python packages
#    Stage 2: Application code
#
#  Default: CPU mode.  GPU support via docker-compose profile.
# ==============================================================================

FROM python:3.11-slim AS base

# ── System dependencies for OpenCV, InsightFace, and image processing ────
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    cmake \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies first (Docker layer cache) ──────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Pre-download models (Baking) ────────────────────────────────────────
# We do this during build so the container is ready instantly.
COPY app/config.py ./app/
COPY app/__init__.py ./app/
COPY scripts/download_models.py ./scripts/
RUN mkdir -p /models_baked && REFINER_MODELS_ROOT=/models_baked python scripts/download_models.py

# ── Copy entrypoint script ──────────────────────────────────────────────
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ── Copy application code ───────────────────────────────────────────────
COPY app/ ./app/
COPY scripts/ ./scripts/

# ── Create data directories ─────────────────────────────────────────────
RUN mkdir -p data/jobs data/datasets models

ENTRYPOINT ["/entrypoint.sh"]

# ── Run (passed as args to entrypoint) ──────────────────────────────────
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
