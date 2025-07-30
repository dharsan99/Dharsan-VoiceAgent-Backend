#!/bin/bash

# Voice Agent Backend Services Stop Script
# This script stops all backend services and cleans up processes

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

# Function to kill process on a port
kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port)
    if [ ! -z "$pid" ]; then
        print_warning "Killing process on port $port (PID: $pid)"
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi
}

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_status "Stopping Voice Agent Backend Services..."

# Stop services using PIDs from the startup script
if [ -f logs/service_pids.txt ]; then
    print_status "Stopping services using saved PIDs..."
    source logs/service_pids.txt
    
    for pid_var in STT_PID TTS_PID MEDIA_PID ORCHESTRATOR_PID; do
        pid=${!pid_var}
        if [ ! -z "$pid" ] && kill -0 $pid 2>/dev/null; then
            print_status "Stopping $pid_var (PID: $pid)..."
            kill $pid 2>/dev/null || true
            sleep 1
        else
            print_warning "$pid_var process not found or already stopped"
        fi
    done
    
    # Remove the PID file
    rm -f logs/service_pids.txt
else
    print_warning "PID file not found. Stopping services by port..."
fi

# Kill any remaining processes on our ports
print_status "Checking for remaining processes on required ports..."
PORTS=(8000 5001 8001 8002 8004)
for port in "${PORTS[@]}"; do
    if check_port $port; then
        print_warning "Port $port is still in use. Force killing..."
        kill_port $port
    fi
done

# Wait a moment for processes to fully stop
sleep 2

# Verify all ports are free
print_status "Verifying all ports are free..."
all_ports_free=true
for port in "${PORTS[@]}"; do
    if check_port $port; then
        print_error "Port $port is still in use"
        all_ports_free=false
    else
        print_success "Port $port is free"
    fi
done

if [ "$all_ports_free" = true ]; then
    print_success "All backend services stopped successfully!"
else
    print_warning "Some services may still be running. Check manually:"
    print_warning "lsof -i :8000 -i :5001 -i :8001 -i :8002 -i :8004"
fi

# Show log files if they exist
if [ -d logs ]; then
    echo ""
    print_status "Recent log files:"
    for log_file in logs/*.log; do
        if [ -f "$log_file" ]; then
            echo "  - $log_file"
        fi
    done
fi

print_success "Backend services cleanup completed!" 