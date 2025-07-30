#!/bin/bash

# Fresh GKE Deployment Script for Voice Agent System
# This script creates a new cluster and deploys all services from scratch

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="speechtotext-466820"
REGION="us-central1"
CLUSTER_NAME="voice-agent-fresh"
REGISTRY_NAME="voice-agent-repo"
NAMESPACE="voice-agent-fresh"
VERSION="v2.0.0"

# Derived values
REGISTRY_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REGISTRY_NAME}"

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}🚀 $1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_step() {
    echo -e "${CYAN}📋 $1${NC}"
}

# Function to check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed. Please install it first."
        exit 1
    fi
    
    # Check if docker is installed
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    # Check if buildx is available
    if ! docker buildx version &> /dev/null; then
        print_error "Docker buildx is not available. Please update Docker."
        exit 1
    fi
    
    # Setup Docker buildx for cross-platform builds (ARM -> AMD64)
    print_step "Setting up Docker buildx for cross-platform builds..."
    docker buildx create --name multiplatform --use --bootstrap || docker buildx use multiplatform || true
    docker buildx inspect --bootstrap
    
    print_status "All prerequisites met"
}

# Function to configure gcloud
configure_gcloud() {
    print_header "Configuring gcloud"
    
    print_step "Setting project to: $PROJECT_ID"
    gcloud config set project "$PROJECT_ID"
    
    print_step "Setting region to: $REGION"
    gcloud config set compute/region "$REGION"
    
    print_step "Enabling required APIs..."
    gcloud services enable \
        container.googleapis.com \
        artifactregistry.googleapis.com \
        compute.googleapis.com \
        cloudbuild.googleapis.com
    
    print_status "gcloud configured"
}

# Function to setup Artifact Registry
setup_artifact_registry() {
    print_header "Setting up Artifact Registry"
    
    # Check if repository exists
    if gcloud artifacts repositories describe "$REGISTRY_NAME" \
        --location="$REGION" &> /dev/null; then
        print_warning "Artifact Registry repository already exists"
    else
        print_step "Creating Artifact Registry repository..."
        gcloud artifacts repositories create "$REGISTRY_NAME" \
            --repository-format=docker \
            --location="$REGION" \
            --description="Voice Agent Docker images"
    fi
    
    print_step "Configuring Docker authentication..."
    gcloud auth configure-docker "${REGION}-docker.pkg.dev"
    
    print_status "Artifact Registry configured"
}

# Function to create GKE cluster
create_gke_cluster() {
    print_header "Creating GKE Cluster"
    
    # Check if cluster already exists
    if gcloud container clusters describe "$CLUSTER_NAME" --region="$REGION" &> /dev/null; then
        print_warning "Cluster $CLUSTER_NAME already exists. Skipping creation."
    else
        print_step "Creating GKE cluster: $CLUSTER_NAME"
        
        gcloud container clusters create "$CLUSTER_NAME" \
            --region="$REGION" \
            --machine-type="e2-standard-4" \
            --num-nodes=2 \
            --min-nodes=1 \
            --max-nodes=5 \
            --enable-autoscaling \
            --enable-autorepair \
            --enable-autoupgrade \
            --disk-size=50GB \
            --disk-type=pd-standard \
            --image-type=COS_CONTAINERD \
            --enable-ip-alias \
            --network=default \
            --subnetwork=default \
            --logging=SYSTEM \
            --monitoring=SYSTEM \
            --enable-network-policy \
            --addons=HorizontalPodAutoscaling,HttpLoadBalancing \
            --workload-pool="${PROJECT_ID}.svc.id.goog"
    fi
    
    print_step "Getting cluster credentials..."
    gcloud container clusters get-credentials "$CLUSTER_NAME" --region="$REGION"
    
    print_status "GKE cluster ready"
}

# Function to build Docker images
build_docker_images() {
    print_header "Building Docker Images"
    
    # Array of services to build
    declare -a services=("orchestrator" "media-server" "stt-service" "tts-service" "llm-service")
    
    for service in "${services[@]}"; do
        print_step "Building $service..."
        
        cd "v2/$service"
        
        # Use different Dockerfile for LLM service to fix ollama issue
        if [[ "$service" == "llm-service" ]]; then
            # Create a fixed Dockerfile for LLM service with proper Python environment
            cat > Dockerfile.fixed << 'EOF'
FROM ollama/ollama:latest

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-full \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies in virtual environment
COPY requirements.txt .

# Create virtual environment and install packages
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create startup script that ensures ollama is available
RUN cat > start.sh << 'SCRIPT'
#!/bin/bash
# Activate virtual environment
source /opt/venv/bin/activate

# Start Ollama server in background
ollama serve &
SERVER_PID=$!

# Wait for server to be ready
sleep 10

# Pull model if not exists
if ! ollama list | grep -q "qwen3:0.6b"; then
    echo "Pulling qwen3:0.6b model..."
    ollama pull qwen3:0.6b
fi

# Start Python service
exec python main.py
SCRIPT

RUN chmod +x start.sh

EXPOSE 11434

CMD ["./start.sh"]
EOF
            dockerfile_flag="--file Dockerfile.fixed"
        else
            dockerfile_flag=""
        fi
        
        # Build for AMD64 platform (GKE requirement) - Cross-compile from ARM
        echo "Cross-compiling $service for AMD64 platform..."
        
        # Ensure buildx builder supports multi-platform
        docker buildx create --name multiplatform --use --bootstrap || true
        
        docker buildx build \
            --platform linux/amd64 \
            $dockerfile_flag \
            --tag "${REGISTRY_PATH}/${service}:${VERSION}" \
            --tag "${REGISTRY_PATH}/${service}:latest" \
            --push \
            --progress=plain \
            .
        
        print_status "$service image built and pushed"
        cd ../..
    done
    
    print_status "All Docker images built and pushed"
}

