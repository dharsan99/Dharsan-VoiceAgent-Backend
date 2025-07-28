#!/bin/bash
# deploy.sh - Deployment script for Voice AI Backend

set -e

echo "🚀 Voice AI Backend Deployment Script"
echo "====================================="

# Check if Modal CLI is installed
if ! command -v modal &> /dev/null; then
    echo "❌ Modal CLI is not installed. Please install it first:"
    echo "   pip install modal"
    echo "   modal token new"
    exit 1
fi

# Check if user is authenticated by trying to list secrets
if ! modal secret list &> /dev/null; then
    echo "❌ Not authenticated with Modal. Please run:"
    echo "   modal token new"
    exit 1
fi

echo "✅ Modal CLI is installed and authenticated"

# Function to create secrets
create_secrets() {
    echo "🔐 Setting up API secrets..."
    
    # Check if secrets already exist
    if modal secret list 2>/dev/null | grep -q "deepgram-secret"; then
        echo "⚠️  deepgram-secret already exists. Skipping..."
    else
        echo "Creating deepgram-secret..."
        modal secret create deepgram-secret DEEPGRAM_API_KEY="key"
    fi
    
    if modal secret list 2>/dev/null | grep -q "groq-secret"; then
        echo "⚠️  groq-secret already exists. Skipping..."
    else
        echo "Creating groq-secret..."
        modal secret create groq-secret GROQ_API_KEY="key"
    fi
    
    if modal secret list 2>/dev/null | grep -q "elevenlabs-secret"; then
        echo "⚠️  elevenlabs-secret already exists. Skipping..."
    else
        echo "Creating elevenlabs-secret..."
        modal secret create elevenlabs-secret ELEVENLABS_API_KEY="key"
    fi
    
    echo "✅ Secrets configured"
}

# Function to deploy the application
deploy_app() {
    echo "🚀 Deploying Voice AI Backend to Modal..."
    
    # Deploy the application
    modal deploy main.py
    
    echo "✅ Deployment completed!"
    echo ""
    echo "📋 Next steps:"
    echo "1. Copy the WebSocket URL from the deployment output"
    echo "2. Update your frontend environment variables"
    echo "3. Test the connection"
}

# Function to view logs
view_logs() {
    echo "📋 Viewing application logs..."
    modal logs voice-ai-backend
}

# Function to list secrets
list_secrets() {
    echo "🔐 Current secrets:"
    modal secret list 2>/dev/null || echo "No secrets found or error listing secrets"
}

# Function to test the deployment
test_deployment() {
    echo "🧪 Testing deployment..."
    
    # Get the app URL
    APP_URL=$(modal app list 2>/dev/null | grep voice-ai-backend | awk '{print $2}')
    
    if [ -z "$APP_URL" ]; then
        echo "❌ Could not find app URL. Is the app deployed?"
        return 1
    fi
    
    echo "Testing health endpoint: $APP_URL/health"
    curl -s "$APP_URL/health" | jq . || echo "Health check failed"
    
    echo "Testing root endpoint: $APP_URL/"
    curl -s "$APP_URL/" | jq . || echo "Root endpoint failed"
}

# Main script logic
case "${1:-deploy}" in
    "setup")
        create_secrets
        ;;
    "deploy")
        deploy_app
        ;;
    "logs")
        view_logs
        ;;
    "secrets")
        list_secrets
        ;;
    "test")
        test_deployment
        ;;
    "full")
        create_secrets
        deploy_app
        test_deployment
        ;;
    *)
        echo "Usage: $0 {setup|deploy|logs|secrets|test|full}"
        echo ""
        echo "Commands:"
        echo "  setup   - Create API secrets"
        echo "  deploy  - Deploy the application"
        echo "  logs    - View application logs"
        echo "  secrets - List current secrets"
        echo "  test    - Test the deployment"
        echo "  full    - Run setup, deploy, and test"
        exit 1
        ;;
esac 