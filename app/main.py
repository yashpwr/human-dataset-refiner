"""
FastAPI application — REST API for the Human Dataset Refiner.

v2: Job-centric API. Every pipeline run is a named "Job" with its
own folder structure, cluster records, and removed-image log.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import get_settings
from app.ingestion import ingest_images, ingest_zip
from app import db
from app.pipeline import get_active_job_id, run_pipeline

# ── Logging ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── App ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Human Dataset Refiner",
    description="AI-powered dataset cleaning tool — Job-centric API.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount data directory for serving images
app.mount("/data", StaticFiles(directory=get_settings().DATA_DIR), name="data")


# ── Startup ─────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    get_settings()
    db.init_db()
    logger.info("Human Dataset Refiner v2.0.0 ready.")


# ── Request schemas ─────────────────────────────────────────────────────

class CreateJobRequest(BaseModel):
    name: str

class RenameRequest(BaseModel):
    name: str

class AssignDatasetRequest(BaseModel):
    dataset_id: int


# ── Jobs ────────────────────────────────────────────────────────────────

@app.post("/jobs", tags=["Jobs"])
async def create_job(req: CreateJobRequest):
    """Create a new job with a user-defined name."""
    name = req.name.strip()
    if not name or "/" in name or "\\" in name:
        raise HTTPException(400, "Invalid job name.")
    existing = db.get_job_by_name(name)
    if existing:
        raise HTTPException(409, f"Job '{name}' already exists.")
    job = db.create_job(name)
    return job


@app.get("/jobs", tags=["Jobs"])
async def list_jobs():
    """List all jobs with their status."""
    jobs = db.list_jobs()
    settings = get_settings()
    # Enrich with image count from filesystem
    for job in jobs:
        ds_id = job.get("dataset_id")
        if ds_id:
            ds = db.get_dataset(ds_id)
            if ds:
                ds_dir = settings.DATASETS_DIR / ds["name"]
                job["dataset_name"] = ds["name"]
                job["image_count"] = len([
                    f for f in ds_dir.iterdir()
                    if f.is_file() and not f.name.startswith(".")
                ]) if ds_dir.exists() else 0
            else:
                job["image_count"] = 0
                job["dataset_name"] = None
        else:
            job["image_count"] = 0
            job["dataset_name"] = None
    return jobs


@app.get("/jobs/{job_id}", tags=["Jobs"])
async def get_job(job_id: int):
    """Get details for a specific job."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    settings = get_settings()
    if job.get("dataset_id"):
        ds = db.get_dataset(job["dataset_id"])
        if ds:
            ds_dir = settings.DATASETS_DIR / ds["name"]
            job["dataset_name"] = ds["name"]
            job["image_count"] = len([
                f for f in ds_dir.iterdir()
                if f.is_file() and not f.name.startswith(".")
            ]) if ds_dir.exists() else 0
        else:
            job["image_count"] = 0
            job["dataset_name"] = None
    else:
        job["image_count"] = 0
        job["dataset_name"] = None
    return job

@app.put("/jobs/{job_id}/rename", tags=["Jobs"])
async def rename_job(job_id: int, req: RenameRequest):
    """Rename a job."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
        
    new_name = req.name.strip().replace(" ", "_")
    if not new_name:
        raise HTTPException(400, "New name cannot be empty.")
        
    if db.get_job_by_name(new_name):
        raise HTTPException(400, f"A job named '{new_name}' already exists.")
        
    settings = get_settings()
    old_dir = settings.JOBS_DIR / job["name"]
    new_dir = settings.JOBS_DIR / new_name
    
    if old_dir.exists():
        old_dir.rename(new_dir)
    else:
        new_dir.mkdir(parents=True, exist_ok=True)
        
    db.update_job(job_id, name=new_name)
    return {"message": f"Job renamed to {new_name}", "new_name": new_name}

@app.put("/jobs/{job_id}/dataset", tags=["Jobs"])
async def assign_dataset(job_id: int, req: AssignDatasetRequest):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    ds = db.get_dataset(req.dataset_id)
    if not ds:
        raise HTTPException(404, "Dataset not found.")
    db.update_job(job_id, dataset_id=req.dataset_id)
    return {"message": f"Dataset '{ds['name']}' assigned to job."}


@app.delete("/jobs/{job_id}", tags=["Jobs"])
async def delete_job(job_id: int):
    """Delete a job and its entire folder tree."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    settings = get_settings()
    job_dir = settings.JOBS_DIR / job["name"]
    if job_dir.exists():
        shutil.rmtree(str(job_dir))
    db.delete_job(job_id)
    return {"message": f"Job '{job['name']}' deleted."}


