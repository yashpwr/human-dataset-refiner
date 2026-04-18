# Human Dataset Refiner v2.0.0

[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2+-61DAFB.svg)](https://react.dev/)

> A professional-grade, AI-powered toolkit for refining, cleaning, and clustering massive human face datasets. Designed for high-quality LoRA, DreamBooth, and fine-tuning identity training.

---

## 🚀 Core Architecture: Datasets & Jobs

The Refiner v2.0.0 utilizes a decoupled architecture to separate source data from processing runs.

- **Datasets**: Independent collections of raw images. Manage your "library" of source content without worrying about specific refinement parameters. Supports batch image uploads and ZIP file ingestion.
- **Jobs**: Specific refinement pipelines. Link a dataset to a job, configure your thresholds, and run the cleaning process. Jobs maintain their own unique results, metadata, and identity groupings.

---

## 🧠 AI-Powered Pipeline

Every job executes a multi-stage refinement pipeline:

### 1. Quality Assessment
Uses **OpenCV Laplacian Variance** to calculate image sharpness and **Pillow** for resolution/corruption checks.
- **Blur Filter**: Automatically rejects out-of-focus images.
- **Resolution Filter**: Ensures training data meets your minimum resolution requirements (e.g., 512x512).

### 2. Neural Duplicate Detection
Uses **64-bit Perceptual Hashing (pHash)** with a tunable Hamming distance. 
- Automatically identifies identical or near-identical images.
- Intelligently keeps the highest-resolution/highest-quality version of a duplicate set.

### 3. Identity Clustering (InsightFace)
Leverages the **buffalo_l** ArcFace architecture for high-precision face recognition.
- Extracts identity-specific embeddings.
- Groups images by *person identity*, separating different individuals into distinct folders even across pose/lighting variations.

### 4. Visual Similarity Fallback (CLIP)
Uses **OpenAI's CLIP (ViT-B/32 via open-clip)** to handle images where no face is detected.
- Performs global visual similarity clustering.
- Ensures consistent "vibe" or style grouping for accessory/unclear shots.

---

## 🛠 Technical Tech Stack

### Backend
- **FastAPI**: Asynchronous Python API and Job Orchestrator.
- **SQLite**: Local persistence for Job/Dataset state and relationship integrity.
- **InsightFace**: Identity extraction (ArcFace).
- **open_clip**: Multi-modal visual embedding extraction.
- **HDBSCAN**: Density-based clustering for automatic group size detection.

### Frontend
- **React (Vite)**: High-performance modern UI.
- **Tailwind-free CSS**: Custom sleek aesthetics with glassmorphism and dark mode.
- **Lucide-React**: Modern iconography system.
- **HMR Enabled**: Ready for development with hot-reloading in Docker.

---

## 📦 Docker & Deployment

The application is fully containerized and includes a **Model Baking** stage to ensure it's ready for immediate use.

### Model Baking (Pre-download)
During the initial Docker build, the following models are fetched and baked into the image's `/models` directory:
- `CLIP-ViT-B-32-laion2B-s34B-b79K`
- `InsightFace buffalo_l` pack

### Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone <repo-url> human-dataset-refiner
   cd human-dataset-refiner
   ```

2. **Spin up the stack**:
   ```bash
   docker compose up --build
   ```

3. **GPU Support (Optional)**:
   Ensure NVIDIA Container Toolkit is installed, then run:
   ```bash
   docker compose --profile gpu up --build
   ```

The dashboard will be available at: **http://localhost:3000**
The API docs will be available at: **http://localhost:8000/docs**

---

## 📂 Data Topology

All runtime data is strictly localized within the `data/` directory (ignored by git):

```bash
data/
├── datasets/            # Raw source collections
│   └── raw_faces_01/
├── jobs/                # Processed runs
│   └── ranveer_job/
│       ├── embeddings/  # CLIP & Face cached vectors
│       ├── metadata/    # image_metadata.csv & reports
│       ├── grouped/     # Final identity-based folders
│       └── removed/     # Quality rejected / Duplicates
├── refiner.db           # State persistence
└── models/              # Optional host-side model cache
```

---

## ⚙️ Configuration (Environment Variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `REFINER_BLUR_THRESHOLD` | `35.0` | Sharpness cutoff (higher = stricter) |
| `REFINER_MIN_RESOLUTION` | `64` | Reject images smaller than this px |
| `REFINER_FACE_DISTANCE_THRESHOLD` | `0.55` | Identity strictness (lower = stricter) |
| `REFINER_MODELS_ROOT` | `/models` | Internal model path (baked-in) |

---

## 📝 License
MIT
