#!/bin/bash

# Update LLM Service with Thinking Tag Fix
# This script updates the LLM service deployment with the new image that removes thinking tags

set -e

echo "🔧 Updating LLM Service with Thinking Tag Fix..."

# Update the LLM service deployment with new image
kubectl patch deployment llm-service -n voice-agent-phase5 -p '
{
  "spec": {
    "template": {
      "spec": {
        "containers": [
          {
            "name": "llm-service",
            "image": "gcr.io/speechtotext-466820/llm-service:latest"
          }
        ]
      }
    }
  }
}'

echo "✅ Updated LLM service deployment with new image"

# Force restart the LLM service deployment
kubectl rollout restart deployment/llm-service -n voice-agent-phase5

echo "🔄 Restarting LLM service deployment..."

# Wait for the deployment to be ready
echo "⏳ Waiting for LLM service to be ready..."
kubectl rollout status deployment/llm-service -n voice-agent-phase5 --timeout=300s

echo "✅ LLM service deployment updated successfully!"

# Show the current pods
echo "📋 Current LLM service pods:"
kubectl get pods -n voice-agent-phase5 -l app=llm-service

# Show the deployment details
echo "📋 LLM service deployment details:"
kubectl describe deployment llm-service -n voice-agent-phase5

echo ""
echo "🎉 LLM Service Thinking Tag Fix Deployed!"
echo ""
echo "The LLM service now:"
echo "- Uses updated system prompt that explicitly forbids thinking tags"
echo "- Includes post-processing to remove any thinking tags from responses"
echo "- Provides clean, spoken responses without internal reasoning"
echo ""
echo "Test the voice agent at: https://dharsan-voiceagent-frontend-o07k2nnvx-dharsan-kumars-projects.vercel.app/v2/phase5?production=true" 