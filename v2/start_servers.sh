#!/bin/bash

# Voice AI Backend v2.0 - Start Both Servers Script

echo "🚀 Starting Voice AI Backend v2.0 servers..."

# Function to cleanup background processes
cleanup() {
    echo "🛑 Shutting down servers..."
    if [ ! -z "$MEDIA_SERVER_PID" ]; then
        kill $MEDIA_SERVER_PID 2>/dev/null
        echo "✅ Media server stopped"
    fi
    if [ ! -z "$PYTHON_SERVER_PID" ]; then
        kill $PYTHON_SERVER_PID 2>/dev/null
        echo "✅ Python server stopped"
    fi
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Check if we're in the v2 directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Please run this script from the v2 directory"
    exit 1
fi

# Check if media server binary exists
if [ ! -f "media-server/media-server" ]; then
    echo "❌ Error: Media server binary not found. Please build it first:"
    echo "   cd media-server && go build -o media-server ."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing Python dependencies..."
pip install -r requirements.txt

# Check environment variables
echo "🔍 Checking environment variables..."
required_vars=("DEEPGRAM_API_KEY" "GROQ_API_KEY" "ELEVENLABS_API_KEY")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "⚠️  Warning: Missing environment variables: ${missing_vars[*]}"
    echo "   Some features may not work properly."
fi

# Start Redpanda (Kafka) if not running
echo "🔍 Checking if Redpanda is running..."
if ! docker ps | grep -q redpanda; then
    echo "🚀 Starting Redpanda (Kafka)..."
    docker-compose up -d redpanda
    echo "⏳ Waiting for Redpanda to be ready..."
    sleep 10
else
    echo "✅ Redpanda is already running"
fi

# Start Media Server (Go)
echo "🚀 Starting Media Server (Go) on port 8080..."
cd media-server
./media-server &
MEDIA_SERVER_PID=$!
cd ..
echo "✅ Media server started with PID: $MEDIA_SERVER_PID"

# Wait a moment for media server to start
sleep 2

# Start Python Backend
echo "🚀 Starting Python Backend on port 8000..."
python main.py &
PYTHON_SERVER_PID=$!
echo "✅ Python server started with PID: $PYTHON_SERVER_PID"

echo ""
echo "🎉 Both servers are now running!"
echo "📡 Media Server (WHIP): http://localhost:8080"
echo "🔌 Python Backend (WebSocket): ws://localhost:8000/ws"
echo "📚 API Documentation: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for user to stop
wait 