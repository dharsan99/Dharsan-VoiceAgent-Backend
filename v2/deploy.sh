#!/bin/bash

# Voice AI Backend v2.0 Deployment Script

echo "🚀 Deploying Voice AI Backend v2.0..."

# Check if we're in the v2 directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Please run this script from the v2 directory"
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
echo "📥 Installing dependencies..."
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

# Deploy to Modal
echo "🚀 Deploying to Modal..."
modal deploy main.py

echo "✅ Deployment complete!"
echo "📊 Check your deployment at: https://modal.com/apps"
echo "🔗 WebSocket endpoint: wss://your-app.modal.run/ws/v2"
echo "📚 API documentation: https://your-app.modal.run/docs" 