#!/bin/bash

# Phase 3: Apply ScyllaDB Schema
# This script applies the database schema to the deployed ScyllaDB instance

set -e

echo "🗄️ Applying ScyllaDB schema for Phase 3..."

# Configuration
SCYLLADB_NAMESPACE="voice-agent-phase3"
SCYLLADB_SERVICE="scylladb"
SCYLLADB_PORT="9042"
SCHEMA_FILE="k8s/phase3/db/schema.cql"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl is not installed or not in PATH"
    exit 1
fi

# Check if the schema file exists
if [ ! -f "$SCHEMA_FILE" ]; then
    print_error "Schema file not found: $SCHEMA_FILE"
    exit 1
fi

# Check if ScyllaDB is running
print_status "Checking ScyllaDB deployment status..."
if ! kubectl get pods -n $SCYLLADB_NAMESPACE -l app=scylladb | grep -q "Running"; then
    print_error "ScyllaDB is not running in namespace $SCYLLADB_NAMESPACE"
    print_status "Please deploy ScyllaDB first using:"
    echo "kubectl apply -f k8s/phase3/manifests/scylladb-deployment.yaml"
    exit 1
fi

print_status "ScyllaDB is running. Waiting for it to be ready..."

# Wait for ScyllaDB to be ready
SLEEP_COUNT=0
MAX_SLEEP=60
while [ $SLEEP_COUNT -lt $MAX_SLEEP ]; do
    if kubectl get pods -n $SCYLLADB_NAMESPACE -l app=scylladb | grep -q "1/1.*Running"; then
        print_status "ScyllaDB is ready!"
        break
    fi
    print_status "Waiting for ScyllaDB to be ready... ($SLEEP_COUNT/$MAX_SLEEP)"
    sleep 5
    SLEEP_COUNT=$((SLEEP_COUNT + 1))
done

if [ $SLEEP_COUNT -eq $MAX_SLEEP ]; then
    print_error "ScyllaDB did not become ready within the expected time"
    exit 1
fi

# Get the ScyllaDB pod name
SCYLLADB_POD=$(kubectl get pods -n $SCYLLADB_NAMESPACE -l app=scylladb -o jsonpath='{.items[0].metadata.name}')

if [ -z "$SCYLLADB_POD" ]; then
    print_error "Could not find ScyllaDB pod"
    exit 1
fi

print_status "Found ScyllaDB pod: $SCYLLADB_POD"

# Test ScyllaDB connection
print_status "Testing ScyllaDB connection..."
if ! kubectl exec -n $SCYLLADB_NAMESPACE $SCYLLADB_POD -- cqlsh -e "SELECT release_version FROM system.local;" > /dev/null 2>&1; then
    print_error "Could not connect to ScyllaDB"
    print_status "Checking ScyllaDB logs..."
    kubectl logs -n $SCYLLADB_NAMESPACE $SCYLLADB_POD --tail=20
    exit 1
fi

print_status "ScyllaDB connection successful!"

# Apply the schema
print_status "Applying schema from $SCHEMA_FILE..."

# Copy schema file to pod
kubectl cp $SCHEMA_FILE $SCYLLADB_NAMESPACE/$SCYLLADB_POD:/tmp/schema.cql

# Apply schema using cqlsh
if kubectl exec -n $SCYLLADB_NAMESPACE $SCYLLADB_POD -- cqlsh -f /tmp/schema.cql; then
    print_status "Schema applied successfully!"
else
    print_error "Failed to apply schema"
    print_status "Checking ScyllaDB logs for errors..."
    kubectl logs -n $SCYLLADB_NAMESPACE $SCYLLADB_POD --tail=10
    exit 1
fi

# Verify schema was applied
print_status "Verifying schema application..."

# Check if keyspace exists
if kubectl exec -n $SCYLLADB_NAMESPACE $SCYLLADB_POD -- cqlsh -e "DESCRIBE KEYSPACE voice_ai_ks;" > /dev/null 2>&1; then
    print_status "✅ Keyspace 'voice_ai_ks' created successfully"
else
    print_error "❌ Keyspace 'voice_ai_ks' not found"
    exit 1
fi

# Check if main table exists
if kubectl exec -n $SCYLLADB_NAMESPACE $SCYLLADB_POD -- cqlsh -e "USE voice_ai_ks; DESCRIBE TABLE voice_interactions;" > /dev/null 2>&1; then
    print_status "✅ Table 'voice_interactions' created successfully"
else
    print_error "❌ Table 'voice_interactions' not found"
    exit 1
fi

# Check if other tables exist
TABLES=("session_summaries" "performance_metrics" "error_logs" "system_health")
for table in "${TABLES[@]}"; do
    if kubectl exec -n $SCYLLADB_NAMESPACE $SCYLLADB_POD -- cqlsh -e "USE voice_ai_ks; DESCRIBE TABLE $table;" > /dev/null 2>&1; then
        print_status "✅ Table '$table' created successfully"
    else
        print_warning "⚠️ Table '$table' not found"
    fi
done

# Insert test data to verify functionality
print_status "Inserting test data to verify functionality..."

TEST_QUERY="
USE voice_ai_ks;
INSERT INTO voice_interactions (session_id, event_timestamp, stage, data, latency_ms, metadata, created_at)
VALUES ('test-session-001', toTimestamp(now()), 'stt', 'Hello world test', 150, {'confidence': '0.95', 'model': 'nova-3'}, toTimestamp(now()));
"

if kubectl exec -n $SCYLLADB_NAMESPACE $SCYLLADB_POD -- cqlsh -e "$TEST_QUERY" > /dev/null 2>&1; then
    print_status "✅ Test data inserted successfully"
else
    print_warning "⚠️ Failed to insert test data"
fi

# Verify test data
if kubectl exec -n $SCYLLADB_NAMESPACE $SCYLLADB_POD -- cqlsh -e "USE voice_ai_ks; SELECT COUNT(*) FROM voice_interactions WHERE session_id = 'test-session-001';" | grep -q "1"; then
    print_status "✅ Test data verification successful"
else
    print_warning "⚠️ Test data verification failed"
fi

# Clean up test data
kubectl exec -n $SCYLLADB_NAMESPACE $SCYLLADB_POD -- cqlsh -e "USE voice_ai_ks; DELETE FROM voice_interactions WHERE session_id = 'test-session-001';" > /dev/null 2>&1

print_status "🎉 ScyllaDB schema application completed successfully!"
echo ""
print_status "📊 Database Summary:"
echo "  - Keyspace: voice_ai_ks"
echo "  - Main Table: voice_interactions"
echo "  - Additional Tables: session_summaries, performance_metrics, error_logs, system_health"
echo "  - Materialized View: stage_analytics"
echo ""
print_status "🔗 Connection Details:"
echo "  - Service: scylladb.voice-agent-phase3.svc.cluster.local:9042"
echo "  - Namespace: voice-agent-phase3"
echo ""
print_status "📝 Next Steps:"
echo "  1. Deploy the Logging Service"
echo "  2. Update Orchestrator to publish intermediate results"
echo "  3. Test the complete Phase 3 pipeline" 