# Function to create Kubernetes manifests
create_k8s_manifests() {
    print_header "Creating Kubernetes Manifests"
    
    # Create manifests directory
    mkdir -p "k8s-fresh/manifests"
    
    print_step "Creating namespace manifest..."
    cat > k8s-fresh/manifests/namespace.yaml << EOF
apiVersion: v1
kind: Namespace
metadata:
  name: ${NAMESPACE}
  labels:
    name: ${NAMESPACE}
    app: voice-agent
EOF

    print_step "Creating persistent volume claims..."
    cat > k8s-fresh/manifests/pvcs.yaml << EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: stt-model-storage-pvc
  namespace: ${NAMESPACE}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
  storageClassName: standard-rwo
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: tts-model-storage-pvc
  namespace: ${NAMESPACE}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 2Gi
  storageClassName: standard-rwo
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ollama-model-storage-pvc
  namespace: ${NAMESPACE}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: standard-rwo
EOF

    print_step "Creating Redpanda (Kafka) deployment..."
    cat > k8s-fresh/manifests/redpanda.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redpanda
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redpanda
  template:
    metadata:
      labels:
        app: redpanda
    spec:
      containers:
      - name: redpanda
        image: vectorized/redpanda:latest
        ports:
        - containerPort: 9092
        - containerPort: 9644
        command:
        - /usr/bin/rpk
        - redpanda
        - start
        - --smp
        - "1"
        - --memory
        - "1G"
        - --reserve-memory
        - "0M"
        - --node-id
        - "0"
        - --kafka-addr
        - "0.0.0.0:9092"
        - --advertise-kafka-addr
        - "redpanda:9092"
        - --pandaproxy-addr
        - "0.0.0.0:8082"
        - --advertise-pandaproxy-addr
        - "redpanda:8082"
        - --schema-registry-addr
        - "0.0.0.0:8081"
        - --rpc-addr
        - "0.0.0.0:33145"
        - --advertise-rpc-addr
        - "redpanda:33145"
        - --mode
        - "dev-container"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: redpanda
  namespace: ${NAMESPACE}
spec:
  selector:
    app: redpanda
  ports:
  - name: kafka
    port: 9092
    targetPort: 9092
  - name: admin
    port: 9644
    targetPort: 9644
EOF

    # Create deployment for each service
    declare -a services=("orchestrator" "media-server" "stt-service" "tts-service" "llm-service")
    
    for service in "${services[@]}"; do
        print_step "Creating $service deployment..."
        
        # Service-specific configurations
        case $service in
            "orchestrator")
                port=8001
                resources_req_cpu="200m"
                resources_req_mem="256Mi"
                resources_lim_cpu="500m"
                resources_lim_mem="512Mi"
                pvc_mount=""
                ;;
            "media-server")
                port=8080
                resources_req_cpu="200m"
                resources_req_mem="256Mi"
                resources_lim_cpu="500m"
                resources_lim_mem="512Mi"
                pvc_mount=""
                ;;
            "stt-service")
                port=8000
                resources_req_cpu="500m"
                resources_req_mem="1Gi"
                resources_lim_cpu="1"
                resources_lim_mem="2Gi"
                pvc_mount="        volumeMounts:
        - name: model-storage
          mountPath: /models
      volumes:
      - name: model-storage
        persistentVolumeClaim:
          claimName: stt-model-storage-pvc"
                ;;
            "tts-service")
                port=5000
                resources_req_cpu="200m"
                resources_req_mem="512Mi"
                resources_lim_cpu="500m"
                resources_lim_mem="1Gi"
                pvc_mount="        volumeMounts:
        - name: model-storage
          mountPath: /models
      volumes:
      - name: model-storage
        persistentVolumeClaim:
          claimName: tts-model-storage-pvc"
                ;;
            "llm-service")
                port=11434
                resources_req_cpu="500m"
                resources_req_mem="1Gi"
                resources_lim_cpu="1"
                resources_lim_mem="2Gi"
                pvc_mount="        volumeMounts:
        - name: ollama-storage
          mountPath: /root/.ollama
      volumes:
      - name: ollama-storage
        persistentVolumeClaim:
          claimName: ollama-model-storage-pvc"
                ;;
        esac
        
        cat > "k8s-fresh/manifests/${service}.yaml" << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${service}
  namespace: ${NAMESPACE}
  labels:
    app: ${service}
    version: ${VERSION}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ${service}
  template:
    metadata:
      labels:
        app: ${service}
    spec:
      containers:
      - name: ${service}
        image: ${REGISTRY_PATH}/${service}:${VERSION}
        ports:
        - containerPort: ${port}
        resources:
          requests:
            memory: "${resources_req_mem}"
            cpu: "${resources_req_cpu}"
          limits:
            memory: "${resources_lim_mem}"
            cpu: "${resources_lim_cpu}"
        livenessProbe:
          httpGet:
            path: /health
            port: ${port}
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: ${port}
          initialDelaySeconds: 5
          periodSeconds: 5
