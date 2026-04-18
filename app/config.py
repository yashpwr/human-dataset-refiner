"""
Configuration module — all settings centralised here.

Every threshold, path, and model name is configurable via environment
variables so the Docker container can be tuned without rebuilding.
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Paths ───────────────────────────────────────────────────────────
    DATA_DIR: Path = Field(
        default=Path("/app/data"),
        description="Root data directory (mounted volume in Docker).",
    )
    MODELS_ROOT: Path = Field(
        default=Path("/models"),
        description="Directory for pre-downloaded models (baked into image).",
    )

    # ── Quality thresholds ──────────────────────────────────────────────
    BLUR_THRESHOLD: float = Field(
        default=35.0,
        description="Laplacian variance below this → blurry.",
    )
    MIN_RESOLUTION: int = Field(
        default=64,
        description="Images with width OR height below this are rejected.",
    )
    MIN_FILE_SIZE_BYTES: int = Field(
        default=2048,  # 2 KB
        description="Files smaller than this are considered suspicious.",
    )

    # ── Duplicate detection ─────────────────────────────────────────────
    PHASH_THRESHOLD: int = Field(
        default=8,
        description="Hamming distance ≤ this → near-duplicate.",
    )

    # ── Feature extraction ──────────────────────────────────────────────
    CLIP_MODEL_NAME: str = Field(
        default="ViT-B-32",
        description="open_clip model architecture.",
    )
    CLIP_PRETRAINED: str = Field(
        default="laion2b_s34b_b79k",
        description="open_clip pretrained weights tag.",
    )
    INSIGHTFACE_MODEL: str = Field(
        default="buffalo_l",
        description="InsightFace model pack name.",
    )
    BATCH_SIZE: int = Field(
        default=32,
        description="Batch size for embedding extraction.",
    )

    # ── Face Identity Clustering ───────────────────────────────────────
    FACE_DISTANCE_THRESHOLD: float = Field(
        default=0.55,
        description=(
            "Cosine distance threshold for ArcFace identity matching. "
            "Two faces with cosine distance < this value are treated as "
            "the same person.  ArcFace normed embeddings: distance ~0.0 "
            "= identical, ~1.0 = very different.  Default 0.55 is "
            "strict enough to separate different people."
        ),
    )
    CLIP_DISTANCE_THRESHOLD: float = Field(
        default=0.5,
        description=(
            "Cosine distance threshold for CLIP visual-similarity "
            "clustering (fallback for images with no detected face)."
        ),
    )

    # ── Server ──────────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=10_240,  # 10 GB
        description="Maximum upload size in megabytes.",
    )

    # ── Derived paths (computed, not from env) ──────────────────────────
    @property
    def JOBS_DIR(self) -> Path:
        return self.DATA_DIR / "jobs"

    @property
    def DATASETS_DIR(self) -> Path:
        return self.DATA_DIR / "datasets"

    @property
    def MODELS_DIR(self) -> Path:
        # If /models exists (baked into image), use it. Otherwise fallback to data/models
        if self.MODELS_ROOT.exists():
            return self.MODELS_ROOT
        return self.DATA_DIR / "models"

    @property
    def DB_PATH(self) -> Path:
        return self.DATA_DIR / "refiner.db"

    def ensure_dirs(self) -> None:
        """Create every output directory if it doesn't exist."""
        for d in (
            self.JOBS_DIR,
            self.DATASETS_DIR,
            self.MODELS_DIR,
        ):
            d.mkdir(parents=True, exist_ok=True)

    model_config = {"env_prefix": "REFINER_"}


@lru_cache()
def get_settings() -> Settings:
    """Singleton accessor — reads env once then caches."""
    settings = Settings()
    settings.ensure_dirs()
    return settings
