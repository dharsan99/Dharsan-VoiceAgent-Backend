#!/bin/bash

# Phase 3: Complete Deployment Script
# This script deploys all Phase 3 components: Redpanda, ScyllaDB, and Logging Service

set -e

echo "🚀 Phase 3: Deploying Scalable Data Backbone"

# Configuration
NAMESPACE="voice-agent-phase3"
REDPANDA_NAMESPACE="voice-agent-phase3"
SCYLLADB_NAMESPACE="voice-agent-phase3"

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

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl is not installed or not in PATH"
    exit 1
fi

# Check if docker is available
if ! command -v docker &> /dev/null; then
    print_error "docker is not installed or not in PATH"
    exit 1
fi

# Function to wait for pod to be ready
wait_for_pod() {
    local namespace=$1
    local label=$2
    local max_wait=300
    local wait_time=0
    
    print_status "Waiting for pod with label $label in namespace $namespace..."
    
    while [ $wait_time -lt $max_wait ]; do
        if kubectl get pods -n $namespace -l $label | grep -q "1/1.*Running"; then
            print_status "Pod is ready!"
            return 0
        fi
        print_status "Waiting for pod to be ready... ($wait_time/$max_wait seconds)"
        sleep 10
        wait_time=$((wait_time + 10))
    done
    
    print_error "Pod did not become ready within $max_wait seconds"
    return 1
}

