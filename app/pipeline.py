"""
Pipeline orchestrator — ties ingestion, quality, dedup, features,
clustering, and reporting into a single ``run_pipeline()`` function.

Runs synchronously in a background **thread** so the event loop
stays responsive for ``/status`` polling.

v2: Job-scoped — each run targets a specific job folder.
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.models import (
    ImageMetadata,
    PipelineState,
    PipelineStatus,
    ProcessingReport,
    RemovalReason,
)
from app.utils import discover_images, copy_image
from app.ingestion import clear_outputs
from app.quality import assess_quality, filter_batch
from app.duplicates import find_duplicates, get_phash_string
from app.features import extract_clip_embeddings, extract_face_embeddings
from app.clustering import cluster_images, organise_into_folders, find_representatives
from app.reporting import generate_report
from app import db

logger = logging.getLogger(__name__)

# ── Active job tracking (for legacy /status endpoint) ───────────────────

_active_job_id: int | None = None


def get_active_job_id() -> int | None:
    return _active_job_id


# ── Main pipeline ──────────────────────────────────────────────────────

def run_pipeline(job_id: int, job_name: str, dataset_name: str) -> None:
    """
    Execute the full cleaning pipeline for a specific job.

    Runs **synchronously** in a background thread so the FastAPI
    event loop is not blocked and ``/jobs/{id}`` remains responsive.
    """
    global _active_job_id
    _active_job_id = job_id
    settings = get_settings()
    job_dir = settings.JOBS_DIR / job_name
    input_dir = settings.DATASETS_DIR / dataset_name
    grouped_dir = job_dir / "grouped"
    removed_dir = job_dir / "removed"
    embeddings_dir = job_dir / "embeddings"
    metadata_dir = job_dir / "metadata"

    # Ensure output dirs exist
    for d in (grouped_dir, removed_dir, embeddings_dir, metadata_dir):
        d.mkdir(parents=True, exist_ok=True)

    def _update(step: str, progress: float) -> None:
        db.update_job(job_id, current_step=step, progress=progress)
        logger.info("[Job %d] [%.0f%%] %s", job_id, progress, step)

    db.update_job(job_id, status="running", progress=0.0, error=None)

    try:
        # ── Step 0: Clean previous outputs ──────────────────────────
        _update("Preparing output directories", 2)
        # Clear only this job's grouped/removed (not global)
        import shutil
        for d in (grouped_dir, removed_dir):
            if d.exists():
                shutil.rmtree(str(d))
            d.mkdir(parents=True, exist_ok=True)

        # ── Step 1: Discover images ─────────────────────────────────
        _update("Discovering images", 5)
        all_images = discover_images(input_dir)
        if not all_images:
            raise ValueError("No images found in job input/ directory.")
        db.update_job(job_id, total_images=len(all_images))
        logger.info("Found %d images in %s.", len(all_images), input_dir)

        # ── Step 2: Quality filtering ───────────────────────────────
        _update("Assessing image quality", 10)
        accepted, removed_quality = filter_batch(all_images)

        quality_map: dict[str, float] = {}
        quality_results: dict[str, object] = {}
        for path in accepted:
            qr = assess_quality(path)
            quality_map[path.name] = qr.quality_score
            quality_results[path.name] = qr

        for path, qr in removed_quality:
            quality_results[path.name] = qr

        # Copy removed images to job's removed/ subfolders
        for path, qr in removed_quality:
            reason = str(qr.removal_reason.value) if qr.removal_reason else "unknown"
            reason_dir = removed_dir / reason
            reason_dir.mkdir(parents=True, exist_ok=True)
            dst = copy_image(path, reason_dir)
            logger.info("Copied to removed/%s: %s → %s", reason, path.name, dst)

        _update("Quality filtering complete", 20)

        # ── Step 3: Duplicate detection ─────────────────────────────
        _update("Detecting duplicates", 25)
        accepted, removed_dups = find_duplicates(accepted, quality_map)

        for path, reason in removed_dups:
            reason_dir = removed_dir / reason
            reason_dir.mkdir(parents=True, exist_ok=True)
            dst = copy_image(path, reason_dir)
            logger.info("Copied to removed/%s: %s → %s", reason, path.name, dst)

        _update("Duplicate detection complete", 35)

        if not accepted:
            raise ValueError(
                "All images were removed by quality/duplicate filters. "
                "Consider adjusting thresholds."
            )

        # ── Step 4: Feature extraction ──────────────────────────────
        _update("Extracting CLIP embeddings", 40)
        clip_emb, clip_fns = extract_clip_embeddings(accepted, embeddings_dir)
        _update("CLIP embeddings done", 55)

        _update("Extracting face embeddings", 58)
        face_emb, face_fns, face_flags = extract_face_embeddings(accepted, embeddings_dir)
        _update("Face embeddings done", 70)

        # ── Step 5: Clustering ──────────────────────────────────────
        _update("Clustering images", 72)
        assignments = cluster_images(
            accepted, clip_emb, clip_fns, face_emb, face_fns,
        )

        # Override organise_into_folders to use job-scoped grouped_dir
        from collections import defaultdict
        cluster_members: dict[int, list[str]] = defaultdict(list)
        for path in accepted:
            cid = assignments.get(path.name, -1)
            cluster_members[cid].append(path.name)

        # Create cluster folders and copy images
        for cid, members in cluster_members.items():
            if cid == -1:
                # Noise → removed
                for fn in members:
                    src = input_dir / fn
                    if src.exists():
                        reason_dir = removed_dir / "no_cluster"
                        reason_dir.mkdir(parents=True, exist_ok=True)
                        copy_image(src, reason_dir)
            else:
                cluster_folder = grouped_dir / f"cluster_{cid:03d}"
                cluster_folder.mkdir(parents=True, exist_ok=True)
                for fn in members:
                    src = input_dir / fn
                    if src.exists():
                        copy_image(src, cluster_folder)

        representatives = find_representatives(clip_emb, clip_fns, dict(cluster_members))
        _update("Clustering complete", 85)

        # ── Step 6: Build and persist metadata ──────────────────────
        _update("Building metadata", 88)

        # Save clusters to SQLite
        cluster_records = []
        for cid, members in sorted(cluster_members.items()):
            if cid == -1:
                continue
            cluster_records.append({
                "cluster_id": cid,
                "cluster_name": f"cluster_{cid:03d}",
                "member_count": len(members),
                "member_filenames": sorted(members),
                "representative": representatives.get(cid),
                "cluster_type": "face" if cid < 1000 else "visual",
            })
        db.save_clusters(job_id, cluster_records)

        # Save removed images to SQLite
        removed_records = []
        # Quality removed
        for path, qr in removed_quality:
            removed_records.append({
                "filename": path.name,
                "reason": str(qr.removal_reason.value) if qr.removal_reason else "unknown",
                "quality_score": qr.quality_score,
                "blur_score": qr.blur_score,
            })
        # Duplicate removed
        for path, reason in removed_dups:
            qr = quality_results.get(path.name)
            removed_records.append({
                "filename": path.name,
                "reason": reason,
                "quality_score": qr.quality_score if qr else 0,
                "blur_score": qr.blur_score if qr else 0,
            })
        # Noise (no cluster)
        for fn in cluster_members.get(-1, []):
            qr = quality_results.get(fn)
            removed_records.append({
                "filename": fn,
                "reason": "no_cluster",
                "quality_score": qr.quality_score if qr else 0,
                "blur_score": qr.blur_score if qr else 0,
            })
        db.save_removed(job_id, removed_records)

        # ── Step 7: Generate legacy report files ────────────────────
        _update("Generating reports", 92)
        # Build metadata for report file
        all_metadata: list[ImageMetadata] = []
        for path in accepted:
            fn = path.name
            qr = quality_results.get(fn)
            cid = assignments.get(fn)
            is_noise = cid == -1
            dest = "removed" if is_noise else f"grouped/cluster_{cid:03d}" if cid is not None else "input"
            reason = str(RemovalReason.NO_CLUSTER.value) if is_noise else None
            all_metadata.append(
                ImageMetadata(
                    filename=fn,
                    cluster_id=None if is_noise else cid,
                    quality_score=qr.quality_score if qr else 0.0,
                    blur_score=qr.blur_score if qr else 0.0,
                    resolution=qr.resolution if qr else (0, 0),
                    face_detected=face_flags.get(fn, False),
                    phash=get_phash_string(path),
                    removal_reason=reason,
                    similarity_group=f"cluster_{cid:03d}" if cid is not None and not is_noise else None,
                    destination=dest,
                )
            )
        for path, qr in removed_quality:
            all_metadata.append(
                ImageMetadata(
                    filename=path.name, cluster_id=None,
                    quality_score=qr.quality_score, blur_score=qr.blur_score,
                    resolution=qr.resolution, face_detected=False,
                    phash=get_phash_string(path),
                    removal_reason=str(qr.removal_reason.value) if qr.removal_reason else None,
                    destination="removed",
                )
            )
        for path, reason in removed_dups:
            qr = quality_results.get(path.name)
            all_metadata.append(
                ImageMetadata(
                    filename=path.name, cluster_id=None,
                    quality_score=qr.quality_score if qr else 0.0,
                    blur_score=qr.blur_score if qr else 0.0,
                    resolution=qr.resolution if qr else (0, 0),
                    face_detected=False, phash=get_phash_string(path),
                    removal_reason=reason, destination="removed",
                )
            )

        # Write report files into job folder
        report = generate_report(all_metadata, dict(cluster_members), representatives, metadata_dir)
        _update("Pipeline complete", 100)

        db.update_job(
            job_id,
            status="completed",
            progress=100.0,
            current_step="Pipeline complete",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        db.update_job(
            job_id,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
            current_step="Failed",
        )

    finally:
        _active_job_id = None
