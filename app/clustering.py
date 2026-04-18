"""
Clustering module — face-identity-first clustering via cosine similarity.

Strategy
--------
Pass 1:  **ArcFace embeddings (identity).**
         Agglomerative clustering with *cosine distance* and
         *average linkage*.  A ``distance_threshold`` determines when
         two faces are "the same person".  This is the gold-standard
         approach for face-identity grouping because ArcFace embeddings
         are L2-normalised and specifically trained so that:
           - same person  → cosine distance ≈ 0.2–0.5
           - diff person  → cosine distance ≈ 0.8–1.2

Pass 2:  **CLIP embeddings (visual fallback).**
         For images where InsightFace did not detect a face, we fall
         back to CLIP visual embeddings with a tighter threshold.

Any image that is not placed in a cluster of ≥ 2 members is treated
as an outlier and moved to ``data/removed/``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_distances

from app.config import get_settings
from app.utils import copy_image

logger = logging.getLogger(__name__)


# ── Core clustering routine ─────────────────────────────────────────────

def _cluster_cosine(
    embeddings: np.ndarray,
    filenames: list[str],
    distance_threshold: float,
    label: str,
) -> dict[str, int]:
    """
    Cluster L2-normalised embeddings using agglomerative clustering
    with cosine distance and average linkage.

    Returns ``{filename: local_cluster_id}`` — only files that ended
    up in a cluster of size ≥ 2.  Singletons are excluded.
    """
    n = len(filenames)
    if n < 2:
        logger.info("%s: fewer than 2 vectors — skipping.", label)
        return {}

    # Compute pairwise cosine distance matrix  (0 = identical, 2 = opposite)
    dist_matrix = cosine_distances(embeddings)

    # Log summary statistics for debugging
    triu_idx = np.triu_indices(n, k=1)
    dists = dist_matrix[triu_idx]
    logger.info(
        "%s distance stats: min=%.4f  mean=%.4f  max=%.4f  (threshold=%.4f)",
        label, dists.min(), dists.mean(), dists.max(), distance_threshold,
    )

    clustering = AgglomerativeClustering(
        n_clusters=None,
        metric="precomputed",
        linkage="average",
        distance_threshold=distance_threshold,
    )
    labels = clustering.fit_predict(dist_matrix)

    # Count members per cluster and filter singletons
    from collections import Counter
    counts = Counter(labels)
    valid_clusters = {cid for cid, cnt in counts.items() if cnt >= 2}

    assignments: dict[str, int] = {}
    for i, fn in enumerate(filenames):
        cid = int(labels[i])
        if cid in valid_clusters:
            assignments[fn] = cid

    n_clusters = len(valid_clusters)
    n_assigned = len(assignments)
    n_singletons = n - n_assigned
    logger.info(
        "%s: %d clusters found, %d images assigned, %d singletons dropped.",
        label, n_clusters, n_assigned, n_singletons,
    )

    return assignments


# ── Public API ──────────────────────────────────────────────────────────

def cluster_images(
    image_paths: list[Path],
    clip_embeddings: np.ndarray,
    clip_filenames: list[str],
    face_embeddings: np.ndarray | None,
    face_filenames: list[str],
) -> dict[str, int]:
    """
    Two-pass identity-first clustering.

    Returns ``{filename: cluster_id}`` where cluster_id ≥ 0 for
    assigned clusters and -1 for unmatched images (noise / outliers).
    """
    settings = get_settings()

    assignments: dict[str, int] = {}
    next_cluster_id = 0

    # ── Pass 1: Face-identity clustering (ArcFace) ──────────────────
    if face_embeddings is not None and len(face_filenames) >= 2:
        logger.info("Pass 1: Clustering %d face embeddings by identity …", len(face_filenames))

        local_assignments = _cluster_cosine(
            face_embeddings,
            face_filenames,
            distance_threshold=settings.FACE_DISTANCE_THRESHOLD,
            label="Face-identity",
        )

        # Remap local cluster IDs to global IDs
        local_to_global: dict[int, int] = {}
        for fn, local_cid in local_assignments.items():
            if local_cid not in local_to_global:
                local_to_global[local_cid] = next_cluster_id
                next_cluster_id += 1
            assignments[fn] = local_to_global[local_cid]

        logger.info(
            "Pass 1 result: %d identity clusters, %d images assigned.",
            len(local_to_global), len(local_assignments),
        )
    else:
        logger.info("Pass 1 skipped — fewer than 2 face embeddings.")

    # ── Pass 2: CLIP visual clustering (fallback) ───────────────────
    unassigned_fns = [fn for fn in clip_filenames if fn not in assignments]
    if len(unassigned_fns) >= 2:
        logger.info(
            "Pass 2: Clustering %d unassigned images by CLIP visual similarity …",
            len(unassigned_fns),
        )
        clip_idx = {fn: i for i, fn in enumerate(clip_filenames)}
        unassigned_indices = [clip_idx[fn] for fn in unassigned_fns]
        unassigned_embeddings = clip_embeddings[unassigned_indices]

        local_assignments = _cluster_cosine(
            unassigned_embeddings,
            unassigned_fns,
            distance_threshold=settings.CLIP_DISTANCE_THRESHOLD,
            label="CLIP-visual",
        )

        local_to_global: dict[int, int] = {}
        for fn, local_cid in local_assignments.items():
            if local_cid not in local_to_global:
                local_to_global[local_cid] = next_cluster_id
                next_cluster_id += 1
            assignments[fn] = local_to_global[local_cid]
    else:
        logger.info("Pass 2 skipped — fewer than 2 unassigned images.")

    # ── Mark unassigned as outliers (-1) ─────────────────────────────
    all_filenames = set(p.name for p in image_paths)
    for fn in all_filenames:
        if fn not in assignments:
            assignments[fn] = -1

    n_clustered = sum(1 for v in assignments.values() if v >= 0)
    n_outliers = sum(1 for v in assignments.values() if v == -1)
    logger.info(
        "Final: %d clustered, %d outliers (removed), %d total clusters.",
        n_clustered, n_outliers, next_cluster_id,
    )

    return assignments


def organise_into_folders(
    image_paths: list[Path],
    assignments: dict[str, int],
) -> dict[int, list[str]]:
    """
    Copy images into ``data/grouped/cluster_NNN/`` or ``data/removed/``.

    Returns ``{cluster_id: [filenames]}`` including cluster_id == -1
    for removed images.
    """
    settings = get_settings()
    path_map = {p.name: p for p in image_paths}

    cluster_members: dict[int, list[str]] = {}

    for fn, cid in assignments.items():
        cluster_members.setdefault(cid, []).append(fn)

        src = path_map.get(fn)
        if src is None:
            continue

        if cid == -1:
            copy_image(src, settings.REMOVED_DIR)
        else:
            cluster_dir = settings.GROUPED_DIR / f"cluster_{cid:03d}"
            copy_image(src, cluster_dir)

    return cluster_members


def find_representatives(
    clip_embeddings: np.ndarray,
    clip_filenames: list[str],
    cluster_members: dict[int, list[str]],
) -> dict[int, str]:
    """
    For each cluster, find the image closest to the centroid.

    Returns ``{cluster_id: representative_filename}``.
    """
    clip_idx = {fn: i for i, fn in enumerate(clip_filenames)}
    reps: dict[int, str] = {}

    for cid, members in cluster_members.items():
        if cid == -1:
            continue
        indices = [clip_idx[fn] for fn in members if fn in clip_idx]
        if not indices:
            continue
        subset = clip_embeddings[indices]
        centroid = subset.mean(axis=0)
        distances = np.linalg.norm(subset - centroid, axis=1)
        rep_idx = indices[int(np.argmin(distances))]
        reps[cid] = clip_filenames[rep_idx]

    return reps
