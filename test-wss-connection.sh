#!/bin/bash

# Test WSS Connection Script
# This script tests the current backend connection status

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ORCHESTRATOR_IP="34.47.230.178"
MEDIA_SERVER_IP="35.244.8.62"
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

# Test HTTP connection
test_http_connection() {
    print_header "Testing HTTP Connection"
    
    # Test orchestrator health endpoint
    if curl -s "http://$ORCHESTRATOR_IP:8001/health" > /dev/null; then
        print_success "Orchestrator HTTP health endpoint is working"
    else
        print_error "Orchestrator HTTP health endpoint is not working"
    fi
    
    # Test media server health endpoint
    if curl -s "http://$MEDIA_SERVER_IP:8001/health" > /dev/null; then
        print_success "Media server HTTP health endpoint is working"
    else
        print_error "Media server HTTP health endpoint is not working"
    fi
}

# Test HTTPS connection
test_https_connection() {
    print_header "Testing HTTPS Connection"
    
    # Test orchestrator HTTPS health endpoint
    if curl -k -s "https://$ORCHESTRATOR_IP:8001/health" > /dev/null; then
        print_success "Orchestrator HTTPS health endpoint is working"
    else
        print_warning "Orchestrator HTTPS health endpoint is not working (expected if SSL not configured)"
    fi
    
    # Test media server HTTPS health endpoint
    if curl -k -s "https://$MEDIA_SERVER_IP:8001/health" > /dev/null; then
        print_success "Media server HTTPS health endpoint is working"
    else
        print_warning "Media server HTTPS health endpoint is not working (expected if SSL not configured)"
    fi
}

# Test WebSocket connection
test_websocket_connection() {
    print_header "Testing WebSocket Connection"
    
    # Test HTTP WebSocket upgrade
    if curl -s -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==" "http://$ORCHESTRATOR_IP:8001/ws" | grep -q "101 Switching Protocols"; then
        print_success "HTTP WebSocket upgrade is working"
    else
        print_error "HTTP WebSocket upgrade is not working"
    fi
    
    # Test HTTPS WebSocket upgrade
    if curl -k -s -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==" "https://$ORCHESTRATOR_IP:8001/ws" | grep -q "101 Switching Protocols"; then
        print_success "HTTPS WebSocket upgrade is working"
    else
        print_warning "HTTPS WebSocket upgrade is not working (expected if SSL not configured)"
    fi
}

# Test Kubernetes services
test_k8s_services() {
    print_header "Testing Kubernetes Services"
    
    if command -v kubectl &> /dev/null; then
        # Check if namespace exists
        if kubectl get namespace $NAMESPACE &> /dev/null; then
            print_success "Namespace $NAMESPACE exists"
            
            # Check orchestrator service
            if kubectl get service orchestrator -n $NAMESPACE &> /dev/null; then
                print_success "Orchestrator service exists"
                
                # Get service details
                ORCHESTRATOR_SERVICE_IP=$(kubectl get service orchestrator -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
                if [ -n "$ORCHESTRATOR_SERVICE_IP" ]; then
                    print_success "Orchestrator service IP: $ORCHESTRATOR_SERVICE_IP"
                else
                    print_warning "Orchestrator service IP not available"
                fi
            else
                print_error "Orchestrator service does not exist"
            fi
            
            # Check media server service
            if kubectl get service media-server -n $NAMESPACE &> /dev/null; then
                print_success "Media server service exists"
                
                # Get service details
                MEDIA_SERVER_SERVICE_IP=$(kubectl get service media-server -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
                if [ -n "$MEDIA_SERVER_SERVICE_IP" ]; then
                    print_success "Media server service IP: $MEDIA_SERVER_SERVICE_IP"
                else
                    print_warning "Media server service IP not available"
                fi
            else
                print_error "Media server service does not exist"
            fi
            
            # Check pod status
            print_header "Pod Status"
            kubectl get pods -n $NAMESPACE -l app=orchestrator
            kubectl get pods -n $NAMESPACE -l app=media-server
            
        else
            print_error "Namespace $NAMESPACE does not exist"
        fi
    else
        print_warning "kubectl not available, skipping Kubernetes tests"
    fi
}

# Test port connectivity
test_port_connectivity() {
    print_header "Testing Port Connectivity"
    
    # Test orchestrator ports
    if nc -z -w5 $ORCHESTRATOR_IP 8001; then
        print_success "Orchestrator port 8001 is open"
    else
        print_error "Orchestrator port 8001 is closed"
    fi
    
    if nc -z -w5 $ORCHESTRATOR_IP 8002; then
        print_success "Orchestrator port 8002 is open"
    else
        print_error "Orchestrator port 8002 is closed"
    fi
    
    # Test media server ports
    if nc -z -w5 $MEDIA_SERVER_IP 8001; then
        print_success "Media server port 8001 is open"
    else
        print_error "Media server port 8001 is closed"
    fi
}

# Main function
main() {
    print_header "WSS Connection Diagnostic Test"
    
    test_port_connectivity
    test_http_connection
    test_https_connection
    test_websocket_connection
    test_k8s_services
    
    print_header "Test Summary"
    echo "If HTTP WebSocket is working but HTTPS WebSocket is not,"
    echo "the backend needs to be updated with SSL support."
    echo ""
    echo "To fix WSS connection issues:"
    echo "1. Run: ./fix-wss-connection.sh"
    echo "2. Rebuild and redeploy the backend images"
    echo "3. Test the frontend connection again"
}

# Run main function
main "$@" 