#!/bin/bash

# Phase 3: Create intermediate topics for logging service
# This script creates the additional topics needed for structured logging

set -e

echo "🚀 Creating Phase 3 intermediate topics for Redpanda..."

# Wait for Redpanda to be ready
echo "⏳ Waiting for Redpanda to be ready..."
until rpk cluster health --brokers localhost:9092 > /dev/null 2>&1; do
    echo "Waiting for Redpanda cluster to be healthy..."
    sleep 5
done

echo "✅ Redpanda cluster is healthy"

# Create intermediate topics for logging
echo "📝 Creating intermediate topics..."

# STT Results topic - stores final transcripts from Speech-to-Text
echo "Creating stt-results topic..."
rpk topic create stt-results \
    --brokers localhost:9092 \
    --partitions 3 \
    --replicas 1 \
    --config retention.ms=86400000 \
    --config cleanup.policy=delete

# LLM Requests topic - stores final responses from Language Model
echo "Creating llm-requests topic..."
rpk topic create llm-requests \
    --brokers localhost:9092 \
    --partitions 3 \
    --replicas 1 \
    --config retention.ms=86400000 \
    --config cleanup.policy=delete

# TTS Results topic - stores metadata about synthesized audio
echo "Creating tts-results topic..."
rpk topic create tts-results \
    --brokers localhost:9092 \
    --partitions 3 \
    --replicas 1 \
    --config retention.ms=86400000 \
    --config cleanup.policy=delete

# Verify topics were created
echo "🔍 Verifying topics..."
rpk topic list --brokers localhost:9092

echo "✅ All Phase 3 intermediate topics created successfully!"
echo ""
echo "📊 Topic Summary:"
echo "  - audio-in: Audio input from Media Server"
echo "  - audio-out: Audio output to Media Server"
echo "  - stt-results: STT transcripts for logging"
echo "  - llm-requests: LLM responses for logging"
echo "  - tts-results: TTS metadata for logging"
echo ""
echo "🎯 Phase 3 Redpanda setup complete!" 