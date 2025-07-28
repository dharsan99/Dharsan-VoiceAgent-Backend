# Voice AI Backend v2 - WebRTC Implementation

## Overview

This is the **Phase 2** implementation of the Voice AI Backend, featuring ultra-low latency audio transport using WebRTC and a production-ready Kubernetes infrastructure optimized for performance.

## 🚀 Key Features

### **Phase 1: WebRTC Transport Layer** ✅
- **UDP-based audio transport** for ultra-low latency (20-50ms vs 100-200ms TCP)
- **Native WebRTC jitter buffer** for smooth audio playback
- **Opus codec** with packet loss concealment
- **Real-time signaling** over WebSocket
- **Session management** with unique session IDs

### **Phase 2: Low-Latency Infrastructure** ✅
- **Kubernetes deployment** with Guaranteed QoS class
- **OS-level kernel tuning** for network performance
- **Prometheus metrics** for comprehensive monitoring
- **Load balancing** with session affinity
- **Health checks** and auto-recovery
- **Security hardening** with non-root containers

## 📊 Performance Improvements

| Metric | V1 (WebSocket) | V2 (WebSocket) | WebRTC (UDP) |
|--------|----------------|----------------|--------------|
| **Latency** | ~100-200ms | ~100-200ms | **~20-50ms** |
| **Jitter Buffer** | Custom | Custom | **Native WebRTC** |
| **Packet Loss** | Manual handling | Manual handling | **Opus PLC** |
| **Scalability** | Limited | Improved | **High** |
| **QoS** | Best Effort | Best Effort | **Guaranteed** |

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Load Balancer │    │   Kubernetes    │
│   (React)       │◄──►│   (NLB)         │◄──►│   Cluster       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │   WebRTC Pods   │
                                              │   (3 replicas)  │
                                              └─────────────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │   Prometheus    │
                                              │   Monitoring    │
                                              └─────────────────┘
```

## 🛠️ Installation & Deployment

### Prerequisites

1. **Kubernetes Cluster** (EKS, GKE, or AKS recommended)
2. **kubectl** configured
3. **Docker** for building images
4. **Container Registry** (ECR, GCR, or Docker Hub)

### Quick Start

1. **Clone and navigate to the v2 directory:**
   ```bash
   cd v2
   ```

2. **Update configuration:**
   ```bash
   # Edit k8s-secrets.yaml with your API keys
   # Update REGISTRY in deploy-k8s.sh
   ```

3. **Deploy to Kubernetes:**
   ```bash
   ./deploy-k8s.sh deploy
   ```

4. **Check deployment status:**
   ```bash
   ./deploy-k8s.sh status
   ```

### Manual Deployment

1. **Build Docker image:**
   ```bash
   docker build -t voice-ai-backend-v2:latest .
   ```

2. **Apply Kubernetes manifests:**
   ```bash
   kubectl create namespace voice-ai
   kubectl apply -f k8s-secrets.yaml -n voice-ai
   kubectl apply -f sysctl-tuning-daemonset.yaml -n voice-ai
   kubectl apply -f k8s-deployment.yaml -n voice-ai
   kubectl apply -f k8s-service.yaml -n voice-ai
   ```

3. **Wait for deployment:**
   ```bash
   kubectl wait --for=condition=available --timeout=300s deployment/voice-ai-backend-v2 -n voice-ai
   ```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level |
| `MAX_SESSIONS_PER_POD` | `100` | Maximum sessions per pod |
| `SESSION_TIMEOUT` | `300` | Session timeout in seconds |
| `WEBRTC_TIMEOUT` | `30` | WebRTC connection timeout |
| `AUDIO_SAMPLE_RATE` | `48000` | Audio sample rate |
| `AUDIO_CHANNELS` | `1` | Audio channels (mono) |
| `AUDIO_BITRATE` | `64000` | Audio bitrate |

### Kubernetes Configuration

#### Resource Requirements
- **CPU**: 1 core (requested and limited)
- **Memory**: 2GB (requested and limited)
- **QoS Class**: Guaranteed

#### Node Requirements
- **Labels**: `node-type: low-latency`
- **Taints**: `dedicated=voice-ai:NoSchedule`

## 📈 Monitoring & Metrics

### Prometheus Metrics

The backend exposes comprehensive metrics at `/metrics`:

- **`webrtc_websocket_connections_total`**: Active WebSocket connections
- **`webrtc_active_sessions_total`**: Active sessions
- **`webrtc_peer_connections_total`**: WebRTC peer connections
- **`webrtc_signaling_messages_total`**: Signaling messages by type
- **`webrtc_signaling_latency_seconds`**: Signaling latency histogram
- **`webrtc_session_duration_seconds`**: Session duration histogram
- **`webrtc_audio_frames_processed_total`**: Audio frames processed
- **`webrtc_errors_total`**: Errors by type

### Health Checks

- **Endpoint**: `/health`
- **Interval**: 30 seconds
- **Timeout**: 5 seconds
- **Failure Threshold**: 3

### Logging

Structured logging with the following levels:
- `INFO`: Normal operations
- `WARNING`: Non-critical issues
- `ERROR`: Errors that need attention

## 🔒 Security

### Container Security
- **Non-root user**: Runs as user 1000
- **Read-only filesystem**: Except for logs and temp
- **Dropped capabilities**: All unnecessary capabilities removed
- **No privilege escalation**: `allowPrivilegeEscalation: false`

### Network Security
- **Session affinity**: Client IP-based for consistent routing
- **Load balancer**: Network Load Balancer for better performance
- **Health checks**: Regular endpoint validation

## 🚀 Performance Tuning

### OS-Level Optimizations

The `sysctl-tuning-daemonset.yaml` applies the following optimizations:

#### Network Tuning
```bash
# Buffer sizes for low latency
net.core.rmem_max=4194304
net.core.wmem_max=4194304
net.ipv4.tcp_low_latency=1
net.ipv4.tcp_congestion_control=bbr
```

#### CPU Tuning
```bash
# Performance governor
echo performance > /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

