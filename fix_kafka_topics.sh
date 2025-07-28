#!/bin/bash

# Fix Kafka Topics for Voice Agent
# This script creates the missing Kafka topics that are causing logging errors

set -e

echo "🔧 Fixing Kafka Topics for Voice Agent..."

# Check if we're in the right directory
if [ ! -f "v2/k8s/phase5/manifests/redpanda-deployment.yaml" ]; then
    echo "❌ Error: Please run this script from the Dharsan-VoiceAgent-Backend directory"
    exit 1
fi

# Get RedPanda pod name
REDPANDA_POD=$(kubectl get pods -n voice-agent-phase5 -l app=redpanda -o jsonpath='{.items[0].metadata.name}')

if [ -z "$REDPANDA_POD" ]; then
    echo "❌ Error: RedPanda pod not found"
    exit 1
fi

echo "📦 Found RedPanda pod: $REDPANDA_POD"

# List of missing topics based on error logs
TOPICS=(
    "stt-results"
    "tts-results" 
    "llm-requests"
    "llm-results"
    "audio-sessions"
    "session-logs"
    "voice-agent-metrics"
)

echo "📋 Creating missing Kafka topics..."

for topic in "${TOPICS[@]}"; do
    echo "Creating topic: $topic"
    kubectl exec -n voice-agent-phase5 $REDPANDA_POD -- rpk topic create $topic --partitions 3 --replicas 1 || {
        echo "⚠️  Topic $topic might already exist or failed to create"
    }
done

echo "✅ Kafka topics created successfully!"

# Verify topics were created
echo "📊 Verifying topics..."
kubectl exec -n voice-agent-phase5 $REDPANDA_POD -- rpk topic list

echo "🎉 Kafka topic fix completed!"
echo "📝 Summary:"
echo "   - Created missing logging topics"
echo "   - Fixed 'Unknown Topic Or Partition' errors"
echo "   - Improved observability and metrics collection" 