# ── Job Pipeline ────────────────────────────────────────────────────────

@app.post("/jobs/{job_id}/start", tags=["Jobs"])
async def start_job(job_id: int):
    """Start the pipeline for a specific job."""
    import threading

    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    if job["status"] == "running":
        raise HTTPException(409, "Job is already running.")
    if get_active_job_id() is not None:
        raise HTTPException(409, "Another job is currently running.")
    if not job.get("dataset_id"):
        raise HTTPException(400, "Job must have a dataset assigned before running.")

    ds = db.get_dataset(job["dataset_id"])
    if not ds:
        raise HTTPException(400, "Assigned dataset no longer exists.")

    thread = threading.Thread(
        target=run_pipeline, args=(job_id, job["name"], ds["name"]), daemon=True
    )
    thread.start()
    return {"message": f"Pipeline started for job '{job['name']}'."}


# ── Datasets ────────────────────────────────────────────────────────────

@app.post("/datasets", tags=["Datasets"])
async def create_dataset(req: CreateJobRequest):
    name = req.name.strip()
    if not name or "/" in name or "\\" in name:
        raise HTTPException(400, "Invalid dataset name.")
    existing = db.get_dataset_by_name(name)
    if existing:
        raise HTTPException(409, f"Dataset '{name}' already exists.")
    ds = db.create_dataset(name)
    return ds

@app.put("/datasets/{dataset_id}/rename", tags=["Datasets"])
async def rename_dataset(dataset_id: int, req: RenameRequest):
    ds = db.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(404, "Dataset not found.")
        
    new_name = req.name.strip().replace(" ", "_")
    if not new_name:
        raise HTTPException(400, "New name cannot be empty.")
        
    if db.get_dataset_by_name(new_name):
        raise HTTPException(400, f"A dataset named '{new_name}' already exists.")
        
    settings = get_settings()
    old_dir = settings.DATASETS_DIR / ds["name"]
    new_dir = settings.DATASETS_DIR / new_name
    
    if old_dir.exists():
        old_dir.rename(new_dir)
    else:
        new_dir.mkdir(parents=True, exist_ok=True)
        
    db.update_dataset(dataset_id, name=new_name)
    return {"message": f"Dataset renamed to {new_name}", "new_name": new_name}

@app.get("/datasets", tags=["Datasets"])
async def list_datasets():
    datasets = db.list_datasets()
    settings = get_settings()
    for ds in datasets:
        ds_dir = settings.DATASETS_DIR / ds["name"]
        if ds_dir.exists():
            ds["image_count"] = len([
                f for f in ds_dir.iterdir()
                if f.is_file() and not f.name.startswith(".")
            ])
        else:
            ds["image_count"] = 0
    return datasets

@app.get("/datasets/{dataset_id}/images", tags=["Datasets"])
async def list_dataset_images(dataset_id: int):
    ds = db.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(404, "Dataset not found.")
    settings = get_settings()
    ds_dir = settings.DATASETS_DIR / ds["name"]
    if not ds_dir.exists():
        return {"images": []}
    images = sorted([
        f.name for f in ds_dir.iterdir()
        if f.is_file() and not f.name.startswith(".")
    ])
    return {"images": images}

@app.post("/datasets/{dataset_id}/upload", tags=["Datasets"])
async def upload_to_dataset(dataset_id: int, files: list[UploadFile] = File(...)):
    ds = db.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(404, "Dataset not found.")

    settings = get_settings()
    ds_dir = settings.DATASETS_DIR / ds["name"]
    ds_dir.mkdir(parents=True, exist_ok=True)

    all_accepted: list[str] = []
    for upload_file in files:
        name = upload_file.filename or "unknown"
        if name.lower().endswith(".zip"):
            accepted = await ingest_zip(upload_file.file, name, target_dir=ds_dir)
            all_accepted.extend(accepted)
        else:
            dest = ds_dir / name
            content = await upload_file.read()
            dest.write_bytes(content)
            all_accepted.append(name)

    if not all_accepted:
        raise HTTPException(400, "No valid image files found.")

    return {
        "message": f"Uploaded {len(all_accepted)} image(s).",
        "image_count": len(all_accepted),
        "filenames": sorted(all_accepted),
    }

