"""
Ingestion module — handles uploads and extracts images into the input folder.

Supports:
  • Single or multiple image file uploads (multipart)
  • ZIP archive upload (automatically extracted)

All files land in ``data/input/`` with their **original filenames** intact.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import BinaryIO

from app.config import get_settings
from app.utils import is_image_file, IGNORED_FILENAMES

logger = logging.getLogger(__name__)


def _sanitise_zip_entry(name: str) -> str | None:
    """
    Return a safe filename from a zip entry, or ``None`` to skip.

    • Strips directory prefixes (we flatten into input/).
    • Skips macOS / Windows metadata files.
    • Rejects path-traversal attempts.
    """
    p = Path(name)

    # Skip directories and hidden/system files.
    if name.endswith("/") or p.name.startswith(".") or p.name in IGNORED_FILENAMES:
        return None

    # Only the basename — we flatten.
    safe_name = p.name

    # Block traversal.
    if ".." in safe_name:
        return None

    return safe_name


async def ingest_zip(file: BinaryIO, filename: str, target_dir: Path | None = None) -> list[str]:
    """
    Extract a ZIP archive into the specified directory or globally.

    Returns the list of original filenames that were accepted.
    """
    settings = get_settings()
    input_dir = target_dir if target_dir else settings.INPUT_DIR
    input_dir.mkdir(parents=True, exist_ok=True)

    accepted: list[str] = []

    # Write the upload to a temp file so zipfile can seek.
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".zip", dir=str(settings.DATA_DIR)
    ) as tmp:
        shutil.copyfileobj(file, tmp)
        tmp_path = Path(tmp.name)

    try:
        with zipfile.ZipFile(tmp_path, "r") as zf:
            for entry in zf.namelist():
                safe = _sanitise_zip_entry(entry)
                if safe is None:
                    continue

                dest = input_dir / safe
                if not is_image_file(dest):
                    logger.debug("Skipping non-image zip entry: %s", safe)
                    continue

                # Handle name collisions: keep the first occurrence.
                if dest.exists():
                    logger.warning("Duplicate name in zip, skipping: %s", safe)
                    continue

                # Extract single member.
                with zf.open(entry) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)

                accepted.append(safe)
                logger.debug("Extracted: %s", safe)
    finally:
        tmp_path.unlink(missing_ok=True)

    logger.info(
        "Ingested %d images from zip '%s'", len(accepted), filename,
    )
    return accepted


async def ingest_images(files: list[tuple[str, BinaryIO]]) -> list[str]:
    """
    Save uploaded image files directly into ``data/input/``.

    *files* is a list of ``(original_filename, file_object)`` pairs.
    Returns the list of accepted filenames.
    """
    settings = get_settings()
    input_dir = settings.INPUT_DIR
    input_dir.mkdir(parents=True, exist_ok=True)

    accepted: list[str] = []

    for original_name, file_obj in files:
        dest = input_dir / original_name

        if not is_image_file(dest):
            logger.debug("Skipping non-image upload: %s", original_name)
            continue

        if dest.exists():
            logger.warning("File already exists, skipping: %s", original_name)
            continue

        with open(dest, "wb") as f:
            shutil.copyfileobj(file_obj, f)

        accepted.append(original_name)

    logger.info("Ingested %d individual image uploads.", len(accepted))
    return accepted


def clear_outputs() -> None:
    """
    Wipe all output directories before a fresh pipeline run.

    ``data/input/`` is intentionally **not** cleared — the user controls it.
    """
    settings = get_settings()
    for d in (
        settings.GROUPED_DIR,
        settings.REMOVED_DIR,
        settings.OUTLIERS_DIR,
        settings.METADATA_DIR,
        settings.EMBEDDINGS_DIR,
    ):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    logger.info("Cleared output directories.")