#### Memory Tuning
```bash
# Reduce swapping
vm.swappiness=1
```

### Application-Level Optimizations

- **Single worker**: `uvicorn --workers 1` for consistent performance
- **Connection pooling**: Reuse WebRTC connections
- **Memory management**: Efficient audio frame handling
- **Error recovery**: Automatic session cleanup

## 🔄 API Endpoints

### WebRTC Signaling
- **WebSocket**: `ws://{host}/ws/v2/{session_id}`
- **Protocol**: WebRTC signaling over WebSocket

### HTTP Endpoints
- **Root**: `GET /` - Service information
- **Health**: `GET /health` - Health check
- **Sessions**: `GET /v2/sessions` - Active sessions
- **Create Session**: `POST /v2/sessions` - Create new session
- **Metrics**: `GET /metrics` - Prometheus metrics

## 🧪 Testing

### Local Testing
```bash
# Test WebRTC signaling
python test_webrtc_signaling.py

# Test HTTP endpoints
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

### Load Testing
```bash
# Test with multiple concurrent sessions
for i in {1..10}; do
  python test_webrtc_signaling.py &
done
wait
```

## 🐛 Troubleshooting

### Common Issues

1. **Pod not starting**
   ```bash
   kubectl describe pod -n voice-ai -l app=voice-ai-backend-v2
   kubectl logs -n voice-ai -l app=voice-ai-backend-v2
   ```

2. **WebRTC connection failures**
   - Check ICE server configuration
   - Verify network policies
   - Check firewall rules

3. **High latency**
   - Verify node placement (low-latency nodes)
   - Check sysctl tuning applied
   - Monitor network metrics

### Debug Commands

```bash
# Check pod status
kubectl get pods -n voice-ai -l app=voice-ai-backend-v2

# View logs
kubectl logs -f -n voice-ai -l app=voice-ai-backend-v2

# Check metrics
kubectl port-forward service/voice-ai-backend-v2-service 8000:80 -n voice-ai
curl http://localhost:8000/metrics

# Check system tuning
kubectl exec -n voice-ai -l app=sysctl-tuning -- sysctl net.core.rmem_max
```

## 📚 Next Steps

### Phase 3: Redis Integration
- Session persistence
- Message bus for signaling
- Horizontal scaling

### Phase 4: Advanced Features
- Multi-party calls
- Recording capabilities
- Advanced analytics
- eBPF monitoring

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review the monitoring metrics 