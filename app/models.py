"""
Pydantic models for API request/response schemas and internal data transfer.

These models enforce structure across the pipeline — every module speaks
the same data shapes.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ───────────────────────────────────────────────────────────────

class PipelineStatus(str, Enum):
    """Current state of the processing pipeline."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RemovalReason(str, Enum):
    """Why an image was sent to the removed/ folder."""
    BLURRY = "blurry"
    LOW_RESOLUTION = "low_resolution"
    CORRUPT = "corrupt"
    TOO_SMALL_FILE = "too_small_file"
    NEAR_DUPLICATE = "near_duplicate"
    EXACT_DUPLICATE = "exact_duplicate"
    NO_CLUSTER = "no_cluster"


# ── Image-level metadata ───────────────────────────────────────────────

class QualityResult(BaseModel):
    """Result of quality assessment for a single image."""
    filename: str
    blur_score: float = Field(description="Laplacian variance — higher is sharper.")
    resolution: tuple[int, int] = Field(description="(width, height)")
    file_size_bytes: int
    quality_score: float = Field(
        ge=0.0, le=1.0,
        description="Normalised composite quality 0–1.",
    )
    is_acceptable: bool
    removal_reason: Optional[RemovalReason] = None


class ImageMetadata(BaseModel):
    """Full metadata record for one image — written to the report."""
    filename: str
    cluster_id: Optional[int] = Field(
        default=None,
        description="Cluster assignment. None if removed before clustering.",
    )
    quality_score: float = Field(ge=0.0, le=1.0)
    blur_score: float
    resolution: tuple[int, int]
    face_detected: bool = False
    phash: Optional[str] = None
    removal_reason: Optional[str] = None
    similarity_group: Optional[str] = Field(
        default=None,
        description="Human-readable grouping label.",
    )
    destination: str = Field(
        default="input",
        description="Which output folder this image ended up in.",
    )


# ── Cluster-level metadata ─────────────────────────────────────────────

class ClusterInfo(BaseModel):
    """Summary of a single cluster."""
    cluster_id: int
    cluster_name: Optional[str] = None
    member_count: int
    member_filenames: list[str]
    representative_filename: Optional[str] = Field(
        default=None,
        description="Image closest to the cluster centroid.",
    )
    cluster_type: str = Field(
        default="visual",
        description="'face' for face-based clusters, 'visual' for CLIP-based.",
    )


# ── Pipeline-level responses ───────────────────────────────────────────

class ProcessingReport(BaseModel):
    """Top-level report returned by /report."""
    total_images: int
    accepted_images: int
    removed_count: int
    outliers_count: int
    clusters_count: int
    clusters: list[ClusterInfo]
    images: list[ImageMetadata]
    thresholds: dict


class PipelineState(BaseModel):
    """Status response returned by /status."""
    status: PipelineStatus = PipelineStatus.IDLE
    progress: float = Field(
        default=0.0, ge=0.0, le=100.0,
        description="Percentage complete.",
    )
    current_step: str = ""
    error: Optional[str] = None
    total_images: Optional[int] = None


class UploadResponse(BaseModel):
    """Response after a successful upload."""
    message: str
    image_count: int
    filenames: list[str]
