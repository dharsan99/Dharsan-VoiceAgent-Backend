#!/bin/bash

# GKE Resource Optimization Deployment Script
# This script deploys the optimized resource configurations to reduce costs by ~70%

set -e

echo "🚀 Starting GKE Resource Optimization Deployment"
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl is not installed or not in PATH"
    exit 1
fi

# Check if we're connected to the right cluster
print_status "Checking cluster connection..."
CURRENT_CONTEXT=$(kubectl config current-context)
print_status "Current context: $CURRENT_CONTEXT"

if [[ ! "$CURRENT_CONTEXT" == *"voice-agent"* ]]; then
    print_warning "Context doesn't contain 'voice-agent'. Are you sure this is the right cluster?"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check namespace exists
print_status "Checking namespace..."
if ! kubectl get namespace voice-agent-phase5 &> /dev/null; then
    print_error "Namespace 'voice-agent-phase5' not found"
    exit 1
fi

print_success "Namespace 'voice-agent-phase5' exists"

# Step 1: Create Persistent Volume Claims first
print_status "Step 1: Creating Persistent Volume Claims..."
echo "Creating PVCs for model storage..."

kubectl apply -f manifests/stt-service-deployment-optimized.yaml --dry-run=client
if [ $? -eq 0 ]; then
    kubectl apply -f manifests/stt-service-deployment-optimized.yaml
    print_success "STT PVC created"
else
    print_error "Failed to create STT PVC"
    exit 1
fi

kubectl apply -f manifests/llm-service-deployment-optimized.yaml --dry-run=client
if [ $? -eq 0 ]; then
    kubectl apply -f manifests/llm-service-deployment-optimized.yaml
    print_success "LLM PVC created"
else
    print_error "Failed to create LLM PVC"
    exit 1
fi

kubectl apply -f manifests/tts-service-deployment-optimized.yaml --dry-run=client
if [ $? -eq 0 ]; then
    kubectl apply -f manifests/tts-service-deployment-optimized.yaml
    print_success "TTS PVC created"
else
    print_error "Failed to create TTS PVC"
    exit 1
fi

# Wait for PVCs to be bound
print_status "Waiting for PVCs to be bound..."
kubectl wait --for=condition=Bound pvc/stt-model-storage-pvc -n voice-agent-phase5 --timeout=300s
kubectl wait --for=condition=Bound pvc/ollama-model-storage-pvc -n voice-agent-phase5 --timeout=300s
kubectl wait --for=condition=Bound pvc/tts-model-storage-pvc -n voice-agent-phase5 --timeout=300s

print_success "All PVCs are bound"

# Step 2: Deploy optimized services in order
print_status "Step 2: Deploying optimized services..."

# Deploy STT service first (most critical)
print_status "Deploying optimized STT service..."
kubectl apply -f manifests/stt-service-deployment-optimized.yaml
kubectl rollout status deployment/stt-service -n voice-agent-phase5 --timeout=600s
print_success "STT service deployed and ready"

# Deploy LLM service
print_status "Deploying optimized LLM service..."
kubectl apply -f manifests/llm-service-deployment-optimized.yaml
kubectl rollout status deployment/llm-service -n voice-agent-phase5 --timeout=900s
print_success "LLM service deployed and ready"

# Deploy TTS service
print_status "Deploying optimized TTS service..."
kubectl apply -f manifests/tts-service-deployment-optimized.yaml
kubectl rollout status deployment/tts-service -n voice-agent-phase5 --timeout=600s
print_success "TTS service deployed and ready"

# Deploy orchestrator
print_status "Deploying optimized orchestrator..."
kubectl apply -f manifests/orchestrator-deployment-optimized.yaml
kubectl rollout status deployment/orchestrator -n voice-agent-phase5 --timeout=300s
print_success "Orchestrator deployed and ready"

# Step 3: Verify deployments
print_status "Step 3: Verifying deployments..."

echo "Checking pod status..."
kubectl get pods -n voice-agent-phase5 -l app=stt-service
kubectl get pods -n voice-agent-phase5 -l app=llm-service
kubectl get pods -n voice-agent-phase5 -l app=tts-service
kubectl get pods -n voice-agent-phase5 -l app=orchestrator

echo "Checking HPA status..."
kubectl get hpa -n voice-agent-phase5

echo "Checking PVC status..."
kubectl get pvc -n voice-agent-phase5

# Step 4: Resource usage comparison
print_status "Step 4: Resource usage comparison..."

echo "Current resource requests:"
kubectl get pods -n voice-agent-phase5 -o custom-columns="NAME:.metadata.name,CPU_REQ:.spec.containers[0].resources.requests.cpu,MEM_REQ:.spec.containers[0].resources.requests.memory"

echo "Current resource usage:"
kubectl top pods -n voice-agent-phase5

# Step 5: Cost savings calculation
print_status "Step 5: Calculating cost savings..."

echo "Resource optimization summary:"
echo "=============================="
echo "Before optimization:"
echo "  - STT: 2 cores CPU, 2Gi memory"
echo "  - LLM: 500m CPU, 1Gi memory"
echo "  - TTS: 100m CPU, 256Mi memory"
echo "  - Orchestrator: 200m CPU, 512Mi memory"
echo ""
echo "After optimization:"
echo "  - STT: 250m CPU, 512Mi memory (87.5% reduction)"
echo "  - LLM: 200m CPU, 512Mi memory (60% reduction)"
echo "  - TTS: 100m CPU, 256Mi memory (no change needed)"
echo "  - Orchestrator: 100m CPU, 256Mi memory (50% reduction)"
echo ""
echo "Expected cost savings: ~70% reduction in resource costs"

print_success "GKE Resource Optimization Deployment Complete!"
echo ""
echo "Next steps:"
echo "1. Monitor resource usage with: kubectl top pods -n voice-agent-phase5"
echo "2. Check HPA scaling with: kubectl get hpa -n voice-agent-phase5"
echo "3. Monitor costs in GCP Console"
echo "4. Test application functionality"
echo ""
echo "If issues arise, you can rollback with:"
echo "kubectl rollout undo deployment/[service-name] -n voice-agent-phase5" 