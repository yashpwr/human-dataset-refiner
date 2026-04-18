import os
import sys
from pathlib import Path

# Add project root to path so we can import app.config
sys.path.append(str(Path(__file__).parent.parent))

from app.config import get_settings

def download_models():
    settings = get_settings()
    # If REFINER_MODELS_ROOT is set (during build), use it. Otherwise use settings.
    models_dir = Path(os.getenv("REFINER_MODELS_ROOT", str(settings.MODELS_DIR)))
    models_dir.mkdir(parents=True, exist_ok=True)

    # Set environment variables for downloaders
    hf_dir = models_dir / "huggingface"
    iface_dir = models_dir / "insightface"

    hf_dir.mkdir(parents=True, exist_ok=True)
    iface_dir.mkdir(parents=True, exist_ok=True)

    os.environ["HF_HOME"] = str(hf_dir)
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(hf_dir)
    os.environ["INSIGHTFACE_HOME"] = str(iface_dir)

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

    # Verification
    def get_size(p):
        return sum(f.stat().st_size for f in Path(p).rglob('*') if f.is_file()) / (1024*1024)

    print(f"HuggingFace cache size: {get_size(hf_dir):.2f} MB")
    print(f"InsightFace cache size: {get_size(iface_dir):.2f} MB")

    total_size = get_size(models_dir)
    print(f"Total models size: {total_size:.2f} MB")
    
    if total_size < 1000:
        print("ERROR: Models directory is suspiciously small. Download might have failed.")
        sys.exit(1)

if __name__ == "__main__":
    download_models()
