#!/bin/bash

# Voice Agent Phase 2 Deployment Script (Google Cloud Services)
# This script sets up the Redpanda message bus and builds the services

set -e

echo "🚀 Deploying Voice Agent Phase 2 (Google Cloud Services)..."

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    echo "Please install Docker and Docker Compose first"
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available"
    echo "Please install Docker Compose first"
    exit 1
fi

# Function to run docker compose
run_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        docker-compose "$@"
    else
        docker compose "$@"
    fi
}

echo "📦 Starting Redpanda message bus..."
run_docker_compose up -d

echo "⏳ Waiting for Redpanda to be ready..."
sleep 10

# Check if Redpanda is healthy
if ! run_docker_compose ps | grep -q "healthy"; then
    echo "⚠️  Redpanda may not be fully ready yet. Continuing..."
fi

echo "📋 Creating Kafka topics..."
# Get the Redpanda container ID
CONTAINER_ID=$(run_docker_compose ps -q redpanda)

if [ -n "$CONTAINER_ID" ]; then
    echo "Creating audio-in topic..."
    docker exec -it "$CONTAINER_ID" rpk topic create audio-in --if-not-exists
    
    echo "Creating audio-out topic..."
    docker exec -it "$CONTAINER_ID" rpk topic create audio-out --if-not-exists
    
    echo "✅ Topics created successfully"
else
    echo "⚠️  Could not find Redpanda container. Topics may need to be created manually."
fi

echo "🔨 Building Media Server..."
cd media-server
go build -o media-server
echo "✅ Media Server built successfully"

echo "🔨 Building Orchestrator..."
cd ../orchestrator
go build -o orchestrator
echo "✅ Orchestrator built successfully"

cd ..

echo ""
echo "🎉 Phase 2 deployment completed!"
echo ""
echo "📋 Next steps:"
echo ""
echo "1. Set up Google Cloud services:"
echo "   - Enable Speech-to-Text API"
echo "   - Enable Text-to-Speech API"
echo "   - Enable Generative Language API"
echo "   - Create service account and download credentials"
echo "   - Get Gemini API key from: https://makersuite.google.com/app/apikey"
echo ""
echo "2. Configure environment variables:"
echo "   cd v2/orchestrator"
echo "   cp env.example .env"
echo "   # Edit .env with your Google Cloud credentials"
echo ""
echo "3. Start the services:"
echo "   # Terminal 1 - Media Server:"
echo "   cd v2/media-server"
echo "   ./media-server"
echo ""
echo "   # Terminal 2 - Orchestrator:"
echo "   cd v2/orchestrator"
echo "   ./orchestrator"
echo ""
echo "4. Start the frontend (if not already running):"
echo "   cd ../Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend"
echo "   npm run dev"
echo ""
echo "5. Test the system:"
echo "   - Open the frontend in your browser"
echo "   - Allow microphone access"
echo "   - Click 'Start Streaming'"
echo "   - Speak and listen for AI response"
echo ""
echo "🔍 Useful commands:"
echo "   # Check Redpanda status:"
echo "   docker compose ps"
echo ""
echo "   # View Redpanda logs:"
echo "   docker compose logs redpanda"
echo ""
echo "   # Check Kafka topics:"
echo "   docker exec -it \$(docker compose ps -q redpanda) rpk topic list"
echo ""
echo "📚 For more information, see README-Phase2.md" 