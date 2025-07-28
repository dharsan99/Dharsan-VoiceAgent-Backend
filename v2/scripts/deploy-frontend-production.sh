#!/bin/bash

# Frontend Production Deployment Script
# This script deploys the React frontend to production with updated backend URLs

set -e

echo "🚀 Starting Frontend Production Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[HEADER]${NC} $1"
}

# Configuration - Update these values for your environment
PROJECT_ID="${GCP_PROJECT_ID:-your-gcp-project-id}"
REGION="${GCP_REGION:-us-central1}"
REGISTRY_NAME="voice-agent-repo"
FRONTEND_DOMAIN="${FRONTEND_DOMAIN:-your-domain.com}"
MEDIA_DOMAIN="${MEDIA_DOMAIN:-media.your-domain.com}"
API_DOMAIN="${API_DOMAIN:-api.your-domain.com}"

# Derived values
REGISTRY_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REGISTRY_NAME}"

# Function to check prerequisites
check_prerequisites() {
    print_header "=== Checking Prerequisites ==="
    
    # Check if we're in the right directory
    if [ ! -f "v2/frontend/package.json" ]; then
        print_error "Frontend package.json not found. Please run this script from the project root."
        exit 1
    fi
    
    # Check if docker is available
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed. Please install it first."
        exit 1
    fi
    
    print_status "✅ All prerequisites met"
}

# Function to update frontend configuration
update_frontend_config() {
    print_header "=== Updating Frontend Configuration ==="
    
    # Create production environment file
    cat > v2/frontend/.env.production << EOF
# Production Environment Configuration
VITE_WHIP_URL=https://${MEDIA_DOMAIN}/whip
VITE_ORCHESTRATOR_URL=https://${API_DOMAIN}
VITE_WEBSOCKET_URL=wss://${API_DOMAIN}/ws
VITE_APP_TITLE=Voice Agent (Production)
VITE_APP_VERSION=v4.0.0
EOF
    
    print_status "✅ Frontend configuration updated"
    print_status "WHIP URL: https://${MEDIA_DOMAIN}/whip"
    print_status "Orchestrator URL: https://${API_DOMAIN}"
    print_status "WebSocket URL: wss://${API_DOMAIN}/ws"
}

# Function to build frontend
build_frontend() {
    print_header "=== Building Frontend ==="
    
    cd v2/frontend
    
    print_status "Installing dependencies..."
    npm ci --production
    
    print_status "Building production bundle..."
    npm run build
    
    cd ../..
    
    print_status "✅ Frontend built successfully"
}

# Function to create frontend Dockerfile
create_frontend_dockerfile() {
    print_header "=== Creating Frontend Dockerfile ==="
    
    cat > v2/frontend/Dockerfile.production << EOF
# Multi-stage build for production frontend
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built application
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Create non-root user
RUN addgroup -g 1001 -S appgroup && \\
    adduser -u 1001 -S appuser -G appgroup

# Change ownership
RUN chown -R appuser:appgroup /usr/share/nginx/html && \\
    chown -R appuser:appgroup /var/cache/nginx && \\
    chown -R appuser:appgroup /var/log/nginx && \\
    chown -R appuser:appgroup /etc/nginx/conf.d

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
    CMD wget --no-verbose --tries=1 --spider http://localhost:80 || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
EOF
    
    # Create nginx configuration
    cat > v2/frontend/nginx.conf << EOF
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    # Logging
    log_format main '\$remote_addr - \$remote_user [\$time_local] "\$request" '
                    '\$status \$body_bytes_sent "\$http_referer" '
                    '"\$http_user_agent" "\$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    server {
        listen 80;
        server_name localhost;
        root /usr/share/nginx/html;
        index index.html;

        # Handle client-side routing
        location / {
            try_files \$uri \$uri/ /index.html;
        }

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # Health check endpoint
        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }
    }
}
EOF
    
    print_status "✅ Frontend Dockerfile and nginx config created"
}

# Function to build and push frontend image
build_and_push_frontend() {
    print_header "=== Building and Pushing Frontend Image ==="
    
    cd v2/frontend
    
    print_status "Building frontend Docker image..."
    docker build -f Dockerfile.production -t "${REGISTRY_PATH}/frontend:v4.0.0" .
    
    print_status "Pushing frontend image to registry..."
    docker push "${REGISTRY_PATH}/frontend:v4.0.0"
    
    cd ../..
    
    print_status "✅ Frontend image built and pushed"
}

