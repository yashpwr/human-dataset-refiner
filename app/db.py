"""
SQLite persistence layer for the Human Dataset Refiner.

Stores job state, cluster assignments, and removed-image records so
that data survives container restarts.  Uses Python's built-in
``sqlite3`` — zero extra dependencies.

Thread safety: every public helper opens its own connection so the
module is safe to call from both the FastAPI event-loop thread and
the background pipeline thread.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

# ── Schema ──────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    UNIQUE NOT NULL,
    created_at    TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    UNIQUE NOT NULL,
    dataset_id    INTEGER REFERENCES datasets(id) ON DELETE SET NULL,
    status        TEXT    DEFAULT 'idle',
    progress      REAL    DEFAULT 0,
    current_step  TEXT    DEFAULT '',
    error         TEXT,
    total_images  INTEGER DEFAULT 0,
    created_at    TEXT    DEFAULT (datetime('now')),
    completed_at  TEXT
);

CREATE TABLE IF NOT EXISTS job_clusters (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id            INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    cluster_id        INTEGER NOT NULL,
    cluster_name      TEXT,
    member_count      INTEGER,
    member_filenames  TEXT,
    representative    TEXT,
    cluster_type      TEXT DEFAULT 'face'
);

CREATE TABLE IF NOT EXISTS job_removed (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id        INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    filename      TEXT    NOT NULL,
    reason        TEXT,
    quality_score REAL,
    blur_score    REAL
);
"""


# ── Helpers ─────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    """Return a new connection with WAL mode and foreign-key enforcement."""
    settings = get_settings()
    db_path = settings.DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables if they don't already exist."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        
        # Migration: Add dataset_id to jobs if missing
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN dataset_id INTEGER REFERENCES datasets(id) ON DELETE SET NULL")
            conn.commit()
            logger.info("Migrated jobs table to include dataset_id.")
        except sqlite3.OperationalError:
            # Column already exists
            pass

    logger.info("SQLite database initialised at %s", get_settings().DB_PATH)


# ── Jobs CRUD ───────────────────────────────────────────────────────────

def create_job(name: str) -> dict:
    """Insert a new job and create its folder structure. Returns the row."""
    settings = get_settings()
    job_dir = settings.JOBS_DIR / name
    for sub in ("grouped", "removed"):
        (job_dir / sub).mkdir(parents=True, exist_ok=True)

    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO jobs (name) VALUES (?)", (name,)
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM jobs WHERE id=?", (cur.lastrowid,)).fetchone())

# ── Datasets CRUD ───────────────────────────────────────────────────────

def create_dataset(name: str) -> dict:
    settings = get_settings()
    ds_dir = settings.DATASETS_DIR / name
    ds_dir.mkdir(parents=True, exist_ok=True)

    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO datasets (name) VALUES (?)", (name,)
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM datasets WHERE id=?", (cur.lastrowid,)).fetchone())

def list_datasets() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM datasets ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

def get_dataset(dataset_id: int) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
        return dict(row) if row else None

def get_dataset_by_name(name: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM datasets WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None

def update_dataset(dataset_id: int, **kwargs) -> None:
    if not kwargs:
        return
    cols = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [dataset_id]
    with _connect() as conn:
        conn.execute(f"UPDATE datasets SET {cols} WHERE id=?", vals)
        conn.commit()

def delete_dataset(dataset_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM datasets WHERE id=?", (dataset_id,))
        conn.commit()


def list_jobs() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_job(job_id: int) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None


def get_job_by_name(name: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None


def update_job(job_id: int, **kwargs) -> None:
    """Update arbitrary columns on a job row."""
    if not kwargs:
        return
    cols = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [job_id]
    with _connect() as conn:
        conn.execute(f"UPDATE jobs SET {cols} WHERE id=?", vals)
        conn.commit()


def delete_job(job_id: int) -> None:
    """Remove the job from DB (cascade deletes clusters/removed)."""
    with _connect() as conn:
        conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        conn.commit()


# ── Clusters CRUD ───────────────────────────────────────────────────────

def save_clusters(job_id: int, clusters: list[dict]) -> None:
    """Bulk-insert cluster records for a completed job."""
    with _connect() as conn:
        conn.execute("DELETE FROM job_clusters WHERE job_id=?", (job_id,))
        for c in clusters:
            conn.execute(
                """INSERT INTO job_clusters
                   (job_id, cluster_id, cluster_name, member_count,
                    member_filenames, representative, cluster_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    c["cluster_id"],
                    c.get("cluster_name"),
                    c["member_count"],
                    json.dumps(c["member_filenames"]),
                    c.get("representative"),
                    c.get("cluster_type", "face"),
                ),
            )
        conn.commit()


def get_clusters(job_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM job_clusters WHERE job_id=? ORDER BY cluster_id", (job_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["member_filenames"] = json.loads(d["member_filenames"]) if d["member_filenames"] else []
            result.append(d)
        return result


def update_cluster_name(job_id: int, cluster_id: int, new_name: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE job_clusters SET cluster_name=? WHERE job_id=? AND cluster_id=?",
            (new_name, job_id, cluster_id),
        )
        conn.commit()


def delete_cluster(job_id: int, cluster_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM job_clusters WHERE job_id=? AND cluster_id=?",
            (job_id, cluster_id),
        )
        conn.commit()


# ── Removed Images CRUD ────────────────────────────────────────────────

def save_removed(job_id: int, images: list[dict]) -> None:
    """Bulk-insert removed-image records."""
    with _connect() as conn:
        conn.execute("DELETE FROM job_removed WHERE job_id=?", (job_id,))
        for img in images:
            conn.execute(
                """INSERT INTO job_removed
                   (job_id, filename, reason, quality_score, blur_score)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    job_id,
                    img["filename"],
                    img.get("reason"),
                    img.get("quality_score", 0),
                    img.get("blur_score", 0),
                ),
            )
        conn.commit()


def get_removed(job_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM job_removed WHERE job_id=? ORDER BY filename", (job_id,)
        ).fetchall()
        return [dict(r) for r in rows]
