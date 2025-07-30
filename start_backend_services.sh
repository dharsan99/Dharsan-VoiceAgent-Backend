#!/bin/bash

# Voice Agent Backend Services Startup Script
# This script starts all backend services with proper virtual environment activation

set -e  # Exit on any error

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

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to kill process on a port
kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port)
    if [ ! -z "$pid" ]; then
        print_warning "Killing process on port $port (PID: $pid)"
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    print_status "Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url/health" >/dev/null 2>&1; then
            print_success "$service_name is ready!"
            return 0
        fi
        
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    
    print_error "$service_name failed to start within $max_attempts seconds"
    return 1
}

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_status "Starting Voice Agent Backend Services..."
print_status "Script directory: $SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    print_error "Virtual environment not found. Please create it first:"
    print_error "python3 -m venv venv"
    exit 1
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Check if required Python packages are installed
print_status "Checking Python dependencies..."
if ! python -c "import fastapi, uvicorn, structlog" 2>/dev/null; then
    print_warning "Some Python packages are missing. Installing requirements..."
    pip install -r requirements.txt
fi

# Load environment configuration
if [ -f "v2/orchestrator/env.config" ]; then
    print_status "Loading environment configuration..."
    export $(grep -v '^#' v2/orchestrator/env.config | xargs)
else
    print_warning "Environment configuration file not found. Using defaults..."
    export ORCHESTRATOR_PORT=8004
    export STT_SERVICE_PORT=8000
    export TTS_SERVICE_PORT=5001
    export MEDIA_SERVER_PORT=8001
    export LLM_SERVICE_PORT=8003
fi

# Kill any existing processes on our ports
print_status "Checking for existing processes on required ports..."
PORTS=($STT_SERVICE_PORT $TTS_SERVICE_PORT $MEDIA_SERVER_PORT $LLM_SERVICE_PORT $ORCHESTRATOR_PORT)
for port in "${PORTS[@]}"; do
    if check_port $port; then
        print_warning "Port $port is in use. Attempting to free it..."
        kill_port $port
    fi
done

# Wait a moment for ports to be freed
sleep 2

# Create logs directory
mkdir -p logs

# Start STT Service
print_status "Starting STT Service on port $STT_SERVICE_PORT..."
cd v2/stt-service
export STT_SERVICE_PORT=$STT_SERVICE_PORT
export CORS_ORIGINS=$CORS_ORIGINS
python main.py > ../../logs/stt-service.log 2>&1 &
STT_PID=$!
cd - > /dev/null
print_success "STT Service started with PID: $STT_PID"

# Start TTS Service
print_status "Starting TTS Service on port $TTS_SERVICE_PORT..."
cd v2/tts-service
export TTS_SERVICE_PORT=$TTS_SERVICE_PORT
export CORS_ORIGINS=$CORS_ORIGINS
python main.py > ../../logs/tts-service.log 2>&1 &
TTS_PID=$!
cd - > /dev/null
print_success "TTS Service started with PID: $TTS_PID"

# Start LLM Service
print_status "Starting LLM Service on port $LLM_SERVICE_PORT..."
cd v2/llm-service
export LLM_SERVICE_PORT=$LLM_SERVICE_PORT
export CORS_ORIGINS=$CORS_ORIGINS
export OLLAMA_BASE_URL=$OLLAMA_BASE_URL
python main.py > ../../logs/llm-service.log 2>&1 &
LLM_PID=$!
cd - > /dev/null
print_success "LLM Service started with PID: $LLM_PID"

# Start Media Server
print_status "Starting Media Server on port $MEDIA_SERVER_PORT..."
cd v2/media-server
./media-server > ../../logs/media-server.log 2>&1 &
MEDIA_PID=$!
cd - > /dev/null
print_success "Media Server started with PID: $MEDIA_PID"

# Start Orchestrator
print_status "Starting Orchestrator on port $ORCHESTRATOR_PORT..."
cd v2/orchestrator
export ORCHESTRATOR_PORT=$ORCHESTRATOR_PORT
export STT_SERVICE_URL=http://localhost:$STT_SERVICE_PORT
export TTS_SERVICE_URL=http://localhost:$TTS_SERVICE_PORT
export LLM_SERVICE_URL=http://localhost:$LLM_SERVICE_PORT
export MEDIA_SERVER_URL=http://localhost:$MEDIA_SERVER_PORT
./orchestrator > ../../logs/orchestrator.log 2>&1 &
ORCHESTRATOR_PID=$!
cd - > /dev/null
print_success "Orchestrator started with PID: $ORCHESTRATOR_PID"

# Wait for services to start
print_status "Waiting for services to initialize..."
sleep 5

# Check service health
print_status "Checking service health..."

# Check STT Service
if wait_for_service "http://localhost:$STT_SERVICE_PORT" "STT Service"; then
    print_success "STT Service is healthy"
else
    print_error "STT Service health check failed"
fi

