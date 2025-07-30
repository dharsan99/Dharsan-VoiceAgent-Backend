#!/bin/bash

# Update Deployments with Security Configuration
# This script updates existing deployments with security configurations

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Create SSL certificates
create_ssl_certificates() {
    print_header "Creating SSL Certificates"
    
    # Create certificates directory
    mkdir -p certs
    
    # Generate self-signed certificate
    openssl req -x509 -newkey rsa:4096 -keyout certs/server.key -out certs/server.crt -days 365 -nodes \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=34.47.230.178"
    
    # Create Kubernetes secret
    kubectl create secret tls voice-agent-tls \
        --cert=certs/server.crt \
        --key=certs/server.key \
        --namespace=$NAMESPACE \
        --dry-run=client -o yaml | kubectl apply -f -
    
    print_success "SSL certificates created"
}

# Update orchestrator deployment with security
update_orchestrator_deployment() {
    print_header "Updating Orchestrator Deployment with Security"
    
    # Patch the orchestrator deployment to add HTTPS environment variables
    kubectl patch deployment orchestrator -n $NAMESPACE --type='json' -p='[
        {
            "op": "add",
            "path": "/spec/template/spec/containers/0/env/-",
            "value": {
                "name": "ENVIRONMENT",
                "value": "production"
            }
        },
        {
            "op": "add",
            "path": "/spec/template/spec/containers/0/env/-",
            "value": {
                "name": "CORS_ALLOWED_ORIGINS",
                "value": "https://dharsan-voice-agent-frontend.vercel.app,https://voice-agent-frontend.vercel.app"
            }
        },
        {
            "op": "add",
            "path": "/spec/template/spec/containers/0/env/-",
            "value": {
                "name": "ENABLE_HTTPS",
                "value": "true"
            }
        },
        {
            "op": "add",
            "path": "/spec/template/spec/containers/0/env/-",
            "value": {
                "name": "SSL_CERT_PATH",
                "value": "/etc/ssl/certs/server.crt"
            }
        },
        {
            "op": "add",
            "path": "/spec/template/spec/containers/0/env/-",
            "value": {
                "name": "SSL_KEY_PATH",
                "value": "/etc/ssl/private/server.key"
            }
        }
    ]'
    
    # Add volume mounts for SSL certificates
    kubectl patch deployment orchestrator -n $NAMESPACE --type='json' -p='[
        {
            "op": "add",
            "path": "/spec/template/spec/containers/0/volumeMounts",
            "value": [
                {
                    "name": "ssl-certs",
                    "mountPath": "/etc/ssl/certs",
                    "readOnly": true
                },
                {
                    "name": "ssl-keys",
                    "mountPath": "/etc/ssl/private",
                    "readOnly": true
                }
            ]
        },
        {
            "op": "add",
            "path": "/spec/template/spec/volumes",
            "value": [
                {
                    "name": "ssl-certs",
                    "secret": {
                        "secretName": "voice-agent-tls",
                        "items": [
                            {
                                "key": "tls.crt",
                                "path": "server.crt"
                            }
                        ]
                    }
                },
                {
                    "name": "ssl-keys",
                    "secret": {
                        "secretName": "voice-agent-tls",
                        "items": [
                            {
                                "key": "tls.key",
                                "path": "server.key"
                            }
                        ]
                    }
                }
            ]
        }
    ]'
    
    print_success "Orchestrator deployment updated with security"
}

