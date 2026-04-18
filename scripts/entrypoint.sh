#!/bin/bash
set -e

# Target directory on the host (mapped via volume)
TARGET_DIR="/app/models"
BAKED_DIR="/models_baked"

echo "Checking models in $TARGET_DIR..."

# If the target directory is empty, seed it from baked image models
if [ ! -d "$TARGET_DIR/huggingface" ]; then
    echo "Local models folder not found. Seeding from baked image models (this is instant)..."
    mkdir -p "$TARGET_DIR"
    cp -rp $BAKED_DIR/* "$TARGET_DIR/"
    echo "Seeding complete. Models are now in your local project directory."
else
    echo "Local models present. Ready to go."
fi

# Set runtime ENVs to use the localized models directory (the one mapped to the host)
export HF_HOME="$TARGET_DIR/huggingface"
export HUGGINGFACE_HUB_CACHE="$TARGET_DIR/huggingface"
export INSIGHTFACE_HOME="$TARGET_DIR/insightface"
export TORCH_HOME="$TARGET_DIR/torch"
export REFINER_MODELS_ROOT="$TARGET_DIR"

# Execute the main application
echo "Starting application..."
exec "$@"
