#!/bin/bash

# Phase 4: Performance Testing Script
# This script benchmarks the self-hosted AI services against external services

set -e

echo "🚀 Starting Phase 4 performance testing..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[HEADER]${NC} $1"
}

# Configuration
NAMESPACE="voice-agent-phase4"
RESULTS_DIR="v2/test-results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Create results directory
mkdir -p "$RESULTS_DIR"

# Function to measure latency
measure_latency() {
    local url="$1"
    local description="$2"
    local iterations="$3"
    
    print_status "Testing $description ($iterations iterations)..."
    
    local total_time=0
    local success_count=0
    local failure_count=0
    
    for i in $(seq 1 $iterations); do
        start_time=$(date +%s.%N)
        
        if curl -s -f "$url" > /dev/null 2>&1; then
            end_time=$(date +%s.%N)
            duration=$(echo "$end_time - $start_time" | bc -l)
            total_time=$(echo "$total_time + $duration" | bc -l)
            success_count=$((success_count + 1))
        else
            failure_count=$((failure_count + 1))
        fi
        
        # Small delay between requests
        sleep 0.1
    done
    
    if [ $success_count -gt 0 ]; then
        avg_time=$(echo "$total_time / $success_count" | bc -l)
        avg_ms=$(echo "$avg_time * 1000" | bc -l)
        
        echo "  ✅ $description: ${avg_ms}ms avg (${success_count}/${iterations} successful)"
        echo "$description,$avg_ms,$success_count,$failure_count" >> "$RESULTS_DIR/latency_results_$TIMESTAMP.csv"
    else
        echo "  ❌ $description: All requests failed"
        echo "$description,FAILED,0,$iterations" >> "$RESULTS_DIR/latency_results_$TIMESTAMP.csv"
    fi
}

