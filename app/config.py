from __future__ import annotations

import os
from json import dumps, loads
from pathlib import Path
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field, BaseModel


class JobConfig(BaseModel):
    """
    Job-specific tunable parameters.
    These can be overridden per job when creating or running.
    """

    blur_threshold: float = Field(
        default=35.0,
        description="Sensitivity for blur detection (Laplacian variance). Higher values are stricter, removing more images.",
    )
    min_resolution: int = Field(
        default=64,
        description="Minimum width or height in pixels. any image smaller than this will be rejected.",
    )
    face_distance_threshold: float = Field(
        default=0.55,
        description="Strictness of identity grouping. Lower is stricter (fewer images per cluster), higher is more relaxed (more merges).",
    )
    phash_threshold: int = Field(
        default=8,
        description="Hamming distance for duplicate detection. Lower is stricter (images must be nearly identical).",
    )
    enable_quality_check: bool = Field(
        default=True,
        description="Whether to perform quality checks (blur, resolution, corruption).",
    )
    enable_duplicate_check: bool = Field(
        default=True,
        description="Whether to perform perceptual hash duplicate detection.",
    )
    face_confidence: float = Field(
        default=0.6,
        description="Minimum confidence score (0.0 to 1.0) for a face to be considered valid.",
    )
    min_face_size: int = Field(
        default=50,
        description="Minimum bounding box size (pixels) for a face. Ignore tiny faces in background.",
    )


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Paths ───────────────────────────────────────────────────────────
    DATA_DIR: Path = Field(
        default=Path("/app/data"),
        description="Root data directory (mounted volume in Docker).",
    )

    # ── Default Job Config (can be overridden per job) ──────────────────
    DEFAULT_BLUR_THRESHOLD: float = Field(default=35.0)
    DEFAULT_MIN_RESOLUTION: int = Field(default=64)
    DEFAULT_FACE_DISTANCE_THRESHOLD: float = Field(default=0.55)
    DEFAULT_PHASH_THRESHOLD: int = Field(default=8)

    # ── System / Model Settings ──────────────────────────────────────────
    CLIP_MODEL_NAME: str = Field(
        default="ViT-B-32",
        description="CLIP architecture for visual features.",
    )
    CLIP_PRETRAINED: str = Field(
        default="laion2b_s34b_b79k",
        description="Pretrained weights tag for the CLIP model.",
    )
    INSIGHTFACE_MODEL: str = Field(
        default="buffalo_l",
        description="InsightFace model pack name for face detection and identification.",
    )
    BATCH_SIZE: int = Field(
        default=32,
        description="Processing batch size for ML models.",
    )
    MIN_FILE_SIZE_BYTES: int = Field(
        default=2048,  # 2 KB
        description="Files smaller than this are rejected as tiny/suspicious.",
    )
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=10_240,  # 10 GB
        description="Maximum allowed upload size for ZIP files.",
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
        return self.DATA_DIR.parent / "models"

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

    def get_default_job_config(self) -> JobConfig:
        """Return a JobConfig populated with system defaults."""
        return JobConfig(
            blur_threshold=self.DEFAULT_BLUR_THRESHOLD,
            min_resolution=self.DEFAULT_MIN_RESOLUTION,
            face_distance_threshold=self.DEFAULT_FACE_DISTANCE_THRESHOLD,
            phash_threshold=self.DEFAULT_PHASH_THRESHOLD,
        )

    model_config = {"env_prefix": "REFINER_"}


@lru_cache()
def get_settings() -> Settings:
    """Singleton accessor — reads env once then caches."""
    settings = Settings()
    settings.ensure_dirs()
    return settings
