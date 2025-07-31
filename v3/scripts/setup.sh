#!/bin/bash

# Dharsan Voice Agent V3 - Setup Script
# This script sets up the complete v3 backend environment

set -e

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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check system requirements
check_requirements() {
    print_status "Checking system requirements..."
    
    # Check Python
    if ! command_exists python3; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi
    
    # Check Go
    if ! command_exists go; then
        print_error "Go is required but not installed"
        exit 1
    fi
    
    # Check Docker
    if ! command_exists docker; then
        print_error "Docker is required but not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command_exists docker-compose; then
        print_error "Docker Compose is required but not installed"
        exit 1
    fi
    
    # Check NVIDIA Docker (optional)
    if command_exists nvidia-docker; then
        print_success "NVIDIA Docker detected - GPU acceleration available"
    else
        print_warning "NVIDIA Docker not found - GPU acceleration may not work"
    fi
    
    print_success "System requirements check passed"
}

# Function to create directory structure
create_directories() {
    print_status "Creating directory structure..."
    
    # Create necessary directories
    mkdir -p logs
    mkdir -p models/{asr,nlp,tts,optimization}
    mkdir -p config/{nginx,prometheus,grafana,logstash}
    mkdir -p shared/{proto,config,utils,bentoml}
    mkdir -p tests/{e2e,performance,load,model}
    mkdir -p docs/{api,deployment,model-optimization,handoff-protocol,troubleshooting}
    
    print_success "Directory structure created"
}

# Function to setup Python virtual environment
setup_python_env() {
    print_status "Setting up Python virtual environment..."
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_success "Virtual environment created"
    else
        print_warning "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install Python dependencies
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        print_success "Python dependencies installed"
    else
        print_warning "requirements.txt not found - skipping Python dependencies"
    fi
}

# Function to setup Go modules
setup_go_modules() {
    print_status "Setting up Go modules..."
    
    # Initialize Go modules for each service
    for service in orchestrator media-server handoff-service logging-service; do
        if [ -d "services/$service" ]; then
            cd "services/$service"
            if [ ! -f "go.mod" ]; then
                go mod init "voice-agent/$service"
                print_success "Go module initialized for $service"
            fi
            go mod tidy
            cd ../..
        fi
    done
    
    print_success "Go modules setup completed"
}

# Function to download and optimize models
download_models() {
    print_status "Downloading and optimizing models..."
    
    # Create models directory if it doesn't exist
    mkdir -p models
    
    # Download ASR model (NVIDIA Parakeet TDT)
    if [ ! -d "models/asr/parakeet-tdt-0.6b-v2" ]; then
        print_status "Downloading NVIDIA Parakeet TDT model..."
        mkdir -p models/asr
        # Note: This would require proper model download logic
        # For now, we'll create a placeholder
        echo "Model download placeholder - implement actual download logic" > models/asr/README.md
        print_warning "ASR model download not implemented - manual download required"
    fi
    
    # Download NLP model (Super Tiny LM)
    if [ ! -d "models/nlp/smol-lm-1.7b-finetuned" ]; then
        print_status "Downloading Super Tiny LM model..."
        mkdir -p models/nlp
        # Note: This would require proper model download logic
        echo "Model download placeholder - implement actual download logic" > models/nlp/README.md
        print_warning "NLP model download not implemented - manual download required"
    fi
    
    # Download TTS model (Zonos)
    if [ ! -d "models/tts/zonos-v0.1-hybrid" ]; then
        print_status "Downloading Zonos TTS model..."
        mkdir -p models/tts
        # Note: This would require proper model download logic
        echo "Model download placeholder - implement actual download logic" > models/tts/README.md
        print_warning "TTS model download not implemented - manual download required"
    fi
    
    print_success "Model directories created"
}

# Function to optimize models
optimize_models() {
    print_status "Optimizing models..."
    
    # Check if CUDA is available
    if command_exists nvidia-smi; then
        print_status "CUDA detected - applying optimizations..."
        
        # Apply INT8 quantization
        if [ -f "scripts/model-optimization.sh" ]; then
            chmod +x scripts/model-optimization.sh
            ./scripts/model-optimization.sh
        else
            print_warning "Model optimization script not found"
        fi
    else
        print_warning "CUDA not detected - skipping GPU optimizations"
    fi
    
    print_success "Model optimization completed"
}