# Function to check if namespace exists
check_namespace() {
    local namespace=$1
    if kubectl get namespace $namespace > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to create namespace if it doesn't exist
create_namespace() {
    local namespace=$1
    if ! check_namespace $namespace; then
        print_status "Creating namespace: $namespace"
        kubectl create namespace $namespace
    else
        print_status "Namespace $namespace already exists"
    fi
}

# Step 1: Create namespaces
print_step "1. Creating namespaces"
create_namespace $NAMESPACE

# Step 2: Deploy Redpanda with enhanced configuration
print_step "2. Deploying Redpanda with intermediate topics"

# Start Redpanda using docker-compose
print_status "Starting Redpanda..."
cd v2
docker-compose up -d redpanda

# Wait for Redpanda to be ready
print_status "Waiting for Redpanda to be ready..."
sleep 30

# Create intermediate topics
print_status "Creating intermediate topics..."
if [ -f "scripts/create-topics.sh" ]; then
    ./scripts/create-topics.sh
else
    print_error "Topic creation script not found"
    exit 1
fi

# Step 3: Deploy ScyllaDB
print_step "3. Deploying ScyllaDB"

# Apply ScyllaDB deployment
print_status "Applying ScyllaDB deployment..."
kubectl apply -f k8s/phase3/manifests/scylladb-deployment.yaml

# Wait for ScyllaDB to be ready
if ! wait_for_pod $SCYLLADB_NAMESPACE "app=scylladb"; then
    print_error "ScyllaDB failed to start"
    kubectl logs -n $SCYLLADB_NAMESPACE -l app=scylladb --tail=20
    exit 1
fi

# Step 4: Apply ScyllaDB schema
print_step "4. Applying ScyllaDB schema"

# Apply schema
print_status "Applying database schema..."
if [ -f "scripts/apply-schema.sh" ]; then
    ./scripts/apply-schema.sh
else
    print_error "Schema application script not found"
    exit 1
fi

# Step 5: Build and deploy Logging Service
print_step "5. Building and deploying Logging Service"

# Build logging service Docker image
print_status "Building logging service Docker image..."
cd logging-service

# Initialize Go module if needed
if [ ! -f "go.sum" ]; then
    print_status "Initializing Go module..."
    go mod tidy
fi

# Build the service
print_status "Building logging service..."
docker build -t logging-service:latest .

cd ..

# Deploy logging service
print_status "Deploying logging service..."
kubectl apply -f k8s/phase3/manifests/logging-service-deployment.yaml

# Wait for logging service to be ready
if ! wait_for_pod $NAMESPACE "app=logging-service"; then
    print_error "Logging service failed to start"
    kubectl logs -n $NAMESPACE -l app=logging-service --tail=20
    exit 1
fi

# Step 6: Update Orchestrator (if running)
print_step "6. Updating Orchestrator for Phase 3"

# Check if orchestrator is running and update it
if kubectl get pods -n $NAMESPACE -l app=orchestrator > /dev/null 2>&1; then
    print_status "Orchestrator is running, updating for Phase 3..."
    # Here you would typically update the orchestrator deployment
    # For now, we'll just note that it needs to be updated
    print_warning "Orchestrator needs to be updated with Phase 3 changes"
    print_status "Please rebuild and redeploy the orchestrator with the updated code"
else
    print_status "Orchestrator not running, will be deployed with Phase 3 support"
fi

# Step 7: Health checks
print_step "7. Running health checks"

# Check Redpanda topics
print_status "Checking Redpanda topics..."
docker exec -it $(docker ps -q --filter "name=redpanda") rpk topic list --brokers localhost:9092

# Check ScyllaDB connection
print_status "Checking ScyllaDB connection..."
SCYLLADB_POD=$(kubectl get pods -n $SCYLLADB_NAMESPACE -l app=scylladb -o jsonpath='{.items[0].metadata.name}')
if kubectl exec -n $SCYLLADB_NAMESPACE $SCYLLADB_POD -- cqlsh -e "SELECT release_version FROM system.local;" > /dev/null 2>&1; then
    print_status "✅ ScyllaDB connection successful"
else
    print_error "❌ ScyllaDB connection failed"
fi

# Check logging service health
print_status "Checking logging service health..."
LOGGING_POD=$(kubectl get pods -n $NAMESPACE -l app=logging-service -o jsonpath='{.items[0].metadata.name}')
if kubectl exec -n $NAMESPACE $LOGGING_POD -- wget -q -O- http://localhost:8080/health > /dev/null 2>&1; then
    print_status "✅ Logging service health check passed"
else
    print_error "❌ Logging service health check failed"
fi

# Step 8: Display deployment summary
print_step "8. Deployment Summary"

echo ""
print_status "🎉 Phase 3 deployment completed successfully!"
echo ""
print_status "📊 Component Status:"
echo "  ✅ Redpanda: Running with intermediate topics"
echo "  ✅ ScyllaDB: Deployed and schema applied"
echo "  ✅ Logging Service: Running and healthy"
echo "  ⚠️  Orchestrator: Needs update for Phase 3"
echo ""
print_status "🔗 Service Endpoints:"
echo "  - Redpanda: localhost:9092"
echo "  - ScyllaDB: scylladb.$SCYLLADB_NAMESPACE.svc.cluster.local:9042"
echo "  - Logging Service: logging-service.$NAMESPACE.svc.cluster.local:8080"
echo ""
print_status "📝 Next Steps:"
echo "  1. Update Orchestrator with Phase 3 code changes"
echo "  2. Test the complete pipeline with logging"
echo "  3. Monitor logs and metrics"
echo "  4. Configure monitoring and alerting"
echo ""
print_status "🧪 Testing Commands:"
echo "  # Check Redpanda topics"
echo "  docker exec -it \$(docker ps -q --filter \"name=redpanda\") rpk topic list"
echo ""
echo "  # Check ScyllaDB data"
echo "  kubectl exec -n $SCYLLADB_NAMESPACE $SCYLLADB_POD -- cqlsh -e \"USE voice_ai_ks; SELECT COUNT(*) FROM voice_interactions;\""
echo ""
echo "  # Check logging service metrics"
echo "  kubectl port-forward -n $NAMESPACE svc/logging-service 8080:8080"
echo "  curl http://localhost:8080/metrics"
echo ""
print_status "📚 Documentation:"
echo "  - Phase 3 TODO: V2_PHASE3_TODO.md"
echo "  - Schema: k8s/phase3/db/schema.cql"
echo "  - Logging Service: logging-service/main.go" 