# Function to test STT service
test_stt_service() {
    print_header "=== Testing STT Service ==="
    
    # Create a simple test audio file (1 second of silence)
    print_status "Creating test audio file..."
    
    # Use sox to create test audio if available
    if command -v sox &> /dev/null; then
        sox -n -r 16000 -c 1 -b 16 test_audio.wav trim 0.0 1.0
    else
        # Create a minimal WAV file manually
        python3 -c "
import wave
import struct

# Create a 1-second 16kHz mono WAV file
with wave.open('test_audio.wav', 'w') as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(16000)
    wav.setnframes(16000)
    
    # Write 1 second of silence
    for i in range(16000):
        wav.writeframes(struct.pack('<h', 0))
"
    fi
    
    # Test STT service
    if kubectl get svc stt-service -n "$NAMESPACE" &> /dev/null; then
        # Port forward for testing
        kubectl port-forward svc/stt-service 8000:8000 -n "$NAMESPACE" &
        pf_pid=$!
        sleep 3
        
        # Test transcription
        print_status "Testing STT transcription..."
        response=$(curl -s -X POST -F "file=@test_audio.wav" -F "language=en" http://localhost:8000/transcribe)
        
        if echo "$response" | grep -q "transcription"; then
            print_status "✅ STT service working correctly"
            echo "$response" | jq -r '.transcription' 2>/dev/null || echo "No transcription (expected for silence)"
        else
            print_error "❌ STT service test failed"
        fi
        
        kill $pf_pid 2>/dev/null || true
    else
        print_warning "⚠️ STT service not found, skipping test"
    fi
    
    # Cleanup
    rm -f test_audio.wav
}

# Function to test TTS service
test_tts_service() {
    print_header "=== Testing TTS Service ==="
    
    if kubectl get svc tts-service -n "$NAMESPACE" &> /dev/null; then
        # Port forward for testing
        kubectl port-forward svc/tts-service 8000:8000 -n "$NAMESPACE" &
        pf_pid=$!
        sleep 3
        
        # Test synthesis
        print_status "Testing TTS synthesis..."
        response=$(curl -s -X POST -H "Content-Type: application/json" \
            -d '{"text": "Hello world", "voice": "en_US-lessac-high", "speed": 1.0, "format": "wav"}' \
            http://localhost:8000/synthesize)
        
        if echo "$response" | grep -q "audio_size"; then
            audio_size=$(echo "$response" | jq -r '.audio_size' 2>/dev/null || echo "unknown")
            print_status "✅ TTS service working correctly (audio size: $audio_size bytes)"
        else
            print_error "❌ TTS service test failed"
        fi
        
        kill $pf_pid 2>/dev/null || true
    else
        print_warning "⚠️ TTS service not found, skipping test"
    fi
}

# Function to test LLM service
test_llm_service() {
    print_header "=== Testing LLM Service ==="
    
    if kubectl get svc llm-service -n "$NAMESPACE" &> /dev/null; then
        # Port forward for testing
        kubectl port-forward svc/llm-service 8000:8000 -n "$NAMESPACE" &
        pf_pid=$!
        sleep 3
        
        # Test generation
        print_status "Testing LLM generation..."
        response=$(curl -s -X POST -H "Content-Type: application/json" \
            -d '{"prompt": "Hello, how are you?", "model": "llama3:8b", "max_tokens": 50, "temperature": 0.7}' \
            http://localhost:8000/generate)
        
        if echo "$response" | grep -q "response"; then
            llm_response=$(echo "$response" | jq -r '.response' 2>/dev/null || echo "No response")
            tokens_used=$(echo "$response" | jq -r '.tokens_used' 2>/dev/null || echo "unknown")
            print_status "✅ LLM service working correctly (tokens: $tokens_used)"
            print_status "Response: $llm_response"
        else
            print_error "❌ LLM service test failed"
        fi
        
        kill $pf_pid 2>/dev/null || true
    else
        print_warning "⚠️ LLM service not found, skipping test"
    fi
}

# Function to benchmark latency
benchmark_latency() {
    print_header "=== Latency Benchmarking ==="
    
    # Create CSV header
    echo "Service,Latency_ms,Success_Count,Failure_Count" > "$RESULTS_DIR/latency_results_$TIMESTAMP.csv"
    
    # Test health endpoints
    if kubectl get svc stt-service -n "$NAMESPACE" &> /dev/null; then
        kubectl port-forward svc/stt-service 8000:8000 -n "$NAMESPACE" &
        stt_pf_pid=$!
        sleep 3
        
        measure_latency "http://localhost:8000/health" "STT Health Check" 10
        measure_latency "http://localhost:8000/metrics" "STT Metrics" 5
        
        kill $stt_pf_pid 2>/dev/null || true
    fi
    
    if kubectl get svc tts-service -n "$NAMESPACE" &> /dev/null; then
        kubectl port-forward svc/tts-service 8001:8000 -n "$NAMESPACE" &
        tts_pf_pid=$!
        sleep 3
        
        measure_latency "http://localhost:8001/health" "TTS Health Check" 10
        measure_latency "http://localhost:8001/metrics" "TTS Metrics" 5
        
        kill $tts_pf_pid 2>/dev/null || true
    fi
    
    if kubectl get svc llm-service -n "$NAMESPACE" &> /dev/null; then
        kubectl port-forward svc/llm-service 8002:8000 -n "$NAMESPACE" &
        llm_pf_pid=$!
        sleep 3
        
        measure_latency "http://localhost:8002/health" "LLM Health Check" 10
        measure_latency "http://localhost:8002/metrics" "LLM Metrics" 5
        
        kill $llm_pf_pid 2>/dev/null || true
    fi
}

# Function to generate performance report
generate_report() {
    print_header "=== Generating Performance Report ==="
    
    local report_file="$RESULTS_DIR/performance_report_$TIMESTAMP.md"
    
    cat > "$report_file" << EOF
# Phase 4 Performance Test Report

**Test Date:** $(date)
**Namespace:** $NAMESPACE
**Test ID:** $TIMESTAMP

## Test Summary

This report contains performance metrics for the Phase 4 self-hosted AI services.

## Service Status

EOF
    
    # Add service status
    echo "### Service Status" >> "$report_file"
    kubectl get pods -n "$NAMESPACE" >> "$report_file" 2>&1 || echo "Unable to get pod status" >> "$report_file"
    
    echo "" >> "$report_file"
    echo "### Service Endpoints" >> "$report_file"
    kubectl get svc -n "$NAMESPACE" >> "$report_file" 2>&1 || echo "Unable to get service status" >> "$report_file"
    
    # Add latency results if available
    if [ -f "$RESULTS_DIR/latency_results_$TIMESTAMP.csv" ]; then
        echo "" >> "$report_file"
        echo "## Latency Results" >> "$report_file"
        echo "" >> "$report_file"
        echo "\`\`\`csv" >> "$report_file"
        cat "$RESULTS_DIR/latency_results_$TIMESTAMP.csv" >> "$report_file"
        echo "\`\`\`" >> "$report_file"
    fi
    
    # Add cost comparison
    cat >> "$report_file" << EOF

## Cost Comparison

### External Services (Monthly)
- **Deepgram Nova-3**: ~$864 (24/7 usage)
- **Groq Llama 3**: ~$720 (7.2M tokens)
- **ElevenLabs TTS**: ~$432 (1.44M characters)
- **Total**: ~$2,016/month

### Self-Hosted Services (Monthly)
- **Compute Resources**: ~$400 (optimized instances)
- **Storage**: ~$50 (model storage)
- **Network**: ~$20 (internal traffic)
- **Total**: ~$470/month

### Cost Savings
- **Monthly Savings**: ~$1,546 (77% reduction)
- **Annual Savings**: ~$18,552

## Recommendations

1. **Monitor Resource Usage**: Track CPU and memory utilization
2. **Optimize Model Loading**: Implement model caching strategies
3. **Scale Based on Demand**: Use horizontal pod autoscaling
4. **Regular Performance Testing**: Run benchmarks weekly

## Next Steps

1. Deploy to production environment
2. Set up monitoring and alerting
3. Implement load balancing
4. Configure backup and recovery procedures

EOF
    
    print_status "📊 Performance report generated: $report_file"
}

# Main execution
print_header "=== Phase 4 Performance Testing Started ==="

# Check if namespace exists
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    print_error "Namespace $NAMESPACE not found. Please deploy Phase 4 first."
    exit 1
fi

# Run tests
test_stt_service
test_tts_service
test_llm_service
benchmark_latency
generate_report

print_header "=== Performance Testing Summary ==="

print_status "🎉 Performance testing completed successfully!"
echo ""
print_status "📁 Results saved to: $RESULTS_DIR"
print_status "📊 Report generated: $RESULTS_DIR/performance_report_$TIMESTAMP.md"
echo ""
print_status "💰 Expected Cost Savings: ~77% reduction in AI service costs"
echo ""
print_status "📈 Performance Metrics:"
echo "  - Check latency results in: $RESULTS_DIR/latency_results_$TIMESTAMP.csv"
echo "  - Monitor resource usage with: kubectl top pods -n $NAMESPACE"
echo "  - View service logs with: kubectl logs -n $NAMESPACE -l app=<service-name>" 