@app.delete("/datasets/{dataset_id}", tags=["Datasets"])
async def delete_dataset(dataset_id: int):
    ds = db.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(404, "Dataset not found.")
    settings = get_settings()
    ds_dir = settings.DATASETS_DIR / ds["name"]
    if ds_dir.exists():
        shutil.rmtree(str(ds_dir))
    db.delete_dataset(dataset_id)
    # Note: jobs referencing this dataset will have dataset_id set to NULL due to ON DELETE SET NULL
    return {"message": f"Dataset '{ds['name']}' deleted."}

@app.delete("/datasets/{dataset_id}/images/{name}", tags=["Datasets"])
async def delete_dataset_image(dataset_id: int, name: str):
    ds = db.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(404, "Dataset not found.")
    settings = get_settings()
    source = settings.DATASETS_DIR / ds["name"] / name
    if not source.exists():
        raise HTTPException(404, "Image not found.")
    source.unlink()
    return {"message": f"Image '{name}' deleted."}


# ── Job Clusters ────────────────────────────────────────────────────────

@app.get("/jobs/{job_id}/clusters", tags=["Jobs"])
async def get_job_clusters(job_id: int):
    """Get clusters for a specific job."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return db.get_clusters(job_id)


@app.put("/jobs/{job_id}/clusters/{cluster_id}/name", tags=["Jobs"])
async def rename_job_cluster(job_id: int, cluster_id: int, req: RenameRequest):
    """Rename a cluster and its directory."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")

    clusters = db.get_clusters(job_id)
    target = next((c for c in clusters if c["cluster_id"] == cluster_id), None)
    if not target:
        raise HTTPException(404, "Cluster not found.")

    settings = get_settings()
    old_name = target["cluster_name"] or f"cluster_{cluster_id:03d}"
    new_name = req.name.strip()
    if not new_name or "/" in new_name or "\\" in new_name:
        raise HTTPException(400, "Invalid name.")

    old_dir = settings.JOBS_DIR / job["name"] / "grouped" / old_name
    new_dir = settings.JOBS_DIR / job["name"] / "grouped" / new_name

    if old_dir.exists() and not new_dir.exists():
        shutil.move(str(old_dir), str(new_dir))

    db.update_cluster_name(job_id, cluster_id, new_name)
    return {"message": f"Cluster renamed to '{new_name}'."}


@app.delete("/jobs/{job_id}/clusters/{cluster_id}", tags=["Jobs"])
async def delete_job_cluster(job_id: int, cluster_id: int):
    """Delete a cluster and its directory."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")

    clusters = db.get_clusters(job_id)
    target = next((c for c in clusters if c["cluster_id"] == cluster_id), None)
    if not target:
        raise HTTPException(404, "Cluster not found.")

    settings = get_settings()
    folder_name = target["cluster_name"] or f"cluster_{cluster_id:03d}"
    cluster_dir = settings.JOBS_DIR / job["name"] / "grouped" / folder_name

    if cluster_dir.exists():
        shutil.rmtree(str(cluster_dir))

    db.delete_cluster(job_id, cluster_id)
    return {"message": "Cluster deleted."}


# ── Job Removed Images ─────────────────────────────────────────────────

@app.get("/jobs/{job_id}/removed", tags=["Jobs"])
async def get_job_removed(job_id: int):
    """Get removed images with reasons for a specific job."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return db.get_removed(job_id)


# ── Legacy endpoints (backward compat) ─────────────────────────────────

@app.get("/status", tags=["Legacy"])
async def legacy_status():
    """Legacy: returns status of the currently active job."""
    active_id = get_active_job_id()
    if active_id:
        job = db.get_job(active_id)
        if job:
            return {
                "status": job["status"],
                "progress": job["progress"],
                "current_step": job["current_step"],
                "error": job["error"],
                "total_images": job["total_images"],
            }
    # Check if any job is running
    for job in db.list_jobs():
        if job["status"] == "running":
            return {
                "status": job["status"],
                "progress": job["progress"],
                "current_step": job["current_step"],
                "error": job["error"],
                "total_images": job["total_images"],
            }
    return {
        "status": "idle",
        "progress": 0,
        "current_step": "",
        "error": None,
        "total_images": 0,
    }


# ── Health ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "version": "2.0.0"}
