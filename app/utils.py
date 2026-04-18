"""
Utility helpers shared across modules.

Keeps image I/O, path handling, and common constants in one place
so pipeline modules stay focused on their own logic.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Supported image extensions (lowercase).
SUPPORTED_EXTENSIONS: set[str] = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif",
}

# Files to always skip.
IGNORED_FILENAMES: set[str] = {
    ".DS_Store", "Thumbs.db", "desktop.ini", ".gitkeep",
}


def is_image_file(path: Path) -> bool:
    """Return True if *path* looks like a supported image file."""
    if path.name in IGNORED_FILENAMES:
        return False
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def discover_images(directory: Path) -> list[Path]:
    """
    Recursively find all supported image files under *directory*.

    Returns a sorted list of absolute ``Path`` objects.
    """
    if not directory.exists():
        return []
    images = sorted(
        p for p in directory.rglob("*") if p.is_file() and is_image_file(p)
    )
    logger.info("Discovered %d images in %s", len(images), directory)
    return images


def load_image_pil(path: Path) -> Optional[Image.Image]:
    """Load an image via Pillow, returning ``None`` on failure."""
    try:
        img = Image.open(path)
        img.load()  # force full decode to catch truncation
        return img.convert("RGB")
    except Exception as exc:
        logger.warning("Failed to load %s: %s", path.name, exc)
        return None


def load_image_cv2(path: Path) -> Optional[np.ndarray]:
    """Load an image via OpenCV (BGR), returning ``None`` on failure."""
    try:
        img = cv2.imread(str(path))
        if img is None:
            raise ValueError("cv2.imread returned None")
        return img
    except Exception as exc:
        logger.warning("Failed to load %s via cv2: %s", path.name, exc)
        return None


def copy_image(src: Path, dst_dir: Path) -> Path:
    """
    Copy an image to *dst_dir* preserving its original filename.

    If a name collision occurs the file is silently skipped (the copy
    already exists).  Returns the destination path.
    """
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name

    if dst.exists():
        logger.debug("Copy target already exists, skipping: %s", dst)
        return dst

    import shutil
    shutil.copy2(str(src), str(dst))
    return dst
