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

# ── Copy application code and scripts ──────────────────────────────────
COPY app/ ./app/
COPY scripts/ ./scripts/

# ── Set model cache environments (baked into image) ─────────────────────
ENV HF_HOME=/models/huggingface
ENV INSIGHTFACE_HOME=/models/insightface

# ── Pre-download models ─────────────────────────────────────────────────
RUN mkdir -p /models && python scripts/download_models.py

# ── Create data directories ─────────────────────────────────────────────
RUN mkdir -p data/jobs data/datasets data/models

# ── Expose API port ─────────────────────────────────────────────────────
EXPOSE 8000

# ── Health check ────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── Run ─────────────────────────────────────────────────────────────────
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
