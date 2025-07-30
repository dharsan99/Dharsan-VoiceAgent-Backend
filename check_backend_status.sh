#!/bin/bash

# Voice Agent Backend Services Status Check Script
# This script checks the status of all backend services

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

# Function to check service health
check_service_health() {
    local url=$1
    local service_name=$2
    
    if curl -s "$url/health" >/dev/null 2>&1; then
        print_success "$service_name is healthy"
        return 0
    else
        print_error "$service_name health check failed"
        return 1
    fi
}

# Function to check service logs endpoint
check_logs_endpoint() {
    local url=$1
    local service_name=$2
    
    if curl -s "$url/logs" >/dev/null 2>&1; then
        print_success "$service_name logs endpoint is working"
        return 0
    else
        print_warning "$service_name logs endpoint not responding"
        return 1
    fi
}

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_status "Checking Voice Agent Backend Services Status..."
echo ""

# Check port status
print_status "Port Status:"
echo "============="
PORTS=(8000 5001 8001 8002 8004)
for port in "${PORTS[@]}"; do
    if check_port $port; then
        pid=$(lsof -ti:$port)
        print_success "Port $port: IN USE (PID: $pid)"
    else
        print_error "Port $port: FREE"
    fi
done

echo ""

# Check service health
print_status "Service Health:"
echo "=================="
healthy_count=0
total_count=0

# Check STT Service
total_count=$((total_count + 1))
if check_service_health "http://localhost:8000" "STT Service"; then
    healthy_count=$((healthy_count + 1))
fi

# Check TTS Service
total_count=$((total_count + 1))
if check_service_health "http://localhost:5001" "TTS Service"; then
    healthy_count=$((healthy_count + 1))
fi

# Check Media Server
total_count=$((total_count + 1))
if check_service_health "http://localhost:8001" "Media Server"; then
    healthy_count=$((healthy_count + 1))
fi

# Check Orchestrator
total_count=$((total_count + 1))
if check_service_health "http://localhost:8004" "Orchestrator"; then
    healthy_count=$((healthy_count + 1))
fi

echo ""

# Check log endpoints
print_status "Log Endpoints:"
echo "================"
logs_working=0

# Check STT logs
if check_logs_endpoint "http://localhost:8000" "STT Service"; then
    logs_working=$((logs_working + 1))
fi

# Check TTS logs
if check_logs_endpoint "http://localhost:5001" "TTS Service"; then
    logs_working=$((logs_working + 1))
fi

# Check Media Server logs
if check_logs_endpoint "http://localhost:8001" "Media Server"; then
    logs_working=$((logs_working + 1))
fi

# Check Orchestrator logs
if check_logs_endpoint "http://localhost:8004" "Orchestrator"; then
    logs_working=$((logs_working + 1))
fi

echo ""

# Summary
print_status "Summary:"
echo "========"
echo "Services Running: $healthy_count/$total_count"
echo "Log Endpoints Working: $logs_working/$total_count"

if [ $healthy_count -eq $total_count ]; then
    print_success "All services are healthy!"
else
    print_warning "Some services are not healthy"
fi

if [ $logs_working -eq $total_count ]; then
    print_success "All log endpoints are working!"
else
    print_warning "Some log endpoints are not working"
fi

echo ""

# Show recent logs if available
if [ -d logs ]; then
    print_status "Recent Log Files:"
    echo "=================="
    for log_file in logs/*.log; do
        if [ -f "$log_file" ]; then
            echo "  - $log_file"
        fi
    done
fi

echo ""
print_status "To start services: ./start_backend_services.sh"
print_status "To stop services:  ./stop_backend_services.sh" 