from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import imagehash
from PIL import Image

from app.config import get_settings, JobConfig
from app.models import RemovalReason
from app.utils import copy_image

logger = logging.getLogger(__name__)


# ── Hash computation ────────────────────────────────────────────────────

def compute_phashes(image_paths: list[Path]) -> dict[str, imagehash.ImageHash]:
    """
    Compute perceptual hashes for all images.

    Returns ``{filename: hash}`` — skips files that cannot be opened.
    """
    hashes: dict[str, imagehash.ImageHash] = {}
    for path in image_paths:
        try:
            img = Image.open(path).convert("RGB")
            h = imagehash.phash(img, hash_size=8)
            hashes[path.name] = h
        except Exception as exc:
            logger.warning("Could not hash %s: %s", path.name, exc)
    logger.info("Computed perceptual hashes for %d images.", len(hashes))
    return hashes


# ── Duplicate grouping ──────────────────────────────────────────────────

def _build_dup_groups(
    hashes: dict[str, imagehash.ImageHash],
    threshold: int,
) -> list[set[str]]:
    """
    Find connected components of near-duplicate images.

    Two images are linked when their Hamming distance ≤ *threshold*.
    """
    names = list(hashes.keys())
    parent: dict[str, str] = {n: n for n in names}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    n = len(names)
    for i in range(n):
        for j in range(i + 1, n):
            dist = hashes[names[i]] - hashes[names[j]]  # Hamming distance
            if dist <= threshold:
                union(names[i], names[j])

    from collections import defaultdict
    groups: dict[str, set[str]] = defaultdict(set)
    for name in names:
        groups[find(name)].add(name)

    # Only return groups with actual duplicates ( > 1 member).
    return [g for g in groups.values() if len(g) > 1]


def find_duplicates(
    image_paths: list[Path],
    quality_scores: dict[str, float],
    config: Optional[JobConfig] = None,
) -> tuple[list[Path], list[tuple[Path, str]]]:
    """
    Detect and remove near-duplicate images.

    Returns
    -------
    kept : list[Path]
        Paths of images that survived deduplication.
    removed : list[tuple[Path, str]]
        ``(path, removal_reason_string)`` for removed duplicates.
    """
    settings = get_settings()
    cfg = config or settings.get_default_job_config()
    
    if not cfg.enable_duplicate_check:
        logger.info("Duplicate detection disabled by config.")
        return image_paths, []

    path_map = {p.name: p for p in image_paths}

    hashes = compute_phashes(image_paths)
    dup_groups = _build_dup_groups(hashes, cfg.phash_threshold)

    removed_names: set[str] = set()

    for group in dup_groups:
        # Pick the best by quality score (highest wins).
        ranked = sorted(
            group,
            key=lambda n: quality_scores.get(n, 0.0),
            reverse=True,
        )
        keeper = ranked[0]
        for dup_name in ranked[1:]:
            removed_names.add(dup_name)
            logger.info(
                "Duplicate detected: %s (keeping: %s, hamming=%d)",
                dup_name,
                keeper,
                hashes[dup_name] - hashes[keeper],
            )

    kept = [p for p in image_paths if p.name not in removed_names]
    removed = [
        (path_map[n], f"duplicate_{_find_keeper(n, dup_groups, removed_names)}")
        for n in removed_names
    ]

    logger.info(
        "Duplicate detection: %d kept, %d removed across %d groups.",
        len(kept), len(removed), len(dup_groups),
    )
    return kept, removed


def _find_keeper(
    removed_name: str,
    groups: list[set[str]],
    removed_names: set[str],
) -> str:
    """Find which image was kept in place of *removed_name*."""
    for group in groups:
        if removed_name in group:
            for name in group:
                if name not in removed_names:
                    return name
    return "unknown"


def get_phash_string(image_path: Path) -> Optional[str]:
    """Return the hex pHash of a single image, or None on failure."""
    try:
        img = Image.open(image_path).convert("RGB")
        return str(imagehash.phash(img, hash_size=8))
    except Exception:
        return None


def _find_keeper(
    removed_name: str,
    groups: list[set[str]],
    removed_names: set[str],
) -> str:
    """Find which image was kept in place of *removed_name*."""
    for group in groups:
        if removed_name in group:
            for name in group:
                if name not in removed_names:
                    return name
    return "unknown"


def get_phash_string(image_path: Path) -> Optional[str]:
    """Return the hex pHash of a single image, or None on failure."""
    try:
        img = Image.open(image_path).convert("RGB")
        return str(imagehash.phash(img, hash_size=8))
    except Exception:
        return None