# Function to setup configuration files
setup_config() {
    print_status "Setting up configuration files..."
    
    # Copy environment file if it doesn't exist
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            print_success "Environment file created from template"
            print_warning "Please edit .env file with your specific configuration"
        else
            print_warning ".env.example not found - manual environment setup required"
        fi
    fi
    
    # Create basic configuration files
    mkdir -p config/nginx
    cat > config/nginx/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream orchestrator {
        server orchestrator:8081;
    }
    
    upstream media-server {
        server media-server:8082;
    }
    
    upstream stt-service {
        server stt-service:8085;
    }
    
    upstream nlp-service {
        server nlp-service:8086;
    }
    
    upstream tts-service {
        server tts-service:8087;
    }
    
    upstream handoff-service {
        server handoff-service:8088;
    }
    
    server {
        listen 80;
        
        location /api/v1/orchestrator/ {
            proxy_pass http://orchestrator/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        
        location /api/v1/media/ {
            proxy_pass http://media-server/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        
        location /api/v1/stt/ {
            proxy_pass http://stt-service/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        
        location /api/v1/nlp/ {
            proxy_pass http://nlp-service/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        
        location /api/v1/tts/ {
            proxy_pass http://tts-service/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        
        location /api/v1/handoff/ {
            proxy_pass http://handoff-service/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
EOF
    
    # Create Prometheus configuration
    mkdir -p config/prometheus
    cat > config/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'orchestrator'
    static_configs:
      - targets: ['orchestrator:8081']
  
  - job_name: 'media-server'
    static_configs:
      - targets: ['media-server:8082']
  
  - job_name: 'stt-service'
    static_configs:
      - targets: ['stt-service:8085']
  
  - job_name: 'nlp-service'
    static_configs:
      - targets: ['nlp-service:8086']
  
  - job_name: 'tts-service'
    static_configs:
      - targets: ['tts-service:8087']
  
  - job_name: 'handoff-service'
    static_configs:
      - targets: ['handoff-service:8088']
EOF
    
    print_success "Configuration files created"
}

# Function to setup monitoring
setup_monitoring() {
    print_status "Setting up monitoring configuration..."
    
    # Create Grafana datasources
    mkdir -p config/grafana/datasources
    cat > config/grafana/datasources/prometheus.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
EOF
    
    # Create Logstash configuration
    mkdir -p config/logstash
    cat > config/logstash/logstash.conf << 'EOF'
input {
  beats {
    port => 5044
  }
}

filter {
  if [fields][service] {
    mutate {
      add_field => { "service" => "%{[fields][service]}" }
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "voice-agent-v3-%{+YYYY.MM.dd}"
  }
}
EOF
    
    print_success "Monitoring configuration created"
}

# Function to build Docker images
build_images() {
    print_status "Building Docker images..."
    
    # Build all services
    docker-compose build
    
    print_success "Docker images built successfully"
}

# Function to start services
start_services() {
    print_status "Starting services..."
    
    # Start infrastructure services first
    docker-compose up -d zookeeper kafka redis scylladb minio
    
    # Wait for infrastructure to be ready
    print_status "Waiting for infrastructure services to be ready..."
    sleep 30
    
    # Start monitoring services
    docker-compose up -d prometheus grafana jaeger elasticsearch logstash kibana
    
    # Wait for monitoring to be ready
    print_status "Waiting for monitoring services to be ready..."
    sleep 30
    
    # Start core services
    docker-compose up -d orchestrator media-server stt-service nlp-service tts-service handoff-service logging-service
    
    # Start API gateway
    docker-compose up -d api-gateway
    
    print_success "All services started successfully"
}

# Function to check service health
check_health() {
    print_status "Checking service health..."
    
    # Wait a bit for services to start
    sleep 10
    
    # Check if services are responding
    services=(
        "http://localhost:8081/health"
        "http://localhost:8082/health"
        "http://localhost:8085/health"
        "http://localhost:8086/health"
        "http://localhost:8087/health"
        "http://localhost:8088/health"
    )
    
    for service in "${services[@]}"; do
        if curl -f -s "$service" > /dev/null; then
            print_success "Service $service is healthy"
        else
            print_warning "Service $service is not responding"
        fi
    done
    
    print_success "Health check completed"
}

# Function to display next steps
display_next_steps() {
    echo ""
    echo "=========================================="
    echo "🎉 V3 Setup Completed Successfully!"
    echo "=========================================="
    echo ""
    echo "📊 Monitoring Dashboards:"
    echo "  - Grafana: http://localhost:3000 (admin/admin)"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Jaeger: http://localhost:16686"
    echo "  - Kibana: http://localhost:5601"
    echo ""
    echo "🔧 Development Tools:"
    echo "  - Kafka UI: http://localhost:8080"
    echo "  - Redis Commander: http://localhost:8081"
    echo "  - MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
    echo ""
    echo "🚀 API Endpoints:"
    echo "  - API Gateway: http://localhost:8080"
    echo "  - Orchestrator: http://localhost:8081"
    echo "  - Media Server: http://localhost:8082"
    echo ""
    echo "📝 Next Steps:"
    echo "  1. Download and optimize models manually"
    echo "  2. Configure environment variables in .env"
    echo "  3. Set up SSL certificates for production"
    echo "  4. Configure monitoring alerts"
    echo "  5. Test the complete pipeline"
    echo ""
    echo "📚 Documentation:"
    echo "  - Check docs/ directory for detailed guides"
    echo "  - Review API documentation in docs/api/"
    echo ""
}

# Main execution
main() {
    echo "🚀 Dharsan Voice Agent V3 - Setup Script"
    echo "=========================================="
    echo ""
    
    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        print_error "Please do not run this script as root"
        exit 1
    fi
    
    # Check requirements
    check_requirements
    
    # Create directories
    create_directories
    
    # Setup Python environment
    setup_python_env
    
    # Setup Go modules
    setup_go_modules
    
    # Download models
    download_models
    
    # Optimize models
    optimize_models
    
    # Setup configuration
    setup_config
    
    # Setup monitoring
    setup_monitoring
    
    # Build images
    build_images
    
    # Start services
    start_services
    
    # Check health
    check_health
    
    # Display next steps
    display_next_steps
}

# Run main function
main "$@" 