#!/bin/bash

# Auto-Start Development Environment Script
# This script opens two terminals: one for backend, one for frontend

echo "🚀 Starting Dharsan Voice Agent Development Environment..."

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command_exists nvm; then
    echo "❌ NVM not found. Please install NVM first."
    echo "   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
    exit 1
fi

if [ ! -f "venv/bin/activate" ]; then
    echo "❌ Python virtual environment not found. Please run:"
    echo "   python3 -m venv venv"
    exit 1
fi

if [ ! -f "start_backend_services.sh" ]; then
    echo "❌ Backend services script not found."
    exit 1
fi

if [ ! -f "../Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend/package.json" ]; then
    echo "❌ Frontend package.json not found."
    exit 1
fi

echo "✅ All prerequisites found!"

# For macOS (using osascript to open new Terminal tabs)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🍎 macOS detected - opening Terminal tabs..."
    
    # Backend terminal
    osascript -e "
    tell application \"Terminal\"
        do script \"cd $(pwd) && echo '🔧 Backend Terminal - Starting services...' && source venv/bin/activate && echo '✅ Virtual environment activated' && echo '🚀 Starting backend services...' && ./start_backend_services.sh\"
    end tell"
    
    # Frontend terminal  
    osascript -e "
    tell application \"Terminal\"
        do script \"cd $(pwd)/../Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend && echo '🎨 Frontend Terminal - Setting up...' && echo '📍 Changed to frontend directory' && source ~/.nvm/nvm.sh && nvm use v20 && echo '✅ Node v20 activated' && echo '🚀 Starting frontend dev server...' && npm run dev\"
    end tell"
    
    echo "✅ Terminals opened! Check your Terminal application."
    
# For Linux (using gnome-terminal or xterm)
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "🐧 Linux detected - opening terminal tabs..."
    
    if command_exists gnome-terminal; then
        # Backend terminal
        gnome-terminal --tab --title="🔧 Backend" -- bash -c "
        echo '🔧 Backend Terminal - Starting services...'
        source venv/bin/activate
        echo '✅ Virtual environment activated'
        echo '🚀 Starting backend services...'
        ./start_backend_services.sh
        exec bash"
        
        # Frontend terminal
        gnome-terminal --tab --title="🎨 Frontend" -- bash -c "
        cd ../Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend
        echo '🎨 Frontend Terminal - Setting up...'
        echo '📍 Changed to frontend directory'
        source ~/.nvm/nvm.sh
        nvm use v20
        echo '✅ Node v20 activated'
        echo '🚀 Starting frontend dev server...'
        npm run dev
        exec bash"
    else
        echo "🖥️ Please install gnome-terminal or use the Cursor tasks instead."
    fi
    
else
    echo "🖥️ Unsupported OS. Please use the Cursor tasks instead."
fi

echo ""
echo "🎯 Alternative: Use Cursor Tasks"
echo "   1. Open Cursor: cursor dharsan-voice-agent.code-workspace"
echo "   2. Press Ctrl+Shift+P"  
echo "   3. Type 'Tasks: Run Task'"
echo "   4. Select '📱 Open Development Terminals'"
echo ""
echo "🔧 Manual Commands:"
echo "   Backend:  source venv/bin/activate && ./start_backend_services.sh"
echo "   Frontend: cd ../Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend && nvm use v20 && npm run dev"
echo ""
echo "🎉 Development environment setup complete!"