${pvc_mount}
---
apiVersion: v1
kind: Service
metadata:
  name: ${service}
  namespace: ${NAMESPACE}
spec:
  selector:
    app: ${service}
  ports:
  - port: ${port}
    targetPort: ${port}
  type: ClusterIP
EOF
    done
    
    # Create LoadBalancer services for external access
    print_step "Creating external LoadBalancer services..."
    cat > k8s-fresh/manifests/loadbalancers.yaml << EOF
apiVersion: v1
kind: Service
metadata:
  name: orchestrator-lb
  namespace: ${NAMESPACE}
spec:
  selector:
    app: orchestrator
  ports:
  - port: 8001
    targetPort: 8001
  type: LoadBalancer
---
apiVersion: v1
kind: Service
metadata:
  name: media-server-lb
  namespace: ${NAMESPACE}
spec:
  selector:
    app: media-server
  ports:
  - port: 8080
    targetPort: 8080
    name: http
  - port: 10000
    targetPort: 10000
    protocol: UDP
    name: rtp
  type: LoadBalancer
EOF

    print_status "Kubernetes manifests created"
}

# Function to deploy to Kubernetes
deploy_to_kubernetes() {
    print_header "Deploying to Kubernetes"
    
    print_step "Creating namespace..."
    kubectl apply -f k8s-fresh/manifests/namespace.yaml
    
    print_step "Creating persistent volume claims..."
    kubectl apply -f k8s-fresh/manifests/pvcs.yaml
    
    print_step "Deploying Redpanda..."
    kubectl apply -f k8s-fresh/manifests/redpanda.yaml
    
    print_step "Waiting for Redpanda to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment/redpanda -n ${NAMESPACE}
    
    print_step "Deploying services..."
    declare -a services=("orchestrator" "media-server" "stt-service" "tts-service" "llm-service")
    
    for service in "${services[@]}"; do
        print_step "Deploying $service..."
        kubectl apply -f "k8s-fresh/manifests/${service}.yaml"
    done
    
    print_step "Creating LoadBalancer services..."
    kubectl apply -f k8s-fresh/manifests/loadbalancers.yaml
    
    print_status "All services deployed"
}

# Function to verify deployment
verify_deployment() {
    print_header "Verifying Deployment"
    
    print_step "Waiting for all deployments to be ready..."
    kubectl wait --for=condition=available --timeout=600s deployment/orchestrator -n ${NAMESPACE}
    kubectl wait --for=condition=available --timeout=600s deployment/media-server -n ${NAMESPACE}
    kubectl wait --for=condition=available --timeout=600s deployment/stt-service -n ${NAMESPACE}
    kubectl wait --for=condition=available --timeout=600s deployment/tts-service -n ${NAMESPACE}
    kubectl wait --for=condition=available --timeout=600s deployment/llm-service -n ${NAMESPACE}
    
    print_step "Getting pod status..."
    kubectl get pods -n ${NAMESPACE}
    
    print_step "Getting service status..."
    kubectl get services -n ${NAMESPACE}
    
    print_step "Getting external IPs..."
    echo "Waiting for LoadBalancer IPs to be assigned..."
    sleep 30
    kubectl get services -n ${NAMESPACE} -o wide
    
    print_status "Deployment verification complete"
}

# Main execution
main() {
    print_header "Fresh GKE Deployment for Voice Agent"
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    echo "Cluster: $CLUSTER_NAME"
    echo "Namespace: $NAMESPACE"
    echo "Version: $VERSION"
    echo ""
    
    check_prerequisites
    configure_gcloud
    setup_artifact_registry
    create_gke_cluster
    build_docker_images
    create_k8s_manifests
    deploy_to_kubernetes
    verify_deployment
    
    print_header "🎉 Deployment Complete!"
    echo -e "${GREEN}Your fresh Voice Agent system is now deployed!${NC}"
    echo ""
    echo "To get external IPs:"
    echo "kubectl get services -n ${NAMESPACE}"
    echo ""
    echo "To check logs:"
    echo "kubectl logs -f deployment/orchestrator -n ${NAMESPACE}"
    echo ""
    echo "To access the cluster later:"
    echo "gcloud container clusters get-credentials ${CLUSTER_NAME} --region=${REGION}"
}

# Run main function
main "$@"