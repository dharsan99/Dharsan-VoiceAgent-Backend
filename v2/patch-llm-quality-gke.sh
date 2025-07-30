#!/bin/bash

# Patch LLM Quality Fix to GKE
# This script updates the orchestrator deployment with the new image and improved system prompt

set -e

echo "🔧 Patching LLM Quality Fix to GKE..."

# Create ConfigMap with improved system prompt
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: llm-system-prompt
  namespace: voice-agent-phase5
data:
  system-prompt: |
    You are a helpful voice assistant. Keep your responses concise and natural for voice interaction.

    IMPORTANT GUIDELINES:
    1. When users greet you (like "Hello", "Hi", "Can you hear me?"), acknowledge their greeting and confirm you can hear them, then offer help.
    2. When users ask if you can hear them, respond with "Yes, I can hear you perfectly" or similar.
    3. Keep responses under 100 words and conversational.
    4. Avoid repeating the user's question back to them.
    5. Be helpful and offer assistance when appropriate.
    6. Use a friendly, natural tone that sounds good when spoken aloud.

    Example responses:
    - User: "Hello, hi, can you hear me?" → "Hello! Yes, I can hear you perfectly. How can I help you today?"
    - User: "Hi there" → "Hi! I'm here and ready to help. What would you like to know?"
    - User: "Can you hear me?" → "Yes, I can hear you clearly. How can I assist you?"
EOF

echo "✅ Created ConfigMap with improved system prompt"

# Update the orchestrator deployment with new image and environment variable
kubectl patch deployment orchestrator -n voice-agent-phase5 -p '
{
  "spec": {
    "template": {
      "spec": {
        "containers": [
          {
            "name": "orchestrator",
            "image": "gcr.io/speechtotext-466820/orchestrator:latest",
            "env": [
              {
                "name": "SYSTEM_PROMPT",
                "valueFrom": {
                  "configMapKeyRef": {
                    "name": "llm-system-prompt",
                    "key": "system-prompt"
                  }
                }
              }
            ]
          }
        ]
      }
    }
  }
}'

echo "✅ Updated orchestrator deployment with new image and system prompt"

# Force restart the orchestrator deployment
kubectl rollout restart deployment/orchestrator -n voice-agent-phase5

echo "🔄 Restarting orchestrator deployment..."

# Wait for the deployment to be ready
echo "⏳ Waiting for orchestrator to be ready..."
kubectl rollout status deployment/orchestrator -n voice-agent-phase5 --timeout=300s

echo "✅ Orchestrator deployment updated successfully!"

# Show the current pods
echo "📋 Current orchestrator pods:"
kubectl get pods -n voice-agent-phase5 -l app=orchestrator

# Show the deployment details
echo "📋 Orchestrator deployment details:"
kubectl describe deployment orchestrator -n voice-agent-phase5

echo ""
echo "🎉 LLM Response Quality Fix Deployed to GKE!"
echo ""
echo "The orchestrator now uses:"
echo "- New image: gcr.io/speechtotext-466820/orchestrator:latest"
echo "- Improved system prompt from ConfigMap"
echo "- Better response handling for greetings and confirmations"
echo ""
echo "Test the voice agent at: https://dharsan-voiceagent-frontend-o07k2nnvx-dharsan-kumars-projects.vercel.app/v2/phase5?production=true" 