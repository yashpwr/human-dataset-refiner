import os
import sys
from pathlib import Path

# Add project root to path so we can import app.config
sys.path.append(str(Path(__file__).parent.parent))

from app.config import get_settings

def download_models():
    settings = get_settings()
    # Use environment variables if set, otherwise fallback to settings
    models_dir = Path(os.getenv("REFINER_MODELS_ROOT", str(settings.MODELS_DIR)))
    models_dir.mkdir(parents=True, exist_ok=True)

    # Set environment variables for downloaders
    os.environ["HF_HOME"] = str(models_dir / "huggingface")
    os.environ["INSIGHTFACE_HOME"] = str(models_dir / "insightface")

    print(f"HF_HOME set to: {os.environ['HF_HOME']}")
    print(f"INSIGHTFACE_HOME set to: {os.environ['INSIGHTFACE_HOME']}")

    # 1. Download open_clip model
    import open_clip
    print(f"Downloading CLIP model: {settings.CLIP_MODEL_NAME} ({settings.CLIP_PRETRAINED}) ...")
    open_clip.create_model_and_transforms(
        settings.CLIP_MODEL_NAME,
        pretrained=settings.CLIP_PRETRAINED,
        device="cpu"
    )

    # 2. Download InsightFace models
    from insightface.app import FaceAnalysis
    print(f"Downloading InsightFace model: {settings.INSIGHTFACE_MODEL} ...")
    app = FaceAnalysis(name=settings.INSIGHTFACE_MODEL, root=str(models_dir / "insightface"))
    app.prepare(ctx_id=-1) # CPU

    print("Model downloads complete.")

if __name__ == "__main__":
    download_models()
