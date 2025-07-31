#!/bin/bash

# Build script for orchestrator only
set -e

# Configuration
PROJECT_ID="speechtotext-466820"
REGION="us-central1"
REGISTRY_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/voice-agent-repo"
IMAGE_NAME="orchestrator"
VERSION="v2.0.1"

echo "🚀 Building orchestrator..."

# Navigate to orchestrator directory
cd orchestrator

# Build for AMD64 platform (GKE requirement)
echo "🔨 Building orchestrator for AMD64 platform..."
docker buildx build \
    --platform linux/amd64 \
    --tag "${REGISTRY_PATH}/${IMAGE_NAME}:${VERSION}" \
    --tag "${REGISTRY_PATH}/${IMAGE_NAME}:latest" \
    --push \
    .

echo "✅ Orchestrator built and pushed successfully!"
echo "📦 Image: ${REGISTRY_PATH}/${IMAGE_NAME}:${VERSION}"

# Return to original directory
cd .. 