#!/bin/bash

# Build script for simplified STT service
set -e

# Configuration
PROJECT_ID="speechtotext-466820"
REGION="asia-south1"
REGISTRY_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/voice-agent-repo"
IMAGE_NAME="stt-service"
VERSION="v1.0.5-simple"

echo "🚀 Building simplified STT service..."

# Navigate to STT service directory
cd stt-service

# Build for AMD64 platform (GKE requirement)
echo "🔨 Building simplified STT service for AMD64 platform..."
docker buildx build \
    --platform linux/amd64 \
    --file Dockerfile.simple \
    --tag "${REGISTRY_PATH}/${IMAGE_NAME}:${VERSION}" \
    --tag "${REGISTRY_PATH}/${IMAGE_NAME}:latest" \
    --push \
    .

echo "✅ Simplified STT service built and pushed successfully!"
echo "📦 Image: ${REGISTRY_PATH}/${IMAGE_NAME}:${VERSION}"

# Return to original directory
cd .. 