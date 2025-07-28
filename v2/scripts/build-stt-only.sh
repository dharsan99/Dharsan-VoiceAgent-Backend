#!/bin/bash

# Build and push STT service only
set -e

# Configuration
PROJECT_ID="speechtotext-466820"
REGION="asia-south1"
REGISTRY_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/voice-agent-repo"
IMAGE_NAME="stt-service"
VERSION="v1.0.4"

echo "🚀 Building and pushing STT service only..."
echo "Project: $PROJECT_ID"
echo "Registry: $REGISTRY_PATH"
echo "Image: $IMAGE_NAME:$VERSION"

# Configure Docker for Artifact Registry
echo "📋 Configuring Docker authentication..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev"

# Build for AMD64 platform (GKE requirement)
echo "🔨 Building STT service for AMD64 platform..."
       cd stt-service

# Use buildx to build for AMD64
docker buildx build \
    --platform linux/amd64 \
    --push \
    -t "${REGISTRY_PATH}/${IMAGE_NAME}:${VERSION}" \
    .

echo "✅ STT service built and pushed successfully!"
echo "Image: ${REGISTRY_PATH}/${IMAGE_NAME}:${VERSION}"

# Update the deployment file
echo "📝 Updating deployment configuration..."
cd ../..
sed -i.bak "s|image:.*stt-service.*|image: ${REGISTRY_PATH}/${IMAGE_NAME}:${VERSION}|g" v2/k8s/phase5/manifests/stt-service-deployment.yaml

echo "✅ Deployment configuration updated!"
echo "Ready to deploy with: kubectl apply -f v2/k8s/phase5/manifests/stt-service-deployment.yaml" 