#!/bin/bash

# Dharsan Voice Agent - Cursor Workspace Setup Script
# This script sets up the optimized Cursor workspace for the voice agent project

set -e

echo "🚀 Setting up Cursor workspace for Dharsan Voice Agent..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if we're in the right directory
if [ ! -f "package.json" ] && [ ! -f "dharsan-voice-agent.code-workspace" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

print_status "Checking prerequisites..."

# Check for Node.js
if ! command -v node &> /dev/null; then
    print_error "Node.js not found. Please install Node.js 16+ from https://nodejs.org/"
    exit 1
fi

# Check for Go
if ! command -v go &> /dev/null; then
    print_warning "Go not found. Install Go 1.19+ from https://golang.org/ for backend development"
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    print_warning "Python3 not found. Install Python 3.8+ for backend services"
fi

# Check for Docker
if ! command -v docker &> /dev/null; then
    print_warning "Docker not found. Install Docker for containerized development"
fi

# Setup frontend dependencies
print_status "Setting up frontend dependencies..."
if [ -d "Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend" ]; then
    cd Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend
    if [ -f "package.json" ]; then
        print_status "Installing frontend dependencies..."
        npm install
        print_success "Frontend dependencies installed"
    fi
    cd ../..
fi

# Setup Python virtual environment
print_status "Setting up Python virtual environment..."
if command -v python3 &> /dev/null; then
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_success "Python virtual environment created"
    fi
    
    source venv/bin/activate 2>/dev/null || print_warning "Could not activate virtual environment"
    
    # Install common Python dependencies
    if [ -f "v2/stt-service/requirements.txt" ]; then
        print_status "Installing STT service dependencies..."
        pip install -r v2/stt-service/requirements.txt
    fi
    
    if [ -f "v2/tts-service/requirements.txt" ]; then
        print_status "Installing TTS service dependencies..."
        pip install -r v2/tts-service/requirements.txt
    fi
    
    if [ -f "v2/llm-service/requirements.txt" ]; then
        print_status "Installing LLM service dependencies..."
        pip install -r v2/llm-service/requirements.txt
    fi
fi

# Setup Go modules
print_status "Setting up Go modules..."
if command -v go &> /dev/null; then
    if [ -d "v2/orchestrator" ] && [ -f "v2/orchestrator/go.mod" ]; then
        cd v2/orchestrator
        go mod tidy
        go mod download
        print_success "Orchestrator Go modules updated"
        cd ../..
    fi
    
    if [ -d "v2/media-server" ] && [ -f "v2/media-server/go.mod" ]; then
        cd v2/media-server
        go mod tidy
        go mod download
        print_success "Media server Go modules updated"
        cd ../..
    fi
fi

# Create logs directory if it doesn't exist
if [ ! -d "logs" ]; then
    mkdir -p logs
    print_success "Logs directory created"
fi

# Create a .env.example if it doesn't exist
if [ ! -f ".env.example" ]; then
    print_status "Creating .env.example file..."
    cat > .env.example << EOF
# Environment Configuration
NODE_ENV=development
REACT_APP_ENVIRONMENT=development

# Backend URLs
REACT_APP_WEBSOCKET_URL=ws://localhost:8080/ws
REACT_APP_API_BASE_URL=http://localhost:8080

# Production URLs (when REACT_APP_ENVIRONMENT=production)
REACT_APP_PROD_WEBSOCKET_URL=wss://your-domain.com/ws
REACT_APP_PROD_API_BASE_URL=https://your-domain.com

# Service Ports
ORCHESTRATOR_PORT=8080
MEDIA_SERVER_PORT=8081
STT_SERVICE_PORT=8082
TTS_SERVICE_PORT=8083
LLM_SERVICE_PORT=8084

# Audio Configuration
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
AUDIO_CHUNK_SIZE=4096

# Logging
LOG_LEVEL=info
EOF
    print_success ".env.example created"
fi

# Check if workspace file exists
if [ -f "dharsan-voice-agent.code-workspace" ]; then
    print_status "Workspace file exists. You can open it with:"
    echo "   cursor dharsan-voice-agent.code-workspace"
else
    print_warning "Workspace file not found. Creating basic workspace..."
fi

# Print helpful information
print_success "Cursor workspace setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Open the workspace: cursor dharsan-voice-agent.code-workspace"
echo "2. Install recommended extensions when prompted"
echo "3. Copy .env.example to .env and configure your environment"
echo "4. Use Ctrl+Shift+P (Cmd+Shift+P on Mac) to run tasks:"
echo "   - 'Tasks: Run Task' → '🚀 Start Full Stack'"
echo "   - 'Tasks: Run Task' → '🎨 Start Frontend'"
echo "   - 'Tasks: Run Task' → '🔧 Start Orchestrator'"
echo ""
echo "🔧 Available commands:"
echo "   Frontend: cd Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend && npm run dev"
echo "   Backend:  cd v2/orchestrator && go run main.go"
echo "   Tests:    cd Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend && npm test"
echo ""
echo "📚 Documentation:"
echo "   - Project docs in ./docs/"
echo "   - Frontend docs in ./Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend/docs/"
echo "   - API docs in service directories"
echo ""
print_success "Happy coding! 🎉"