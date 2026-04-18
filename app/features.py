"""
Feature extraction module — CLIP visual embeddings + InsightFace face embeddings.

Both models are loaded **lazily** (on first call) and cached as module-level
singletons.  Embeddings are persisted to ``data/embeddings/`` so that
reprocessing the same dataset is effectively free.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from PIL import Image
from tqdm import tqdm

from app.config import get_settings

logger = logging.getLogger(__name__)

# ── Lazy model singletons ───────────────────────────────────────────────

_clip_model = None
_clip_preprocess = None
_clip_tokenizer = None
_insightface_app = None
_device: str = "cpu"


def _get_device() -> str:
    """Pick CUDA if available, else CPU."""
    global _device
    if torch.cuda.is_available():
        _device = "cuda"
    else:
        _device = "cpu"
    return _device


def _load_clip():
    """Load open_clip model + preprocessing on first call."""
    global _clip_model, _clip_preprocess, _clip_tokenizer

    if _clip_model is not None:
        return

    import open_clip

    settings = get_settings()
    device = _get_device()

    logger.info(
        "Loading CLIP model %s (%s) on %s …",
        settings.CLIP_MODEL_NAME,
        settings.CLIP_PRETRAINED,
        device,
    )
    model, _, preprocess = open_clip.create_model_and_transforms(
        settings.CLIP_MODEL_NAME,
        pretrained=settings.CLIP_PRETRAINED,
        device=device,
    )
    model.eval()
    _clip_model = model
    _clip_preprocess = preprocess
    _clip_tokenizer = open_clip.get_tokenizer(settings.CLIP_MODEL_NAME)
    logger.info("CLIP model loaded.")


def _load_insightface():
    """Load InsightFace analysis app on first call."""
    global _insightface_app

    if _insightface_app is not None:
        return

    from insightface.app import FaceAnalysis

    settings = get_settings()
    logger.info("Loading InsightFace model '%s' …", settings.INSIGHTFACE_MODEL)

    app = FaceAnalysis(
        name=settings.INSIGHTFACE_MODEL,
        root=str(settings.MODELS_DIR / "insightface"),
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    app.prepare(ctx_id=0 if torch.cuda.is_available() else -1, det_size=(640, 640))
    _insightface_app = app
    logger.info("InsightFace model loaded.")


def _load_cached_embeddings(
    kind: str,
    expected_filenames: list[str],
    embeddings_dir: Path,
) -> Optional[tuple[np.ndarray, list[str]]]:
    """
    Try to load previously saved embeddings.

    Returns ``(embeddings_array, filenames_list)`` if the cache
    matches *expected_filenames*, else ``None``.
    """
    emb_path = embeddings_dir / f"{kind}_embeddings.npy"
    fn_path = embeddings_dir / f"{kind}_filenames.json"

    if not emb_path.exists() or not fn_path.exists():
        return None

    cached_fns = json.loads(fn_path.read_text())
    if set(cached_fns) != set(expected_filenames):
        logger.info("Cache mismatch for %s embeddings — re-extracting.", kind)
        return None

    embeddings = np.load(emb_path)
    logger.info("Loaded %s embeddings from cache (%d vectors).", kind, len(embeddings))
    return embeddings, cached_fns


def _save_embeddings(
    kind: str,
    embeddings: np.ndarray,
    filenames: list[str],
    embeddings_dir: Path,
) -> None:
    """Persist embeddings + filename list for future reuse."""
    np.save(embeddings_dir / f"{kind}_embeddings.npy", embeddings)
    (embeddings_dir / f"{kind}_filenames.json").write_text(json.dumps(filenames, indent=2))
    logger.info("Saved %s embeddings (%d vectors).", kind, len(embeddings))


# ── CLIP embeddings ─────────────────────────────────────────────────────

def extract_clip_embeddings(image_paths: list[Path], embeddings_dir: Path) -> tuple[np.ndarray, list[str]]:
    """
    Extract L2-normalised CLIP embeddings for all images.

    Returns ``(embeddings, filenames)`` where embeddings is of shape
    ``(N, dim)`` and filenames is aligned to the same order.
    """
    filenames = [p.name for p in image_paths]

    # Try cache first.
    cached = _load_cached_embeddings("clip", filenames, embeddings_dir)
    if cached is not None:
        return cached

    _load_clip()
    settings = get_settings()
    device = _get_device()

    all_embeddings: list[np.ndarray] = []
    valid_filenames: list[str] = []

    for i in tqdm(range(0, len(image_paths), settings.BATCH_SIZE), desc="CLIP embeddings"):
        batch_paths = image_paths[i : i + settings.BATCH_SIZE]
        batch_tensors = []
        batch_names = []

        for path in batch_paths:
            try:
                img = Image.open(path).convert("RGB")
                tensor = _clip_preprocess(img).unsqueeze(0)
                batch_tensors.append(tensor)
                batch_names.append(path.name)
            except Exception as exc:
                logger.warning("CLIP preprocess failed for %s: %s", path.name, exc)

        if not batch_tensors:
            continue

        batch = torch.cat(batch_tensors, dim=0).to(device)

        with torch.no_grad():
            features = _clip_model.encode_image(batch)
            features = features.float()
            features = features / features.norm(dim=-1, keepdim=True)

        all_embeddings.append(features.cpu().numpy())
        valid_filenames.extend(batch_names)

    embeddings = np.vstack(all_embeddings).astype(np.float32)

    _save_embeddings("clip", embeddings, valid_filenames, embeddings_dir)
    logger.info("Extracted CLIP embeddings: shape %s", embeddings.shape)
    return embeddings, valid_filenames


# ── Face embeddings (InsightFace) ───────────────────────────────────────

def extract_face_embeddings(
    image_paths: list[Path],
    embeddings_dir: Path,
) -> tuple[np.ndarray | None, list[str], dict[str, bool]]:
    """
    Extract ArcFace embeddings for detected faces.

    For multi-face images, uses the **largest** bounding box (assumed
    to be the primary subject).

    Returns
    -------
    embeddings : np.ndarray | None
        Shape ``(M, 512)`` for the M images with a detected face.
        ``None`` if no faces were found at all.
    filenames : list[str]
        Filenames aligned with *embeddings* (only those with faces).
    face_flags : dict[str, bool]
        ``{filename: has_face}`` for every input image.
    """
    all_filenames = [p.name for p in image_paths]

    # Try cache.
    cached = _load_cached_embeddings("face", all_filenames, embeddings_dir)
    face_flags_path = embeddings_dir / "face_flags.json"
    if cached is not None and face_flags_path.exists():
        face_flags = json.loads(face_flags_path.read_text())
        return cached[0], cached[1], face_flags

    _load_insightface()

    import cv2

    embeddings_list: list[np.ndarray] = []
    face_filenames: list[str] = []
    face_flags: dict[str, bool] = {}

    for path in tqdm(image_paths, desc="Face embeddings"):
        img = cv2.imread(str(path))
        if img is None:
            face_flags[path.name] = False
            continue

        faces = _insightface_app.get(img)

        if not faces:
            face_flags[path.name] = False
            continue

        # Pick the largest face by bounding-box area.
        best = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        embedding = best.normed_embedding  # already L2-normalised

        embeddings_list.append(embedding)
        face_filenames.append(path.name)
        face_flags[path.name] = True

    if not embeddings_list:
        logger.info("No faces detected in any image.")
        # Save empty cache so we don't retry.
        (embeddings_dir / "face_flags.json").write_text(json.dumps(face_flags, indent=2))
        return None, [], face_flags

    embeddings = np.vstack(embeddings_list).astype(np.float32)

    _save_embeddings("face", embeddings, face_filenames, embeddings_dir)
    (embeddings_dir / "face_flags.json").write_text(json.dumps(face_flags, indent=2))

    logger.info(
        "Face embeddings: %d faces found out of %d images.",
        len(face_filenames),
        len(image_paths),
    )
    return embeddings, face_filenames, face_flags
