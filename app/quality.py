from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

from app.config import get_settings, JobConfig
from app.models import QualityResult, RemovalReason
from app.utils import load_image_cv2

logger = logging.getLogger(__name__)


# ── Single-image assessment ─────────────────────────────────────────────

def _blur_score(cv_img: np.ndarray) -> float:
    """Laplacian variance — higher means sharper."""
    grey = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(grey, cv2.CV_64F).var())


def _check_corruption(path: Path) -> bool:
    """Return ``True`` if the file can be fully decoded by Pillow."""
    try:
        with Image.open(path) as img:
            img.verify()
        # verify() doesn't actually decode pixels — reopen to be sure.
        with Image.open(path) as img:
            img.load()
        return True
    except Exception:
        return False


def assess_quality(image_path: Path, config: Optional[JobConfig] = None) -> QualityResult:
    """
    Run all quality checks on a single image.

    Returns a ``QualityResult`` with the verdict and scores.
    """
    settings = get_settings()
    # Fallback to system defaults if no job-specific config provided
    cfg = config or settings.get_default_job_config()
    
    filename = image_path.name
    file_size = image_path.stat().st_size

    # ── Corruption check ────────────────────────────────────────────
    if not _check_corruption(image_path):
        return QualityResult(
            filename=filename,
            blur_score=0.0,
            resolution=(0, 0),
            file_size_bytes=file_size,
            quality_score=0.0,
            is_acceptable=False,
            removal_reason=RemovalReason.CORRUPT,
        )

    # ── Quality Check Toggle ────────────────────────────────────────
    if not cfg.enable_quality_check:
        return QualityResult(
            filename=filename,
            blur_score=0.0,
            resolution=(0, 0),
            file_size_bytes=file_size,
            quality_score=1.0,  # Neutral high score
            is_acceptable=True,
        )

    # ── File-size check ─────────────────────────────────────────────
    if file_size < settings.MIN_FILE_SIZE_BYTES:
        return QualityResult(
            filename=filename,
            blur_score=0.0,
            resolution=(0, 0),
            file_size_bytes=file_size,
            quality_score=0.0,
            is_acceptable=False,
            removal_reason=RemovalReason.TOO_SMALL_FILE,
        )

    # ── Load for pixel-level checks ─────────────────────────────────
    cv_img = load_image_cv2(image_path)
    if cv_img is None:
        return QualityResult(
            filename=filename,
            blur_score=0.0,
            resolution=(0, 0),
            file_size_bytes=file_size,
            quality_score=0.0,
            is_acceptable=False,
            removal_reason=RemovalReason.CORRUPT,
        )

    h, w = cv_img.shape[:2]
    resolution = (w, h)

    # ── Resolution check ────────────────────────────────────────────
    if w < cfg.min_resolution or h < cfg.min_resolution:
        return QualityResult(
            filename=filename,
            blur_score=0.0,
            resolution=resolution,
            file_size_bytes=file_size,
            quality_score=0.1,
            is_acceptable=False,
            removal_reason=RemovalReason.LOW_RESOLUTION,
        )

    # ── Blur check ──────────────────────────────────────────────────
    blur = _blur_score(cv_img)
    if blur < cfg.blur_threshold:
        # Normalise blur score to 0–1 range (cap at 1000 for scaling).
        norm_blur = min(blur / 1000.0, 1.0)
        return QualityResult(
            filename=filename,
            blur_score=blur,
            resolution=resolution,
            file_size_bytes=file_size,
            quality_score=round(norm_blur * 0.5, 4),  # penalised
            is_acceptable=False,
            removal_reason=RemovalReason.BLURRY,
        )

    # ── All checks passed ───────────────────────────────────────────
    norm_blur = min(blur / 1000.0, 1.0)
    # Resolution bonus: bigger is better, capped at 4096.
    res_score = min(min(w, h) / 4096.0, 1.0)
    quality_score = round(0.6 * norm_blur + 0.4 * res_score, 4)

    return QualityResult(
        filename=filename,
        blur_score=blur,
        resolution=resolution,
        file_size_bytes=file_size,
        quality_score=quality_score,
        is_acceptable=True,
    )


# ── Batch processing ────────────────────────────────────────────────────

def filter_batch(
    image_paths: list[Path],
    config: Optional[JobConfig] = None,
) -> tuple[list[Path], list[tuple[Path, QualityResult]]]:
    """
    Assess quality for a batch of images.

    Returns ``(accepted_paths, removed_list)`` where *removed_list*
    contains ``(path, quality_result)`` pairs.
    """
    accepted: list[Path] = []
    removed: list[tuple[Path, QualityResult]] = []

    for path in image_paths:
        result = assess_quality(path, config=config)
        if result.is_acceptable:
            accepted.append(path)
        else:
            removed.append((path, result))
            logger.info(
                "Removed %-30s  reason=%s  score=%.3f",
                path.name,
                result.removal_reason,
                result.quality_score,
            )

    logger.info(
        "Quality filter: %d accepted, %d removed out of %d total.",
        len(accepted), len(removed), len(image_paths),
    )
    return accepted, removed
