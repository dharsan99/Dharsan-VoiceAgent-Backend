#!/bin/bash

# Voice AI Backend v2 - Kubernetes Deployment Script
# This script deploys the WebRTC backend to a Kubernetes cluster

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="voice-ai"
IMAGE_NAME="voice-ai-backend-v2"
IMAGE_TAG="latest"
PROJECT_ID=$(gcloud config get-value project)
REGISTRY="gcr.io/${PROJECT_ID}"  # Google Container Registry

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

# Function to check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    print_success "Kubectl is available and connected to cluster"
}

# Function to build and push Docker image
build_image() {
    print_status "Building Docker image..."
    
    # Build the image
    docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
    
    if [ ! -z "$REGISTRY" ]; then
        # Tag for registry
        docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}
        
        print_status "Pushing image to registry..."
        docker push ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}
        
        # Update deployment to use registry image
        sed -i.bak "s|image: ${IMAGE_NAME}:${IMAGE_TAG}|image: ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}|g" k8s-deployment.yaml
    fi
    
    print_success "Docker image built successfully"
}

# Function to create namespace
create_namespace() {
    print_status "Creating namespace: $NAMESPACE"
    
    kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
    
    print_success "Namespace created/updated"
}

# Function to apply Kubernetes manifests
apply_manifests() {
    print_status "Applying Kubernetes manifests..."
    
    # Apply Redis first
    kubectl apply -f k8s-redis.yaml
    
    # Wait for Redis to be ready
    print_status "Waiting for Redis to be ready..."
    kubectl wait --for=condition=available --timeout=120s deployment/redis -n redis
    
    # Apply secrets and configmaps first
    kubectl apply -f k8s-secrets.yaml -n $NAMESPACE
    
    # Apply system tuning DaemonSet
    kubectl apply -f sysctl-tuning-daemonset.yaml -n $NAMESPACE
    
    # Apply deployment
    kubectl apply -f k8s-deployment.yaml -n $NAMESPACE
    
    # Apply services
    kubectl apply -f k8s-service.yaml -n $NAMESPACE
    
    print_success "Kubernetes manifests applied successfully"
}

# Function to wait for deployment
wait_for_deployment() {
    print_status "Waiting for deployment to be ready..."
    
    kubectl wait --for=condition=available --timeout=300s deployment/voice-ai-backend-v2 -n $NAMESPACE
    
    print_success "Deployment is ready"
}

# Function to get service information
get_service_info() {
    print_status "Getting service information..."
    
    # Get external IP (if using LoadBalancer)
    EXTERNAL_IP=$(kubectl get service voice-ai-backend-v2-service -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "Pending")
    
    if [ "$EXTERNAL_IP" != "Pending" ]; then
        print_success "External IP: $EXTERNAL_IP"
        print_status "WebRTC Backend URL: http://$EXTERNAL_IP"
        print_status "WebSocket URL: ws://$EXTERNAL_IP/ws/v2/{session_id}"
    else
        print_warning "External IP is pending. Check with: kubectl get service voice-ai-backend-v2-service -n $NAMESPACE"
    fi
    
    # Get pod information
    print_status "Pod status:"
    kubectl get pods -n $NAMESPACE -l app=voice-ai-backend-v2
}

# Function to show logs
show_logs() {
    print_status "Showing logs for the latest pod..."
    
    POD_NAME=$(kubectl get pods -n $NAMESPACE -l app=voice-ai-backend-v2 -o jsonpath='{.items[0].metadata.name}')
    kubectl logs -f $POD_NAME -n $NAMESPACE
}

# Function to run health checks
health_check() {
    print_status "Running health checks..."
    
    # Get service URL
    SERVICE_URL=$(kubectl get service voice-ai-backend-v2-service -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "localhost")
    
    if [ "$SERVICE_URL" = "localhost" ]; then
        print_warning "Using port-forward for health check..."
        kubectl port-forward service/voice-ai-backend-v2-service 8000:80 -n $NAMESPACE &
        PF_PID=$!
        sleep 5
        SERVICE_URL="localhost:8000"
    fi
    
    # Test health endpoint
    if curl -f "http://$SERVICE_URL/health" > /dev/null 2>&1; then
        print_success "Health check passed"
    else
        print_error "Health check failed"
    fi
    
    # Cleanup port-forward if we started it
    if [ ! -z "$PF_PID" ]; then
        kill $PF_PID 2>/dev/null || true
    fi
}

# Main deployment function
deploy() {
    print_status "Starting Voice AI Backend v2 deployment..."
    
    check_kubectl
    build_image
    create_namespace
    apply_manifests
    wait_for_deployment
    get_service_info
    health_check
    
    print_success "Deployment completed successfully!"
    print_status "You can now access the WebRTC backend at the provided URLs"
}

# Function to clean up
cleanup() {
    print_status "Cleaning up deployment..."
    
    kubectl delete -f k8s-service.yaml -n $NAMESPACE --ignore-not-found
    kubectl delete -f k8s-deployment.yaml -n $NAMESPACE --ignore-not-found
    kubectl delete -f sysctl-tuning-daemonset.yaml -n $NAMESPACE --ignore-not-found
    kubectl delete -f k8s-secrets.yaml -n $NAMESPACE --ignore-not-found
    
    print_success "Cleanup completed"
}

# Function to show usage
usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy     Deploy the Voice AI Backend v2 to Kubernetes"
    echo "  cleanup    Remove the deployment from Kubernetes"
    echo "  logs       Show logs from the running pods"
    echo "  status     Show deployment status"
    echo "  health     Run health checks"
    echo "  help       Show this help message"
}

# Main script logic
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    cleanup)
        cleanup
        ;;
    logs)
        show_logs
        ;;
    status)
        kubectl get all -n $NAMESPACE -l app=voice-ai-backend-v2
        ;;
    health)
        health_check
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        print_error "Unknown command: $1"
        usage
        exit 1
        ;;
esac 