#!/bin/bash

# Build and Deploy Secure Images
# This script builds and deploys the updated orchestrator and media server with HTTPS/WSS support

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGISTRY="asia-south1-docker.pkg.dev/speechtotext-466820/voice-agent-repo"
ORCHESTRATOR_VERSION="v1.0.28"
MEDIA_SERVER_VERSION="v1.0.30"
NAMESPACE="voice-agent-phase5"

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    if ! command -v docker &> /dev/null; then
        print_error "docker is not installed"
        exit 1
    fi
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "docker is not running"
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Build orchestrator image
build_orchestrator() {
    print_header "Building Orchestrator Image"
    
    cd orchestrator
    
    # Build the image for Linux/amd64 platform
    docker build --platform linux/amd64 -t $REGISTRY/orchestrator:$ORCHESTRATOR_VERSION .
    
    if [ $? -eq 0 ]; then
        print_success "Orchestrator image built successfully"
    else
        print_error "Failed to build orchestrator image"
        exit 1
    fi
    
    cd ..
}

# Build media server image
build_media_server() {
    print_header "Building Media Server Image"
    
    cd media-server
    
    # Build the image for Linux/amd64 platform
    docker build --platform linux/amd64 -t $REGISTRY/media-server:$MEDIA_SERVER_VERSION .
    
    if [ $? -eq 0 ]; then
        print_success "Media server image built successfully"
    else
        print_error "Failed to build media server image"
        exit 1
    fi
    
    cd ..
}

# Push images to registry
push_images() {
    print_header "Pushing Images to Registry"
    
    # Push orchestrator
    docker push $REGISTRY/orchestrator:$ORCHESTRATOR_VERSION
    
    if [ $? -eq 0 ]; then
        print_success "Orchestrator image pushed successfully"
    else
        print_error "Failed to push orchestrator image"
        exit 1
    fi
    
    # Push media server
    docker push $REGISTRY/media-server:$MEDIA_SERVER_VERSION
    
    if [ $? -eq 0 ]; then
        print_success "Media server image pushed successfully"
    else
        print_error "Failed to push media server image"
        exit 1
    fi
}

# Update deployments with new images
update_deployments() {
    print_header "Updating Deployments with New Images"
    
    # Update orchestrator image
    kubectl set image deployment/orchestrator orchestrator=$REGISTRY/orchestrator:$ORCHESTRATOR_VERSION -n $NAMESPACE
    
    if [ $? -eq 0 ]; then
        print_success "Orchestrator deployment updated"
    else
        print_error "Failed to update orchestrator deployment"
        exit 1
    fi
    
    # Update media server image
    kubectl set image deployment/media-server media-server=$REGISTRY/media-server:$MEDIA_SERVER_VERSION -n $NAMESPACE
    
    if [ $? -eq 0 ]; then
        print_success "Media server deployment updated"
    else
        print_error "Failed to update media server deployment"
        exit 1
    fi
}

# Wait for deployments to be ready
wait_for_deployments() {
    print_header "Waiting for Deployments to be Ready"
    
    kubectl rollout status deployment orchestrator -n $NAMESPACE --timeout=300s
    kubectl rollout status deployment media-server -n $NAMESPACE --timeout=300s
    
    print_success "All deployments are ready"
}

# Test the deployment
test_deployment() {
    print_header "Testing Deployment"
    
    # Wait a bit for services to be ready
    sleep 30
    
    # Get service IPs
    ORCHESTRATOR_IP=$(kubectl get service orchestrator-lb -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
    MEDIA_SERVER_IP=$(kubectl get service media-server -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
    
    if [ -n "$ORCHESTRATOR_IP" ]; then
        print_success "Orchestrator IP: $ORCHESTRATOR_IP"
        
        # Test HTTP health endpoint
        if curl -s "http://$ORCHESTRATOR_IP:8001/health" > /dev/null; then
            print_success "Orchestrator HTTP health endpoint is working"
        else
            print_warning "Orchestrator HTTP health endpoint test failed"
        fi
        
        # Test HTTPS health endpoint
        if curl -k -s "https://$ORCHESTRATOR_IP:8001/health" > /dev/null; then
            print_success "Orchestrator HTTPS health endpoint is working"
        else
            print_warning "Orchestrator HTTPS health endpoint test failed"
        fi
        
        # Test WebSocket upgrade
        if curl -k -s -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==" "https://$ORCHESTRATOR_IP:8001/ws" | grep -q "101 Switching Protocols"; then
            print_success "Orchestrator HTTPS WebSocket upgrade is working"
        else
            print_warning "Orchestrator HTTPS WebSocket upgrade test failed"
        fi
    else
        print_warning "Orchestrator IP not available yet"
    fi
    
    if [ -n "$MEDIA_SERVER_IP" ]; then
        print_success "Media server IP: $MEDIA_SERVER_IP"
        
        # Test HTTP health endpoint
        if curl -s "http://$MEDIA_SERVER_IP:8001/health" > /dev/null; then
            print_success "Media server HTTP health endpoint is working"
        else
            print_warning "Media server HTTP health endpoint test failed"
        fi
        
        # Test HTTPS health endpoint
        if curl -k -s "https://$MEDIA_SERVER_IP:443/health" > /dev/null; then
            print_success "Media server HTTPS health endpoint is working"
        else
            print_warning "Media server HTTPS health endpoint test failed"
        fi
    else
        print_warning "Media server IP not available yet"
    fi
}

# Main function
main() {
    print_header "Building and Deploying Secure Images"
    
    check_prerequisites
    build_orchestrator
    build_media_server
    push_images
    update_deployments
    wait_for_deployments
    test_deployment
    
    print_header "Build and Deploy Complete"
    print_success "Secure images built and deployed successfully"
    echo ""
    echo "Next steps:"
    echo "1. Test the frontend connection with WSS"
    echo "2. Monitor the logs for any issues"
    echo "3. Verify all functionality is working"
}

# Run main function
main "$@" 