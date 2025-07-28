# Voice Agent Backend System

A comprehensive backend system for real-time voice AI conversations with multiple deployment architectures, from simple API-based systems to complex Kubernetes microservices with WebRTC, gRPC, and event-driven pipelines.

## Live Demo
**Live Application**: [https://dharsan-voice-agent-frontend.vercel.app/](https://dharsan-voice-agent-frontend.vercel.app/)

## Repository Links
- **Frontend Repository**: [https://github.com/dharsan99/Dharsan-VoiceAgent-Frontend](https://github.com/dharsan99/Dharsan-VoiceAgent-Frontend)
- **Backend Repository**: [https://github.com/dharsan99/Dharsan-VoiceAgent-Backend](https://github.com/dharsan99/Dharsan-VoiceAgent-Backend)

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Version History](#version-history)
- [Quick Start](#quick-start)
- [Development Setup](#development-setup)
- [Deployment](#deployment)
- [Testing](#testing)
- [Documentation](#documentation)
- [Contributing](#contributing)

## Overview

The Voice Agent Backend is a sophisticated system that provides real-time voice conversation capabilities with AI services. It supports multiple deployment architectures, from simple API-based systems to complex Kubernetes microservices with WebRTC, gRPC, and event-driven pipelines.

### Key Capabilities
- **Real-time Voice Processing**: Live audio capture, streaming, and playback
- **Multiple AI Integrations**: Support for various STT, LLM, and TTS services
- **WebRTC & gRPC**: High-performance communication protocols
- **Event-Driven Architecture**: Scalable, responsive conversation flow
- **Production Ready**: Kubernetes deployment with monitoring and auto-scaling
- **Multi-Phase Evolution**: Progressive enhancement from simple to complex architectures

## System Architecture

### High-Level Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Media Server  │    │   Orchestrator  │
│   (React)       │◄──►│   (Go)          │◄──►│   (Go)          │
│   Port: 80      │    │   Port: 8080    │    │   Port: 8001    │
│   Nginx         │    │   WHIP Protocol │    │   AI Pipeline   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Ingress       │    │   Redpanda      │    │   Prometheus    │
│   Controller    │    │   (Kafka)       │    │   Monitoring    │
│   SSL/TLS       │    │   Message Bus   │    │   Metrics       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Pipeline Flow
1. **Audio Capture**: Browser microphone → WebRTC/WebSocket
2. **Real-time Processing**: Audio streaming to backend services
3. **AI Pipeline**: STT → LLM → TTS processing
4. **Response Delivery**: Audio streaming back to frontend
5. **Playback**: Real-time audio output with visualization

## Version History

### V1 - Initial Test Version
**Status**: Complete | **Focus**: API Integration & Basic Functionality

**Features**:
- Direct API integration with external services
- **STT**: Deepgram for speech-to-text
- **LLM**: Groq for language processing
- **TTS**: ElevenLabs for text-to-speech
- **Backup**: Azure Speech Services
- Simple WebSocket communication
- Basic audio visualization
- **Metrics System**: Comprehensive conversation tracking and analytics

**Architecture**:
```
Frontend → WebSocket → Backend → External APIs (Deepgram/Groq/ElevenLabs/Azure)
```

**Use Case**: Proof of concept, testing AI service integrations

**Key Files**:
- [CONVERSATION_METRICS.md](./v1/CONVERSATION_METRICS.md) - Enhanced conversation metrics system
- [DATABASE_README.md](./v1/DATABASE_README.md) - SQLite-based metrics database
- [V1_COMPLETE_ANALYSIS.md](./V1_COMPLETE_ANALYSIS.md) - Complete V1 system analysis

---

### V2 - GKE Production Version
**Status**: Complete | **Focus**: Kubernetes, WebRTC, Microservices

**Evolution**:
- **Phase 1**: WHIP protocol, STUN/TURN servers, Kafka, Redpanda
- **Phase 2**: Moved to gRPC for better performance
- **Phase 3**: Redis integration for session persistence
- **Phase 4**: Self-hosted AI models (Whisper + Piper)
- **Phase 5**: Event-driven architecture with deterministic flow

**Features**:
- **WebRTC**: WHIP protocol for real-time audio streaming
- **gRPC**: High-performance inter-service communication
- **Kafka/Redpanda**: Message bus for scalability
- **Kubernetes**: Production deployment with auto-scaling
- **Event-Driven**: Deterministic conversation flow
- **Performance**: <5ms end-to-end latency, 95.8% success rate
- **Self-Hosted AI**: Whisper for STT, Piper for TTS

**Architecture**:
```
Frontend (React) → WebRTC/WebSocket → Media Server → Orchestrator → AI Services
                                    ↓
                              Kafka/Redpanda → STT/LLM/TTS Services
```

**Use Case**: Production deployment, high-performance voice conversations

**Key Files**:
- [README-Phase2.md](./v2/README-Phase2.md) - Phase 2 implementation details
- [README-Phase3.md](./v2/README-Phase3.md) - Redis integration
- [README-Phase4.md](./v2/README-Phase4.md) - Self-hosted AI models
- [PIPELINE_TEST_RESULTS.md](./v2/PIPELINE_TEST_RESULTS.md) - Comprehensive test results
- [WHIP_SETUP.md](./v2/WHIP_SETUP.md) - WebRTC WHIP protocol setup

---

### V3 - VAD & Live Conversations
**Status**: In Development | **Focus**: Voice Activity Detection, Enhanced UX

**Planned Features**:
- **VAD**: Voice Activity Detection for natural conversations
- **Live Transcription**: Real-time text display
- **Conversation Management**: Context-aware dialogue
- **Advanced Audio Processing**: Noise reduction, echo cancellation
- **Multi-modal Support**: Text, voice, and visual interactions

**Use Case**: Natural, human-like voice conversations

**Key Files**:
- [V3_COMPLETE_ANALYSIS.md](./V3_COMPLETE_ANALYSIS.md) - Complete V3 system analysis
- [VAD_IMPROVEMENT_ANALYSIS.md](./VAD_IMPROVEMENT_ANALYSIS.md) - Voice Activity Detection analysis

## Quick Start

### Prerequisites
- Python 3.8+ (for V1)
- Go 1.24.5+ (for V2)
- Docker (for containerized deployment)
- kubectl (for Kubernetes deployment)
- Node.js 18+ (for frontend)

### V1 Backend (API-based)
```bash
# Clone the repository
git clone https://github.com/dharsan99/Dharsan-VoiceAgent-Backend
cd Dharsan-VoiceAgent-Backend

# Set up Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys

# Start the backend
python main.py
```

### V2 Backend (Kubernetes)
```bash
# Navigate to V2 directory
cd v2

# Deploy to GKE
./deploy.sh

# Check deployment status
kubectl get pods -n voice-agent-phase5
kubectl logs -n voice-agent-phase5 deployment/orchestrator
```

### Service Health Check
```bash
# Check all services
./check-deployment.sh

# Test individual services
curl http://localhost:8080/health  # Media Server
curl http://localhost:8001/health  # Orchestrator
curl http://localhost:5000/health  # TTS Service
```

## Development Setup

### Environment Configuration

#### V1 Environment Variables
```env
# API Keys
DEEPGRAM_API_KEY=your_deepgram_key
GROQ_API_KEY=your_groq_key
ELEVENLABS_API_KEY=your_elevenlabs_key
AZURE_SPEECH_KEY=your_azure_key

# Service URLs
DEEPGRAM_URL=https://api.deepgram.com/v1/listen
GROQ_URL=https://api.groq.com/openai/v1/chat/completions
ELEVENLABS_URL=https://api.elevenlabs.io/v1/text-to-speech
AZURE_SPEECH_URL=https://eastus.tts.speech.microsoft.com/cognitiveservices/v1
```

#### V2 Environment Variables
```env
# Kafka/Redpanda Configuration
KAFKA_BROKERS=redpanda.voice-agent-phase5.svc.cluster.local:9092

# AI Service Configuration
STT_SERVICE_URL=http://stt-service.voice-agent-phase5.svc.cluster.local:8000
LLM_SERVICE_URL=http://llm-service.voice-agent-phase5.svc.cluster.local:11434
TTS_SERVICE_URL=http://tts-service.voice-agent-phase5.svc.cluster.local:5000

# WebRTC Configuration
ICE_SERVERS=stun:stun.l.google.com:19302
```

### Available Scripts
```bash
# V1 Development
python main.py              # Start V1 backend
python test_grpc_implementation.py  # Test gRPC implementation

# V2 Development
cd v2
go build -o orchestrator    # Build orchestrator
go build -o media-server    # Build media server
./deploy.sh                 # Deploy to Kubernetes

# Testing
python test_system_readiness.py  # System readiness test
python test_event_driven_flow.py # Event-driven flow test
```

## Deployment

### V1 Deployment (Modal)
```bash
# Deploy to Modal
modal deploy main.py

# Check deployment
modal app list
modal logs voice-agent-backend
```

### V2 Deployment (GKE)
```bash
# Deploy to GKE
cd v2
./deploy.sh

# Check deployment
kubectl get pods -n voice-agent-phase5
kubectl logs -f -n voice-agent-phase5 deployment/orchestrator

# Access services
kubectl port-forward -n voice-agent-phase5 svc/orchestrator 8001:8001
kubectl port-forward -n voice-agent-phase5 svc/media-server 8080:8080
```

### Production Deployment
```bash
# Production deployment with monitoring
cd v2
./deploy-production.sh

# Check production status
./check-deployment.sh

# Monitor logs
kubectl logs -f -n voice-agent-phase5 deployment/orchestrator
kubectl logs -f -n voice-agent-phase5 deployment/media-server
```

## Testing

### Manual Testing
1. **V1 Testing**: `http://localhost:8000/health` - API-based testing
2. **V2 Testing**: `http://localhost:8080/health` - WebRTC testing
3. **Phase 2 Testing**: `http://localhost:8001/health` - gRPC testing
4. **Phase 5 Testing**: Event-driven testing

### Automated Testing
```bash
# Run all tests
python test_system_readiness.py

# Run specific test suites
python test_grpc_implementation.py
python test_event_driven_flow.py
python test_websocket_simple.py

# Performance testing
python test_phase2_backend.py
```

### Performance Testing
```bash
# Run performance benchmarks
python test_grpc_communication.py

# Check performance metrics
./quick-service-check.js
```

## Documentation

### Core Documentation
- **[Quick Start](./QUICK_START.md)** - Quick setup guide
- **[Setup](./SETUP.md)** - Detailed setup instructions
- **[Versioning](./VERSIONING.md)** - Version management strategy
- **[System Readiness Report](./system_readiness_report.md)** - System readiness analysis

### V1 Documentation
- **[Conversation Metrics](./v1/CONVERSATION_METRICS.md)** - Enhanced conversation metrics system
- **[Database README](./v1/DATABASE_README.md)** - SQLite-based metrics database
- **[V1 Complete Analysis](./V1_COMPLETE_ANALYSIS.md)** - Complete V1 system analysis

### V2 Documentation
- **[Phase 2 Implementation](./v2/README-Phase2.md)** - Phase 2 implementation details
- **[Phase 3 Implementation](./v2/README-Phase3.md)** - Redis integration
- **[Phase 4 Implementation](./v2/README-Phase4.md)** - Self-hosted AI models
- **[Pipeline Test Results](./v2/PIPELINE_TEST_RESULTS.md)** - Comprehensive test results
- **[WHIP Setup](./v2/WHIP_SETUP.md)** - WebRTC WHIP protocol setup

### Architecture Documentation
- **[V2 Complete Analysis](./V2_COMPLETE_ANALYSIS.md)** - Complete V2 system analysis
- **[V3 Complete Analysis](./V3_COMPLETE_ANALYSIS.md)** - Complete V3 system analysis
- **[Backend Refactoring Summary](./BACKEND_REFACTORING_SUMMARY.md)** - Code refactoring overview
- **[Complete Pipeline Codebase Analysis](./COMPLETE_PIPELINE_CODEBASE_ANALYSIS.md)** - Pipeline architecture analysis

### Audio Processing Documentation
- **[Audio Enhancement Implementation](./AUDIO_ENHANCEMENT_IMPLEMENTATION.md)** - Audio processing improvements
- **[Audio Flow Logic Analysis](./AUDIO_FLOW_LOGIC_ANALYSIS.md)** - Audio pipeline flow analysis
- **[Audio Level Meter Implementation](./AUDIO_LEVEL_METER_IMPLEMENTATION.md)** - Audio visualization
- **[Audio Pipeline Debugging Analysis](./AUDIO_PIPELINE_DEBUGGING_ANALYSIS.md)** - Audio pipeline debugging
- **[Audio Pipeline Debugging Enhanced](./AUDIO_PIPELINE_DEBUGGING_ENHANCED.md)** - Enhanced debugging
- **[Audio Pipeline Debugging Resolution](./AUDIO_PIPELINE_DEBUGGING_RESOLUTION.md)** - Debugging resolution
- **[Complete Audio Buffering Implementation](./COMPLETE_AUDIO_BUFFERING_IMPLEMENTATION.md)** - Audio buffering system
- **[Complete Audio Buffering Testing Status](./COMPLETE_AUDIO_BUFFERING_TESTING_STATUS.md)** - Buffering test results

### Connection Management Documentation
- **[Connection Management Analysis](./CONNECTION_MANAGEMENT_ANALYSIS.md)** - Connection management system
- **[WebSocket Connection Final Fix](./WEBSOCKET_CONNECTION_FINAL_FIX.md)** - WebSocket fixes
- **[WebSocket Connection Fix Success](./WEBSOCKET_CONNECTION_FIX_SUCCESS.md)** - Connection success
- **[WebSocket Connection Fix](./WEBSOCKET_CONNECTION_FIX.md)** - Connection fixes
- **[WebSocket Stability Fix](./WEBSOCKET_STABILITY_FIX.md)** - Stability improvements
- **[WebSocket Audio Pipeline Test Results](./WEBSOCKET_AUDIO_PIPELINE_TEST_RESULTS.md)** - Pipeline test results
- **[Realtime WebSocket Updates Implementation](./REALTIME_WEBSOCKET_UPDATES_IMPLEMENTATION.md)** - Real-time updates

### Pipeline Documentation
- **[Pipeline Completion Fixes Implementation](./PIPELINE_COMPLETION_FIXES_IMPLEMENTATION.md)** - Pipeline fixes
- **[Pipeline Completion Issue Analysis](./PIPELINE_COMPLETION_ISSUE_ANALYSIS.md)** - Issue analysis
- **[Pipeline Flag Implementation Plan](./PIPELINE_FLAG_IMPLEMENTATION_PLAN.md)** - Flag implementation
- **[Pipeline Flag Integration Success](./PIPELINE_FLAG_INTEGRATION_SUCCESS.md)** - Integration success
- **[Pipeline Flag System Design](./PIPELINE_FLAG_SYSTEM_DESIGN.md)** - System design
- **[Pipeline State Management Live Status](./PIPELINE_STATE_MANAGEMENT_LIVE_STATUS.md)** - State management
- **[Premature Pipeline Activation Fix](./PREMATURE_PIPELINE_ACTIVATION_FIX.md)** - Activation fixes

### Session Management Documentation
- **[Session ID Analysis and Fixes](./SESSION_ID_ANALYSIS_AND_FIXES.md)** - Session ID fixes
- **[Session ID Consistency Fix](./SESSION_ID_CONSISTENCY_FIX.md)** - Consistency fixes
- **[Session ID Fixes Summary](./SESSION_ID_FIXES_SUMMARY.md)** - Fixes summary
- **[Session ID Resolution Verification](./SESSION_ID_RESOLUTION_VERIFICATION.md)** - Resolution verification
- **[Final Session ID Resolution](./FINAL_SESSION_ID_RESOLUTION.md)** - Final resolution

### GKE Deployment Documentation
- **[GKE Current Status Analysis](./GKE_CURRENT_STATUS_ANALYSIS.md)** - Current status
- **[GKE Final Status Report](./GKE_FINAL_STATUS_REPORT.md)** - Final status
- **[GKE Optimization Deployment Success](./GKE_OPTIMIZATION_DEPLOYMENT_SUCCESS.md)** - Optimization success
- **[GKE Optimization Implementation Guide](./GKE_OPTIMIZATION_IMPLEMENTATION_GUIDE.md)** - Implementation guide
- **[GKE Pipeline Flow Analysis](./GKE_PIPELINE_FLOW_ANALYSIS.md)** - Pipeline flow
- **[GKE Pipeline Logs VAD Analysis](./GKE_PIPELINE_LOGS_VAD_ANALYSIS.md)** - VAD analysis
- **[GKE Production Deployment Guide](./GKE_PRODUCTION_DEPLOYMENT_GUIDE.md)** - Production guide
- **[GKE Usage and Limits Analysis](./GKE_USAGE_AND_LIMITS_ANALYSIS.md)** - Usage analysis
- **[GKE Auto Scaling Configuration](./GKE_AUTO_SCALING_CONFIGURATION.md)** - Auto-scaling
- **[GKE Logs Analysis Pipeline Fixes](./GKE_LOGS_ANALYSIS_PIPELINE_FIXES.md)** - Logs analysis

### Service-Specific Documentation
- **[STT Issue Fix Summary](./STT_ISSUE_FIX_SUMMARY.md)** - STT fixes
- **[STT Optimization Deployment Success](./STT_OPTIMIZATION_DEPLOYMENT_SUCCESS.md)** - STT optimization
- **[STT Service Kubernetes Optimization](./STT_SERVICE_KUBERNETES_OPTIMIZATION.md)** - STT K8s optimization
- **[STT Classification Improvements](./STT_CLASSIFICATION_IMPROVEMENTS.md)** - STT improvements
- **[STT Connection Fixes Analysis](./STT_CONNECTION_FIXES_ANALYSIS.md)** - STT connection fixes
- **[STT Fallback Response Fix](./STT_FALLBACK_RESPONSE_FIX.md)** - STT fallback
- **[TTS Pipeline Analysis](./TTS_PIPELINE_ANALYSIS.md)** - TTS pipeline
- **[Whisper Large Testing Results](./WHISPER_LARGE_TESTING_RESULTS.md)** - Whisper testing
- **[Whisper Large Upgrade Implementation](./WHISPER_LARGE_UPGRADE_IMPLEMENTATION.md)** - Whisper upgrade

### Frontend Integration Documentation
- **[Frontend Pipeline Components Success](./FRONTEND_PIPELINE_COMPONENTS_SUCCESS.md)** - Frontend success
- **[Frontend Pipeline Issues Analysis](./FRONTEND_PIPELINE_ISSUES_ANALYSIS.md)** - Frontend issues
- **[Phase 2 Frontend Implementation Success](./PHASE2_FRONTEND_IMPLEMENTATION_SUCCESS.md)** - Phase 2 success
- **[Phase 3 Implementation Summary](./PHASE3_IMPLEMENTATION_SUMMARY.md)** - Phase 3 summary
- **[Phase 4 Implementation Summary](./PHASE4_IMPLEMENTATION_SUMMARY.md)** - Phase 4 summary

### Performance and Optimization Documentation
- **[Memory Optimization Plan](./MEMORY_OPTIMIZATION_PLAN.md)** - Memory optimization
- **[Memory Optimization Success](./MEMORY_OPTIMIZATION_SUCCESS.md)** - Optimization success
- **[GCP Free Tier Memory Analysis](./GCP_FREE_TIER_MEMORY_ANALYSIS.md)** - Memory analysis
- **[Kafka Configuration Fix Success](./KAFKA_CONFIGURATION_FIX_SUCCESS.md)** - Kafka fixes
- **[Media Server Loadbalancer Fix](./MEDIA_SERVER_LOADBALANCER_FIX.md)** - Loadbalancer fixes
- **[Media Server Session Affinity Fix](./MEDIA_SERVER_SESSION_AFFINITY_FIX.md)** - Session affinity
- **[WHIP Connection Timing Fix](./WHIP_CONNECTION_TIMING_FIX.md)** - WHIP timing

### User Experience Documentation
- **[Automatic Listening and Connection Fix](./AUTOMATIC_LISTENING_AND_CONNECTION_FIX.md)** - Auto-connection
- **[CORS Fix for Listening Endpoints](./CORS_FIX_FOR_LISTENING_ENDPOINTS.md)** - CORS fixes
- **[Dynamic Button Implementation](./DYNAMIC_BUTTON_IMPLEMENTATION.md)** - Dynamic UI
- **[Graceful Stop Conversation Implementation](./GRACEFUL_STOP_CONVERSATION_IMPLEMENTATION.md)** - Graceful stop
- **[Manual Workflow Restored](./MANUAL_WORKFLOW_RESTORED.md)** - Manual workflow
- **[Silence and Unwanted Audio Analysis](./SILENCE_AND_UNWANTED_AUDIO_ANALYSIS.md)** - Audio analysis
- **[Simplified Frontend and Audio Filtering Implementation](./SIMPLIFIED_FRONTEND_AND_AUDIO_FILTERING_IMPLEMENTATION.md)** - Audio filtering

### Testing and Analysis Documentation
- **[Test Report](./test_report.md)** - Test results
- **[gRPC Test Report](./grpc_test_report.md)** - gRPC testing
- **[System Readiness Report](./system_readiness_report.md)** - System readiness
- **[Current System Status Analysis](./CURRENT_SYSTEM_STATUS_ANALYSIS.md)** - Current status
- **[Final System Status Report](./FINAL_SYSTEM_STATUS_REPORT.md)** - Final status
- **[Event Sequence Implementation Summary](./EVENT_SEQUENCE_IMPLEMENTATION_SUMMARY.md)** - Event sequence

### Development Documentation
- **[Modal Setup](./MODAL_SETUP.md)** - Modal deployment setup
- **[V2 Phase 1 TODO](./V2_PHASE1_TODO.md)** - Phase 1 tasks
- **[V2 Phase 3 TODO](./V2_PHASE3_TODO.md)** - Phase 3 tasks
- **[V2 Phase 4 TODO](./V2_PHASE4_TODO.md)** - Phase 4 tasks

## Performance Metrics

### Current Performance (Phase 5)
- **End-to-End Latency**: < 5ms (target: < 100ms)
- **Success Rate**: 95.8% (target: > 85%)
- **WHIP Connection**: 2.5ms average
- **WebSocket Communication**: 1.5ms average
- **AI Pipeline Response**: 2.0ms average
- **gRPC Communication**: < 1ms average

### Resource Usage
- **Memory Usage**: Optimized with automatic cleanup
- **CPU Usage**: Efficient processing with connection pooling
- **Network**: Optimized for low-latency communication
- **Storage**: Minimal with efficient data structures

## Troubleshooting

### Common Issues

#### WebSocket Connection Issues
- **Issue**: Connection timeouts or failures
- **Solution**: Check backend service status
- **Debug**: Use browser console and network tab
- **Reference**: [WebSocket Connection Fix](./WEBSOCKET_CONNECTION_FIX.md)

#### Audio Pipeline Issues
- **Issue**: Audio not processing correctly
- **Solution**: Check audio pipeline state
- **Debug**: Monitor pipeline logs
- **Reference**: [Audio Pipeline Debugging Resolution](./AUDIO_PIPELINE_DEBUGGING_RESOLUTION.md)

#### Kubernetes Deployment Issues
- **Issue**: Pods not starting or services unavailable
- **Solution**: Check resource limits and service configuration
- **Debug**: Use kubectl logs and describe commands
- **Reference**: [GKE Current Status Analysis](./GKE_CURRENT_STATUS_ANALYSIS.md)

#### Performance Issues
- **Issue**: High latency or poor audio quality
- **Solution**: Check network conditions and service health
- **Monitoring**: Use built-in performance metrics
- **Reference**: [GKE Optimization Implementation Guide](./GKE_OPTIMIZATION_IMPLEMENTATION_GUIDE.md)

### Debug Commands
```bash
# Check service health
./check-deployment.sh

# View service logs
kubectl logs -n voice-agent-phase5 deployment/orchestrator
kubectl logs -n voice-agent-phase5 deployment/media-server
kubectl logs -n voice-agent-phase5 deployment/tts-service

# Test individual services
curl http://localhost:8080/health
curl http://localhost:8001/health
curl http://localhost:5000/health

# Check system readiness
python test_system_readiness.py
```

## Contributing

### Development Workflow
1. **Fork** the repository
2. **Create** a feature branch
3. **Make** your changes
4. **Test** thoroughly
5. **Submit** a pull request

### Code Standards
- **Python**: Follow PEP 8 for V1
- **Go**: Follow Go best practices for V2
- **Testing**: Include unit tests for new features
- **Documentation**: Update relevant documentation

### Testing Requirements
- **Unit Tests**: 80%+ coverage
- **Integration Tests**: End-to-end functionality
- **Performance Tests**: Latency and throughput validation

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **React Team**: For the excellent frontend framework
- **WebRTC Community**: For real-time communication standards
- **Kubernetes Community**: For container orchestration
- **AI Service Providers**: Deepgram, Groq, ElevenLabs, Azure, Google Cloud
- **Open Source Projects**: Whisper, Piper, Redpanda, Prometheus

---

## Support

For questions, issues, or contributions:
- **Issues**: [GitHub Issues](https://github.com/dharsan99/Dharsan-VoiceAgent-Backend/issues)
- **Discussions**: [GitHub Discussions](https://github.com/dharsan99/Dharsan-VoiceAgent-Backend/discussions)
- **Documentation**: See the [Documentation](#documentation) section above

---

**Ready to build amazing voice AI experiences!**