# Update media server deployment with security
update_media_server_deployment() {
    print_header "Updating Media Server Deployment with Security"
    
    # Patch the media server deployment to add HTTPS environment variables
    kubectl patch deployment media-server -n $NAMESPACE --type='json' -p='[
        {
            "op": "add",
            "path": "/spec/template/spec/containers/0/env/-",
            "value": {
                "name": "ENVIRONMENT",
                "value": "production"
            }
        },
        {
            "op": "add",
            "path": "/spec/template/spec/containers/0/env/-",
            "value": {
                "name": "CORS_ALLOWED_ORIGINS",
                "value": "https://dharsan-voice-agent-frontend.vercel.app,https://voice-agent-frontend.vercel.app"
            }
        },
        {
            "op": "add",
            "path": "/spec/template/spec/containers/0/env/-",
            "value": {
                "name": "ENABLE_HTTPS",
                "value": "true"
            }
        },
        {
            "op": "add",
            "path": "/spec/template/spec/containers/0/env/-",
            "value": {
                "name": "SSL_CERT_PATH",
                "value": "/etc/ssl/certs/server.crt"
            }
        },
        {
            "op": "add",
            "path": "/spec/template/spec/containers/0/env/-",
            "value": {
                "name": "SSL_KEY_PATH",
                "value": "/etc/ssl/private/server.key"
            }
        }
    ]'
    
    # Add volume mounts for SSL certificates
    kubectl patch deployment media-server -n $NAMESPACE --type='json' -p='[
        {
            "op": "add",
            "path": "/spec/template/spec/containers/0/volumeMounts",
            "value": [
                {
                    "name": "ssl-certs",
                    "mountPath": "/etc/ssl/certs",
                    "readOnly": true
                },
                {
                    "name": "ssl-keys",
                    "mountPath": "/etc/ssl/private",
                    "readOnly": true
                }
            ]
        },
        {
            "op": "add",
            "path": "/spec/template/spec/volumes",
            "value": [
                {
                    "name": "ssl-certs",
                    "secret": {
                        "secretName": "voice-agent-tls",
                        "items": [
                            {
                                "key": "tls.crt",
                                "path": "server.crt"
                            }
                        ]
                    }
                },
                {
                    "name": "ssl-keys",
                    "secret": {
                        "secretName": "voice-agent-tls",
                        "items": [
                            {
                                "key": "tls.key",
                                "path": "server.key"
                            }
                        ]
                    }
                }
            ]
        }
    ]'
    
    print_success "Media server deployment updated with security"
}

# Restart deployments
restart_deployments() {
    print_header "Restarting Deployments"
    
    # Restart orchestrator
    kubectl rollout restart deployment orchestrator -n $NAMESPACE
    print_success "Orchestrator restart initiated"
    
    # Restart media server
    kubectl rollout restart deployment media-server -n $NAMESPACE
    print_success "Media server restart initiated"
    
    # Wait for rollouts to complete
    print_header "Waiting for rollouts to complete"
    kubectl rollout status deployment orchestrator -n $NAMESPACE --timeout=300s
    kubectl rollout status deployment media-server -n $NAMESPACE --timeout=300s
    
    print_success "All deployments restarted successfully"
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
        
        # Test HTTPS health endpoint (will fail until code is updated)
        if curl -k -s "https://$ORCHESTRATOR_IP:8001/health" > /dev/null; then
            print_success "Orchestrator HTTPS health endpoint is working"
        else
            print_warning "Orchestrator HTTPS health endpoint test failed (expected until code is updated)"
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
        
        # Test HTTPS health endpoint (will fail until code is updated)
        if curl -k -s "https://$MEDIA_SERVER_IP:443/health" > /dev/null; then
            print_success "Media server HTTPS health endpoint is working"
        else
            print_warning "Media server HTTPS health endpoint test failed (expected until code is updated)"
        fi
    else
        print_warning "Media server IP not available yet"
    fi
}

# Main function
main() {
    print_header "Updating Deployments with Security Configuration"
    
    check_prerequisites
    create_ssl_certificates
    update_orchestrator_deployment
    update_media_server_deployment
    restart_deployments
    test_deployment
    
    print_header "Update Complete"
    print_success "Deployments updated with security configuration"
    print_warning "Note: HTTPS/WSS will not work until the code is updated and images are rebuilt"
    echo ""
    echo "Next steps:"
    echo "1. Update the orchestrator and media server code with HTTPS/WSS support"
    echo "2. Rebuild and push the images with the updated code"
    echo "3. Update the image tags in the deployments"
    echo "4. Test the frontend connection"
}

# Run main function
main "$@" 