#!/bin/bash

# Deploy Session ID Fixes
# This script deploys the updated orchestrator and media server with session ID fixes

set -e

echo "🚀 Deploying Session ID Fixes..."

# Check if we're in the right directory
if [ ! -f "v2/orchestrator/main.go" ]; then
    echo "❌ Error: Please run this script from the Dharsan-VoiceAgent-Backend directory"
    exit 1
fi

# Build the updated images
echo "📦 Building updated images..."

echo "Building orchestrator..."
cd v2/orchestrator
docker build -t voice-agent-orchestrator:session-fixes .
cd ../..

echo "Building media server..."
cd v2/media-server
docker build -t voice-agent-media-server:session-fixes .
cd ../..

# Create a temporary deployment manifest for testing
echo "📝 Creating deployment manifests..."

cat > temp-orchestrator-deployment.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orchestrator-session-fixes
  namespace: voice-agent-phase5
  labels:
    app: orchestrator-session-fixes
    component: orchestration
    phase: "5"
    version: "5.0.1"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: orchestrator-session-fixes
      component: orchestration
  template:
    metadata:
      labels:
        app: orchestrator-session-fixes
        component: orchestration
        phase: "5"
        version: "5.0.1"
    spec:
      containers:
        - name: orchestrator
          image: voice-agent-orchestrator:session-fixes
          imagePullPolicy: Never
          ports:
            - containerPort: 8001
              name: http
          env:
            - name: STT_SERVICE_URL
              value: "http://stt-service.voice-agent-phase5.svc.cluster.local:8000"
            - name: TTS_SERVICE_URL
              value: "http://tts-service.voice-agent-phase5.svc.cluster.local:8000"
            - name: LLM_SERVICE_URL
              value: "http://llm-service.voice-agent-phase5.svc.cluster.local:11434"
            - name: LLM_ENDPOINT
              value: "http://llm-service.voice-agent-phase5.svc.cluster.local:11434/api/generate"
            - name: LLM_MODEL_NAME
              value: "qwen3:0.6b"
            - name: REDPANDA_HOST
              value: "redpanda.voice-agent-phase5.svc.cluster.local"
            - name: REDPANDA_PORT
              value: "9092"
          resources:
            requests:
              cpu: "200m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "1Gi"
          livenessProbe:
            httpGet:
              path: /health
              port: 8001
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health
              port: 8001
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: orchestrator-session-fixes
  namespace: voice-agent-phase5
  labels:
    app: orchestrator-session-fixes
    component: orchestration
    phase: "5"
    version: "5.0.1"
spec:
  type: ClusterIP
  ports:
    - port: 8001
      targetPort: 8001
      name: http
  selector:
    app: orchestrator-session-fixes
    component: orchestration
EOF

cat > temp-media-server-deployment.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: media-server-session-fixes
  namespace: voice-agent-phase5
  labels:
    app: media-server-session-fixes
    component: media
    phase: "5"
    version: "5.0.1"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: media-server-session-fixes
      component: media
  template:
    metadata:
      labels:
        app: media-server-session-fixes
        component: media
        phase: "5"
        version: "5.0.1"
    spec:
      containers:
        - name: media-server
          image: voice-agent-media-server:session-fixes
          imagePullPolicy: Never
          ports:
            - containerPort: 8080
              name: http
          env:
            - name: REDPANDA_HOST
              value: "redpanda.voice-agent-phase5.svc.cluster.local"
            - name: REDPANDA_PORT
              value: "9092"
          resources:
            requests:
              cpu: "200m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "1Gi"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: media-server-session-fixes
  namespace: voice-agent-phase5
  labels:
    app: media-server-session-fixes
    component: media
    phase: "5"
    version: "5.0.1"
spec:
  type: ClusterIP
  ports:
    - port: 8080
      targetPort: 8080
      name: http
  selector:
    app: media-server-session-fixes
    component: media
EOF

echo "🔧 Applying deployment manifests..."

# Apply the new deployments
kubectl apply -f temp-orchestrator-deployment.yaml
kubectl apply -f temp-media-server-deployment.yaml

echo "⏳ Waiting for deployments to be ready..."

# Wait for deployments to be ready
kubectl rollout status deployment/orchestrator-session-fixes -n voice-agent-phase5 --timeout=300s
kubectl rollout status deployment/media-server-session-fixes -n voice-agent-phase5 --timeout=300s

echo "✅ Session ID fixes deployed successfully!"

echo "📊 Checking deployment status..."
kubectl get pods -n voice-agent-phase5 | grep session-fixes

echo ""
echo "🎯 Next steps:"
echo "1. Test the new services with session ID fixes"
echo "2. Monitor logs for session ID validation warnings"
echo "3. Verify that session tracking works correctly"
echo ""
echo "To check logs:"
echo "kubectl logs -f deployment/orchestrator-session-fixes -n voice-agent-phase5"
echo "kubectl logs -f deployment/media-server-session-fixes -n voice-agent-phase5"

# Clean up temporary files
rm -f temp-orchestrator-deployment.yaml temp-media-server-deployment.yaml 