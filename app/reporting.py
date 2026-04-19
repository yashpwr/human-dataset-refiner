"""
Reporting module — generates CSV and JSON reports from pipeline results.

All reports are written to ``data/metadata/``.  Original filenames are
always preserved — no renaming anywhere.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings, JobConfig
from app.models import ClusterInfo, ImageMetadata, ProcessingReport

logger = logging.getLogger(__name__)


def _write_csv(
    images: list[ImageMetadata],
    output_path: Path,
) -> None:
    """Write per-image metadata to a CSV file."""
    fieldnames = [
        "filename",
        "cluster_id",
        "quality_score",
        "blur_score",
        "resolution_w",
        "resolution_h",
        "face_detected",
        "phash",
        "removal_reason",
        "similarity_group",
        "destination",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for img in images:
            writer.writerow(
                {
                    "filename": img.filename,
                    "cluster_id": img.cluster_id if img.cluster_id is not None else "",
                    "quality_score": f"{img.quality_score:.4f}",
                    "blur_score": f"{img.blur_score:.2f}",
                    "resolution_w": img.resolution[0],
                    "resolution_h": img.resolution[1],
                    "face_detected": img.face_detected,
                    "phash": img.phash or "",
                    "removal_reason": img.removal_reason or "",
                    "similarity_group": img.similarity_group or "",
                    "destination": img.destination,
                }
            )

    logger.info("Wrote CSV report: %s (%d rows)", output_path.name, len(images))


def _write_json(data: dict, output_path: Path) -> None:
    """Write a JSON report."""
    output_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    logger.info("Wrote JSON report: %s", output_path.name)


def generate_report(
    all_image_metadata: list[ImageMetadata],
    cluster_members: dict[int, list[str]],
    representatives: dict[int, str],
    metadata_dir: Path,
    config: JobConfig,
) -> ProcessingReport:
    """
    Build the final ``ProcessingReport`` and write CSV + JSON files.
    """
    settings = get_settings()

    # ── Build cluster info ──────────────────────────────────────────
    clusters: list[ClusterInfo] = []
    for cid, members in sorted(cluster_members.items()):
        if cid == -1:
            continue
        clusters.append(
            ClusterInfo(
                cluster_id=cid,
                member_count=len(members),
                member_filenames=sorted(members),
                representative_filename=representatives.get(cid),
                cluster_type="face" if cid < 1000 else "visual",
                # Convention: face clusters get IDs < 1000 (but in practice
                # the pipeline assigns IDs sequentially — the type is set
                # during cluster construction).
            )
        )

    removed_count = sum(1 for im in all_image_metadata if im.removal_reason)
    accepted_count = len(all_image_metadata) - removed_count

    report = ProcessingReport(
        total_images=len(all_image_metadata),
        accepted_images=accepted_count,
        removed_count=removed_count,
        outliers_count=0, # Deprecated concept
        clusters_count=len(clusters),
        clusters=clusters,
        images=all_image_metadata,
        thresholds={
            "blur_threshold": config.blur_threshold,
            "min_resolution": config.min_resolution,
            "phash_threshold": config.phash_threshold,
            "face_distance_threshold": config.face_distance_threshold,
            "face_confidence": config.face_confidence,
            "min_face_size": config.min_face_size,
            "clip_model": settings.CLIP_MODEL_NAME,
            "insightface_model": settings.INSIGHTFACE_MODEL,
        },
    )

    # ── Write outputs ───────────────────────────────────────────────
    _write_csv(all_image_metadata, metadata_dir / "image_metadata.csv")

    _write_json(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_images": report.total_images,
                "accepted_images": report.accepted_images,
                "removed_count": report.removed_count,
                "outliers_count": report.outliers_count,
                "clusters_count": report.clusters_count,
            },
            "thresholds": report.thresholds,
            "clusters": [c.model_dump() for c in clusters],
        },
        metadata_dir / "clusters_summary.json",
    )

    _write_json(
        report.model_dump(),
        metadata_dir / "processing_report.json",
    )

    logger.info(
        "Report generated: %d images, %d clusters, %d removed, %d outliers.",
        report.total_images,
        report.clusters_count,
        report.removed_count,
        report.outliers_count,
    )

    return report
