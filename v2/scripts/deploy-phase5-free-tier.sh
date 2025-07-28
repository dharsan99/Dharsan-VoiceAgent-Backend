#!/bin/bash

# Phase 5: Cost-Free Voice Agent Deployment
# Deploy to GKE Autopilot with tiny LLM (phi-3-mini) to stay within free tier

set -e

# Configuration
PROJECT_ID="speechtotext-466820"
REGION="asia-south1"
CLUSTER_NAME="voice-agent-free"
NAMESPACE="voice-agent-phase5"

echo "🚀 Starting Phase 5: Cost-Free Voice Agent Deployment"
echo "=================================================="
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Cluster: $CLUSTER_NAME"
echo "Namespace: $NAMESPACE"
echo ""

# Step 1: Set up GCP configuration
echo "🔧 Setting up GCP configuration..."
gcloud config set project $PROJECT_ID
gcloud config set compute/region $REGION

# Step 2: Create GKE Autopilot cluster (if not exists)
echo "🏗️  Creating GKE Autopilot cluster..."
if ! gcloud container clusters describe $CLUSTER_NAME --region=$REGION >/dev/null 2>&1; then
    echo "Creating new Autopilot cluster: $CLUSTER_NAME"
    gcloud container clusters create-auto $CLUSTER_NAME \
        --region=$REGION \
        --project=$PROJECT_ID
else
    echo "Cluster $CLUSTER_NAME already exists"
fi

# Step 3: Get cluster credentials
echo "🔑 Getting cluster credentials..."
gcloud container clusters get-credentials $CLUSTER_NAME --region=$REGION

# Step 4: Create namespace
echo "📁 Creating namespace..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Step 5: Deploy core services
echo "🚀 Deploying core services..."

# Deploy Redpanda first (message bus)
echo "📨 Deploying Redpanda..."
kubectl apply -f k8s/phase5/manifests/redpanda-deployment.yaml

# Wait for Redpanda to be ready
echo "⏳ Waiting for Redpanda to be ready..."
kubectl wait --for=condition=ready pod -l app=redpanda -n $NAMESPACE --timeout=300s

# Create Kafka topics
echo "📝 Creating Kafka topics..."
kubectl run kafka-topics --image=redpandadata/redpanda:latest --rm -it --restart=Never \
    -- rpk topic create audio-in --brokers redpanda.$NAMESPACE.svc.cluster.local:9092 || true
kubectl run kafka-topics --image=redpandadata/redpanda:latest --rm -it --restart=Never \
    -- rpk topic create audio-out --brokers redpanda.$NAMESPACE.svc.cluster.local:9092 || true

# Deploy AI services
echo "🤖 Deploying AI services..."
kubectl apply -f k8s/phase5/manifests/stt-service-deployment.yaml
kubectl apply -f k8s/phase5/manifests/tts-service-deployment.yaml

# Deploy LLM service (tiny model)
echo "🧠 Deploying LLM service with phi-3-mini..."
kubectl apply -f k8s/phase5/manifests/llm-service-deployment.yaml

# Deploy core infrastructure
echo "🏗️  Deploying core infrastructure..."
kubectl apply -f k8s/phase5/manifests/orchestrator-deployment.yaml
kubectl apply -f k8s/phase5/manifests/media-server-deployment.yaml

# Step 6: Wait for all services to be ready
echo "⏳ Waiting for all services to be ready..."
kubectl wait --for=condition=ready pod -l app=stt-service -n $NAMESPACE --timeout=300s
kubectl wait --for=condition=ready pod -l app=tts-service -n $NAMESPACE --timeout=300s
kubectl wait --for=condition=ready pod -l app=orchestrator -n $NAMESPACE --timeout=300s
kubectl wait --for=condition=ready pod -l app=media-server -n $NAMESPACE --timeout=300s

# Note: LLM service may take longer due to model download
echo "⏳ LLM service is downloading phi-3-mini model (this may take 5-10 minutes)..."

# Step 7: Get service URLs
echo "🌐 Getting service URLs..."
MEDIA_SERVER_IP=$(kubectl get svc media-server -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "Pending")
ORCHESTRATOR_IP=$(kubectl get svc orchestrator-lb -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "Pending")

echo ""
echo "🎉 Phase 5 Deployment Complete!"
echo "================================"
echo "Namespace: $NAMESPACE"
echo "Media Server: $MEDIA_SERVER_IP"
echo "Orchestrator: $ORCHESTRATOR_IP"
echo ""
echo "📊 Service Status:"
kubectl get pods -n $NAMESPACE
echo ""
echo "🔍 To check LLM service status:"
echo "kubectl logs -f deployment/llm-service -n $NAMESPACE"
echo ""
echo "🧪 To test the deployment:"
echo "kubectl get svc -n $NAMESPACE"
echo ""
echo "✅ Phase 5 deployment completed successfully!" 