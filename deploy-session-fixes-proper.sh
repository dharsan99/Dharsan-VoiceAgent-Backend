#!/bin/bash

# Deploy Session ID Fixes - Proper Version
# This script deploys the updated orchestrator and media server with session ID fixes
# by building and pushing to the existing registry

set -e

echo "🚀 Deploying Session ID Fixes - Proper Version..."

# Check if we're in the right directory
if [ ! -f "v2/orchestrator/main.go" ]; then
    echo "❌ Error: Please run this script from the Dharsan-VoiceAgent-Backend directory"
    exit 1
fi

# Configuration
REGISTRY="asia-south1-docker.pkg.dev/speechtotext-466820/voice-agent-repo"
ORCHESTRATOR_IMAGE="$REGISTRY/orchestrator"
MEDIA_SERVER_IMAGE="$REGISTRY/media-server"
NEW_VERSION="v1.0.23"

echo "📦 Building updated images..."

# Build orchestrator
echo "Building orchestrator..."
cd v2/orchestrator
docker build -t $ORCHESTRATOR_IMAGE:$NEW_VERSION .
docker tag $ORCHESTRATOR_IMAGE:$NEW_VERSION $ORCHESTRATOR_IMAGE:latest
cd ../..

# Build media server
echo "Building media server..."
cd v2/media-server
docker build -t $MEDIA_SERVER_IMAGE:$NEW_VERSION .
docker tag $MEDIA_SERVER_IMAGE:$NEW_VERSION $MEDIA_SERVER_IMAGE:latest
cd ../..

echo "📤 Pushing images to registry..."

# Push orchestrator
echo "Pushing orchestrator image..."
docker push $ORCHESTRATOR_IMAGE:$NEW_VERSION
docker push $ORCHESTRATOR_IMAGE:latest

# Push media server
echo "Pushing media server image..."
docker push $MEDIA_SERVER_IMAGE:$NEW_VERSION
docker push $MEDIA_SERVER_IMAGE:latest

echo "🚀 Deploying updated services..."

# Update orchestrator deployment
echo "Updating orchestrator deployment..."
kubectl set image deployment/orchestrator orchestrator=$ORCHESTRATOR_IMAGE:$NEW_VERSION -n voice-agent-phase5

# Update media server deployment
echo "Updating media server deployment..."
kubectl set image deployment/media-server media-server=$MEDIA_SERVER_IMAGE:$NEW_VERSION -n voice-agent-phase5

echo "⏳ Waiting for deployments to roll out..."

# Wait for orchestrator rollout
echo "Waiting for orchestrator rollout..."
kubectl rollout status deployment/orchestrator -n voice-agent-phase5 --timeout=300s

# Wait for media server rollout
echo "Waiting for media server rollout..."
kubectl rollout status deployment/media-server -n voice-agent-phase5 --timeout=300s

echo "✅ Deployment completed successfully!"

# Clean up any failed session-fixes deployments
echo "🧹 Cleaning up failed session-fixes deployments..."
kubectl delete deployment orchestrator-session-fixes -n voice-agent-phase5 --ignore-not-found=true
kubectl delete deployment media-server-session-fixes -n voice-agent-phase5 --ignore-not-found=true

# Show final status
echo "📊 Final deployment status:"
kubectl get pods -n voice-agent-phase5

echo "🎉 Session ID fixes deployed successfully!"
echo "📝 Summary of fixes:"
echo "   - Improved session ID generation with crypto/rand"
echo "   - Enhanced session mapping logic"
echo "   - Better WebSocket session handling"
echo "   - Improved session ID validation"
echo "   - Added session confirmation messages" 