# Check TTS Service
if wait_for_service "http://localhost:$TTS_SERVICE_PORT" "TTS Service"; then
    print_success "TTS Service is healthy"
else
    print_error "TTS Service health check failed"
fi

# Check LLM Service
if wait_for_service "http://localhost:$LLM_SERVICE_PORT" "LLM Service"; then
    print_success "LLM Service is healthy"
else
    print_error "LLM Service health check failed"
fi

# Check Media Server
if wait_for_service "http://localhost:$MEDIA_SERVER_PORT" "Media Server"; then
    print_success "Media Server is healthy"
else
    print_error "Media Server health check failed"
fi

# Check Orchestrator
if wait_for_service "http://localhost:$ORCHESTRATOR_PORT" "Orchestrator"; then
    print_success "Orchestrator is healthy"
else
    print_error "Orchestrator health check failed"
fi

# Test log endpoints
print_status "Testing log endpoints..."
sleep 2

# Test individual service log endpoints
print_status "Testing individual service log endpoints..."

# Test STT logs
if curl -s "http://localhost:$STT_SERVICE_PORT/logs" >/dev/null 2>&1; then
    print_success "STT Service logs endpoint is working"
else
    print_warning "STT Service logs endpoint not responding"
fi

# Test TTS logs
if curl -s "http://localhost:$TTS_SERVICE_PORT/logs" >/dev/null 2>&1; then
    print_success "TTS Service logs endpoint is working"
else
    print_warning "TTS Service logs endpoint not responding"
fi

# Test LLM logs
if curl -s "http://localhost:$LLM_SERVICE_PORT/logs" >/dev/null 2>&1; then
    print_success "LLM Service logs endpoint is working"
else
    print_warning "LLM Service logs endpoint not responding"
fi

# Test Media Server logs
if curl -s "http://localhost:$MEDIA_SERVER_PORT/logs" >/dev/null 2>&1; then
    print_success "Media Server logs endpoint is working"
else
    print_warning "Media Server logs endpoint not responding"
fi

# Test Orchestrator log aggregation
if curl -s "http://localhost:$ORCHESTRATOR_PORT/logs" >/dev/null 2>&1; then
    print_success "Orchestrator log aggregation endpoint is working"
else
    print_warning "Orchestrator log aggregation endpoint not responding"
fi

# Save PIDs to file for later cleanup
cat > logs/service_pids.txt << EOF
STT_PID=$STT_PID
TTS_PID=$TTS_PID
LLM_PID=$LLM_PID
MEDIA_PID=$MEDIA_PID
ORCHESTRATOR_PID=$ORCHESTRATOR_PID
EOF

# Display service information
echo ""
print_success "All backend services started successfully!"
echo ""
echo "Service Information:"
echo "==================="
echo "STT Service:      http://localhost:$STT_SERVICE_PORT (PID: $STT_PID)"
echo "TTS Service:      http://localhost:$TTS_SERVICE_PORT (PID: $TTS_PID)"
echo "LLM Service:      http://localhost:$LLM_SERVICE_PORT (PID: $LLM_PID)"
echo "Media Server:     http://localhost:$MEDIA_SERVER_PORT (PID: $MEDIA_PID)"
echo "Orchestrator:     http://localhost:$ORCHESTRATOR_PORT (PID: $ORCHESTRATOR_PID)"
echo ""
echo "Log Files:"
echo "=========="
echo "STT Service:      logs/stt-service.log"
echo "TTS Service:      logs/tts-service.log"
echo "LLM Service:      logs/llm-service.log"
echo "Media Server:     logs/media-server.log"
echo "Orchestrator:     logs/orchestrator.log"
echo ""
echo "Test Log Endpoints:"
echo "=================="
echo "STT Logs:         curl http://localhost:$STT_SERVICE_PORT/logs"
echo "TTS Logs:         curl http://localhost:$TTS_SERVICE_PORT/logs"
echo "LLM Logs:         curl http://localhost:$LLM_SERVICE_PORT/logs"
echo "Media Logs:       curl http://localhost:$MEDIA_SERVER_PORT/logs"
echo "All Logs:         curl http://localhost:$ORCHESTRATOR_PORT/logs"
echo ""
echo "To stop all services, run: ./stop_backend_services.sh"
echo ""

# Keep the script running to maintain the virtual environment
print_status "Services are running. Press Ctrl+C to stop all services..."

# Function to cleanup on exit
cleanup() {
    echo ""
    print_status "Stopping all services..."
    
    if [ -f logs/service_pids.txt ]; then
        source logs/service_pids.txt
        
        for pid_var in STT_PID TTS_PID LLM_PID MEDIA_PID ORCHESTRATOR_PID; do
            pid=${!pid_var}
            if [ ! -z "$pid" ] && kill -0 $pid 2>/dev/null; then
                print_status "Stopping $pid_var (PID: $pid)..."
                kill $pid 2>/dev/null || true
            fi
        done
    fi
    
    print_success "All services stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Keep the script running
while true; do
    sleep 1
done 