# Function to create frontend deployment manifest
create_frontend_manifest() {
    print_header "=== Creating Frontend Deployment Manifest ==="
    
    cat > v2/k8s/phase4/manifests/frontend-deployment.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: voice-agent-phase4
  labels:
    app: frontend
    component: ui
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
      component: ui
  template:
    metadata:
      labels:
        app: frontend
        component: ui
    spec:
      containers:
        - name: frontend
          image: ${REGISTRY_PATH}/frontend:v4.0.0
          imagePullPolicy: Always
          ports:
            - containerPort: 80
              name: http
          env:
            - name: VITE_WHIP_URL
              value: "https://${MEDIA_DOMAIN}/whip"
            - name: VITE_ORCHESTRATOR_URL
              value: "https://${API_DOMAIN}"
            - name: VITE_WEBSOCKET_URL
              value: "wss://${API_DOMAIN}/ws"
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "200m"
          livenessProbe:
            httpGet:
              path: /health
              port: 80
            initialDelaySeconds: 30
            periodSeconds: 30
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          securityContext:
            allowPrivilegeEscalation: false
            runAsNonRoot: true
            runAsUser: 1001
            runAsGroup: 1001
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
---
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: voice-agent-phase4
  labels:
    app: frontend
    component: ui
spec:
  type: LoadBalancer
  ports:
    - port: 80
      targetPort: 80
      name: http
    - port: 443
      targetPort: 80
      name: https
  selector:
    app: frontend
    component: ui
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: frontend-ingress
  namespace: voice-agent-phase4
  annotations:
    kubernetes.io/ingress.class: "gce"
    kubernetes.io/ingress.global-static-ip-name: "voice-agent-frontend-ip"
    networking.gke.io/managed-certificates: "voice-agent-frontend-cert"
spec:
  rules:
  - host: ${FRONTEND_DOMAIN}
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 80
EOF
    
    print_status "✅ Frontend deployment manifest created"
}

# Function to deploy frontend
deploy_frontend() {
    print_header "=== Deploying Frontend ==="
    
    print_status "Applying frontend deployment..."
    kubectl apply -f v2/k8s/phase4/manifests/frontend-deployment.yaml
    
    print_status "Waiting for frontend deployment to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment/frontend -n voice-agent-phase4
    
    print_status "✅ Frontend deployed successfully"
}

# Function to show deployment status
show_deployment_status() {
    print_header "=== Frontend Deployment Status ==="
    
    echo "📊 Frontend Pod Status:"
    kubectl get pods -n voice-agent-phase4 -l app=frontend
    
    echo ""
    echo "🌐 Frontend Service:"
    kubectl get svc -n voice-agent-phase4 -l app=frontend
    
    echo ""
    echo "🔗 Frontend Ingress:"
    kubectl get ingress -n voice-agent-phase4 -l app=frontend
    
    echo ""
    print_status "📝 Frontend URLs:"
    echo "  - Frontend: https://${FRONTEND_DOMAIN}"
    echo "  - Media Server: https://${MEDIA_DOMAIN}"
    echo "  - API: https://${API_DOMAIN}"
}

# Function to verify deployment
verify_deployment() {
    print_header "=== Verifying Frontend Deployment ==="
    
    # Get the external IP
    EXTERNAL_IP=$(kubectl get svc frontend -n voice-agent-phase4 -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
    
    if [ -n "$EXTERNAL_IP" ]; then
        print_status "Frontend external IP: $EXTERNAL_IP"
        
        # Test health endpoint
        print_status "Testing frontend health endpoint..."
        if curl -f "http://${EXTERNAL_IP}/health" > /dev/null 2>&1; then
            print_status "✅ Frontend health check passed"
        else
            print_warning "⚠️ Frontend health check failed"
        fi
    else
        print_warning "⚠️ External IP not yet assigned"
    fi
    
    print_status "✅ Frontend deployment verification complete"
}

# Main execution
main() {
    print_header "=== Frontend Production Deployment Started ==="
    
    # Check if required environment variables are set
    if [ "$PROJECT_ID" = "your-gcp-project-id" ]; then
        print_error "Please set GCP_PROJECT_ID environment variable"
        print_status "Example: export GCP_PROJECT_ID=my-project-123"
        exit 1
    fi
    
    if [ "$FRONTEND_DOMAIN" = "your-domain.com" ]; then
        print_error "Please set FRONTEND_DOMAIN environment variable"
        print_status "Example: export FRONTEND_DOMAIN=app.mydomain.com"
        exit 1
    fi
    
    # Execute deployment steps
    check_prerequisites
    update_frontend_config
    build_frontend
    create_frontend_dockerfile
    build_and_push_frontend
    create_frontend_manifest
    deploy_frontend
    show_deployment_status
    verify_deployment
    
    print_header "=== Frontend Production Deployment Complete ==="
    
    print_status "🎉 Frontend successfully deployed to production!"
    echo ""
    print_status "📊 Deployment Summary:"
    echo "  - Project: $PROJECT_ID"
    echo "  - Region: $REGION"
    echo "  - Frontend Domain: $FRONTEND_DOMAIN"
    echo "  - Media Domain: $MEDIA_DOMAIN"
    echo "  - API Domain: $API_DOMAIN"
    echo "  - Registry: $REGISTRY_PATH"
    echo ""
    print_status "🔧 Next Steps:"
    echo "  1. Configure DNS to point to the external IPs"
    echo "  2. Test the complete voice agent pipeline"
    echo "  3. Monitor performance and user experience"
    echo "  4. Set up monitoring and analytics"
    echo ""
    print_status "🌐 Access URLs:"
    echo "  - Frontend: https://${FRONTEND_DOMAIN}"
    echo "  - Media Server: https://${MEDIA_DOMAIN}"
    echo "  - API: https://${API_DOMAIN}"
}

# Run main function
main "$@" 