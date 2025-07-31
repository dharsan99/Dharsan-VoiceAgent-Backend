# Dharsan Voice Agent - V3 Backend

## Version 3 Architecture Overview

V3 represents a complete evolution of the voice agent system with **extreme performance optimization** and **ultra-low latency** capabilities. This version focuses on achieving sub-100ms end-to-end latency through advanced model selection, optimization techniques, and architectural innovations.

### Core Pipeline Architecture

The voice agent's functionality is realized through a sequential pipeline of three distinct machine learning stages:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CORE AI PIPELINE                                  │
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Stage 1   │───►│   Stage 2   │───►│   Stage 3   │───►│   Output    │  │
│  │     ASR     │    │     NLP     │    │     TTS     │    │   Audio     │  │
│  │< 30ms       │    │< 20ms       │    │< 50ms       │    │  Stream     │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                             │
│  NVIDIA Parakeet    Super Tiny LM      Zonos-v0.1      HTTP Streaming     │
│  TDT-0.6B-v2        (Intent Class.)    (Voice Clone)    Response           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Stage 1: Instantaneous Speech Recognition (ASR)

**Model**: NVIDIA Parakeet-TDT-0.6B-v2  
**Target Latency**: < 30ms  
**Key Features**:
- **FastConformer Encoder**: Optimized Conformer with efficient downsampling
- **Token-and-Duration Transducer (TDT)**: Frame-skipping capability for ultra-low latency
- **Real-Time Factor**: 3380x (56 minutes of audio per second)
- **Word Error Rate**: 6.05% (clean audio)

**Implementation**: RealtimeSTT with KoljaB/RealtimeSTT library
- Two-stage Voice Activity Detection (VAD)
- WebRTCVAD + SileroVAD for noise filtering
- Streaming audio chunk processing

**Optimizations**:
- INT8 quantization for reduced memory footprint
- Structured pruning for faster inference
- CUDA Graph optimization for GPU acceleration

### Stage 2: On-Device Intent Recognition (NLP)

**Model**: Super Tiny Language Models (SLMs) < 2B parameters  
**Target Latency**: < 20ms  
**Key Features**:
- **Fine-tuned SLM**: HuggingFaceTB/SmolLM-1.7B or microsoft/phi-2
- **Local Pattern Capture**: Bi-LSTM for immediate trigger detection
- **Causal Self-Attention**: Incremental processing for real-time responses
- **Knowledge Distillation**: Teacher-student model optimization

**Advanced Logic**:
- Sub-sentence processing for instant responsiveness
- Rolling window pattern detection (3-5 tokens)
- Pre-emptive action triggering
- Continuous intent refinement

### Stage 3: Expressive, Low-Latency Speech Synthesis (TTS)

**Model**: Zonos-v0.1  
**Target Latency**: < 50ms (Time-to-First-Byte)  
**Key Features**:
- **Few-Shot Voice Cloning**: MAML-based meta-learning
- **Diffusion-Based Neural Vocoder**: High-fidelity 44kHz output
- **Streaming Inference**: Real-time audio generation
- **Apache 2.0 License**: Commercial-friendly

**Optimizations**:
- Lookahead modules for reduced TTFB
- Streaming audio chunk generation
- PyAudio integration for immediate playback

### Backend Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Load Balancer │    │   API Gateway   │
│   (React/TS)    │◄──►│   (Nginx/Envoy) │◄──►│   (Kong/Traefik)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                       ┌─────────────────────────────────────────────┐
                       │              Core Services                  │
                       │  ┌─────────────┐  ┌─────────────┐          │
                       │  │Orchestrator │  │Media Server │          │
                       │  │   (Go)     │  │   (Go)     │          │
                       │  └─────────────┘  └─────────────┘          │
                       │  ┌─────────────┐  ┌─────────────┐          │
                       │  │STT Service  │  │TTS Service  │          │
                       │  │  (Python)   │  │  (Python)   │          │
                       │  └─────────────┘  └─────────────┘          │
                       │  ┌─────────────┐  ┌─────────────┐          │
                       │  │NLP Service  │  │Logging      │          │
                       │  │  (Python)   │  │Service (Go) │          │
                       │  └─────────────┘  └─────────────┘          │
                       └─────────────────────────────────────────────┘
                                                       │
                       ┌─────────────────────────────────────────────┐
                       │            Infrastructure                  │
                       │  ┌─────────────┐  ┌─────────────┐          │
                       │  │   Kafka     │  │   Redis     │          │
                       │  │ (Streaming) │  │  (Cache)    │          │
                       │  └─────────────┘  └─────────────┘          │
                       │  ┌─────────────┐  ┌─────────────┐          │
                       │  │  ScyllaDB   │  │   MinIO     │          │
                       │  │ (Database)  │  │ (Storage)   │          │
                       │  └─────────────┘  └─────────────┘          │
                       └─────────────────────────────────────────────┘
```

### Key Improvements in V3

1. **Ultra-Low Latency Pipeline**
   - **Sub-100ms end-to-end latency**: ASR (30ms) + NLP (20ms) + TTS (50ms)
   - **Frame-skipping ASR**: NVIDIA Parakeet TDT for 3380x real-time factor
   - **Incremental NLP**: Causal self-attention for continuous processing
   - **Streaming TTS**: Time-to-First-Byte optimization with lookahead modules

2. **Advanced Model Optimization**
   - **INT8 Quantization**: Reduced memory footprint and faster inference
   - **Structured Pruning**: Maintains dense matrix structures for GPU efficiency
   - **Knowledge Distillation**: Teacher-student model optimization for SLMs
   - **CUDA Graph Optimization**: Eliminates kernel launch overhead

3. **Enhanced Microservices Architecture**
   - **BentoML Integration**: Standardized model packaging and deployment
   - **Independent Scaling**: GPU-optimized service allocation
   - **Circuit Breaker Patterns**: Improved fault tolerance
   - **Health Checks**: Comprehensive monitoring and alerting

4. **AI + Human Co-Pilot System**
   - **Seamless Handoff Protocol**: Context-aware human agent transfer
   - **Trigger Detection**: Multi-modal handoff triggers (keywords, sentiment, confidence)
   - **Conversation Context**: Complete interaction history preservation
   - **Real-time Routing**: Instant human agent notification

5. **RESTful API Design (No WebSockets)**
   - **HTTP Streaming**: Chunked Transfer Encoding for audio streams
   - **Asynchronous Processing**: Job-based interaction management
   - **FastAPI Framework**: High-performance async API development
   - **Universal Compatibility**: Works with any HTTP client

### Directory Structure

```
v3/
├── README.md                           # This file
├── docker-compose.yml                  # Local development setup
├── docker-compose.prod.yml            # Production setup
├── .env.example                       # Environment variables template
├── scripts/                           # Utility scripts
│   ├── setup.sh                       # Initial setup
│   ├── deploy.sh                      # Deployment script
│   ├── health-check.sh                # Health monitoring
│   ├── model-optimization.sh          # Model quantization/pruning
│   └── cleanup.sh                     # Cleanup utilities
├── k8s/                               # Kubernetes manifests
│   ├── base/                          # Base configurations
│   ├── overlays/                      # Environment overlays
│   └── monitoring/                    # Monitoring stack
├── services/                          # Microservices
│   ├── orchestrator/                  # Main orchestration service (Go)
│   ├── media-server/                  # WebRTC/WHIP handling (Go)
│   ├── stt-service/                   # ASR with Parakeet TDT (Python)
│   ├── nlp-service/                   # Intent classification with SLM (Python)
│   ├── tts-service/                   # TTS with Zonos voice cloning (Python)
│   ├── handoff-service/               # AI-Human handoff management (Go)
│   └── logging-service/               # Centralized logging (Go)
├── models/                            # Model artifacts and configurations
│   ├── asr/                           # Parakeet TDT model files
│   ├── nlp/                           # Fine-tuned SLM models
│   ├── tts/                           # Zonos model and voice embeddings
│   └── optimization/                  # Quantized/pruned model variants
├── shared/                            # Shared libraries
│   ├── proto/                         # Protocol buffers
│   ├── config/                        # Configuration management
│   ├── utils/                         # Common utilities
│   └── bentoml/                       # BentoML service templates
├── tests/                             # Integration tests
│   ├── e2e/                           # End-to-end pipeline tests
│   ├── performance/                   # Latency and throughput tests
│   ├── load/                          # Load testing scenarios
│   └── model/                         # Model accuracy and optimization tests
└── docs/                              # Documentation
    ├── api/                           # API documentation
    ├── deployment/                    # Deployment guides
    ├── model-optimization/            # Model optimization guides
    ├── handoff-protocol/              # AI-Human handoff documentation
    └── troubleshooting/               # Troubleshooting guides
```

### Quick Start

1. **Prerequisites**
   ```bash
   # Required tools
   - Docker & Docker Compose
   - Go 1.21+
   - Python 3.11+
   - Node.js 20+
   - kubectl (for K8s deployment)
   - NVIDIA GPU with CUDA 12.0+ (for optimal performance)
   - 16GB+ RAM (32GB recommended)
   ```

2. **Model Setup**
   ```bash
   cd v3
   # Download and optimize models
   ./scripts/model-optimization.sh
   # This will:
   # - Download Parakeet TDT model
   # - Fine-tune SLM for intent classification
   # - Set up Zonos TTS with voice cloning
   # - Apply INT8 quantization
   ```

3. **Local Development Setup**
   ```bash
   cd v3
   cp .env.example .env
   # Edit .env with your configuration
   ./scripts/setup.sh
   docker-compose up -d
   ```

4. **Production Deployment**
   ```bash
   cd v3
   ./scripts/deploy.sh
   ```

### Phased Development Roadmap

#### **Stage 1: 50% Completion (Core MVP Pipeline)**

**Technical Specifications**:
```python
# app.py (Monolithic Implementation)
from fastapi import FastAPI, UploadFile
from parakeet import ParakeetASR
from smol_lm import IntentClassifier
from zonos import ZonosTTS

app = FastAPI()
asr = ParakeetASR()
nlp = IntentClassifier()
tts = ZonosTTS()

@app.post("/process")
async def process_audio(audio: UploadFile):
    # Sequential pipeline (no optimizations)
    audio_data = await audio.read()
    text = asr.transcribe(audio_data)          # ~300ms latency
    intent = nlp.classify(text)                # ~150ms latency
    response_audio = tts.generate(intent.response)  # ~400ms latency
    return Response(response_audio, media_type="audio/wav")
```

**Optimization Focus**:  
- Use PyTorch's `torch.jit.trace` for model serialization (5-10% speedup)
- Implement batch size=1 for all models
- Basic SileroVAD for voice activity detection

**Goal**: Prove that audio can be processed from start to finish. Latency will be high (~850ms), but the pipeline works.

#### **Stage 2: 85% Completion (Optimized System)**

**Architecture Changes**:
```
services/
├── stt-service/     # BentoML bento (GPU optimized)
├── nlp-service/     # BentoML bento (CPU optimized)
├── tts-service/     # BentoML bento (GPU optimized)
└── orchestrator/    # FastAPI + Redis job queue
```

**Critical Optimizations**:
```python
# tts_service.py (BentoML Service)
import torch
from bentoml import service, artifacts, api
from transformers import pipeline

@service(resources={"gpu": 1, "gpu_type": "a100"})
class TTSService:
    def __init__(self):
        self.model = torch.compile(
            pipeline("text-to-speech", "Zyphra/Zonos-v0.1"),
            mode="max-autotune",
            fullgraph=True
        )
        # Warm-up with dynamic shape declaration
        warmup_input = torch.randint(0, 100, (1, 50))
        self.model(warmup_input)

    @api
    async def generate(self, text: str) -> bytes:
        with torch.inference_mode():
            # Pinned memory input
            inputs = tokenizer(text, return_tensors="pt").pin_memory().cuda()
            return self.model(**inputs).audio
```

**Performance Targets**:
| Component        | Optimization               | Latency Reduction |
|------------------|----------------------------|-------------------|
| ASR              | CUDA Graphs + INT8         | 300ms → 28ms      |
| NLP              | Knowledge Distillation     | 150ms → 18ms      |
| TTS              | Triton Kernels             | 400ms → 45ms      |
| Network Overhead | HTTP/2 Multiplexing        | 120ms → 9ms       |

**Goal**: Achieve **sub-100ms end-to-end latency**. The system is now fast, robust, and scalable.

#### **Stage 3: 100% Completion (Advanced Intelligence)**

**Key Implementations**:

1. **Tiered NLP Architecture**:
```python
class HybridNLP:
    def __init__(self):
        self.trigger_model = BiLSTM()  # <1MB model
        self.main_model = SmolLM1B()
    
    async def process(self, tokens: list[str]):
        # Parallel execution
        trigger_result = await self.trigger_model.predict(tokens[-3:])
        main_result = await self.main_model.predict(tokens)
        
        if trigger_result.confidence > 0.9:
            return HandoffAction(trigger_result.intent)
        return main_result
```

2. **RL Dialogue Policy**:
```python
# rl_agent.py
class DialogueAgent:
    def __init__(self):
        self.q_table = ScyllaDB("q_values")  # State-action store
        
    def choose_action(self, state: ConversationState):
        # State: [turn_count, intent_conf, sentiment]
        return self.q_table.get_optimal_action(state)
    
    def update_policy(self, reward: float):
        # Online TD-learning
        self.q_table.update(state, action, reward)
```

3. **Token-Level Monitoring**:
```python
# monitoring.py
class LatencyTracker:
    def record(self, stage: str, token: str, start: float):
        elapsed = time.perf_counter() - start
        Kafka.produce("latency_metrics", 
            json.dumps({
                "token": token,
                "stage": stage,
                "latency_ms": elapsed*1000
            })
        )
```

**Goal**: The system is not just fast, but also intelligent, adaptive, and fully observable for production.

### Cross-Phase Dependencies

| Phase | Backend Dependency | Frontend Dependency |
|-------|---------------------|---------------------|
| 2→1   | Async API spec ready | Web Audio API polyfills |
| 3→2   | RL policy service running | Zustand store structure |
| 3→1   | Token-level metrics API | Dashboard framework setup |

### Performance Validation Plan

**Stage 2 Verification**:
```bash
# Latency test script
hey -n 1000 -c 50 -m POST -D audio.wav http://api/process
```

**Metrics**:
- P99 latency < 100ms
- Error rate < 0.1%
- GPU util > 85%

**Stage 3 Validation**:
- A/B test conversation success rate (RL vs rule-based)
- WCAG 2.1 compliance audit
- Lighthouse PWA score > 90

### Monitoring

- **Health Dashboard**: http://localhost:3000/health
- **Metrics**: http://localhost:9090 (Prometheus)
- **Logs**: http://localhost:5601 (Kibana)
- **Tracing**: http://localhost:16686 (Jaeger)
- **Model Performance**: http://localhost:3000/model-metrics

### Performance Metrics

- **End-to-End Latency**: < 100ms (ASR: 30ms + NLP: 20ms + TTS: 50ms)
- **ASR Accuracy**: > 94% (Word Error Rate: 6.05%)
- **ASR Speed**: 3380x real-time factor (56 minutes/second)
- **TTS Quality**: High-fidelity 44kHz output with voice cloning
- **Concurrent Sessions**: 1000+ (scalable with GPU resources)
- **Uptime**: 99.9%
- **Model Memory**: < 2GB total (optimized with quantization)

### API Endpoints

- **POST /api/v1/interaction/start**: Start new conversation
- **GET /api/v1/interaction/result/{job_id}**: Stream audio response
- **POST /api/v1/handoff**: Trigger human agent handoff
- **GET /api/v1/health**: Service health check
- **GET /api/v1/metrics**: Performance metrics

### Development Guidelines

1. **Code Standards**
   - Go: Follow Go best practices and use `gofmt`
   - Python: Follow PEP 8 and use type hints
   - Use conventional commits
   - Write comprehensive tests

2. **Model Optimization**
   - Apply INT8 quantization to all models
   - Use structured pruning for size reduction
   - Implement CUDA Graph optimization
   - Monitor memory usage and latency

3. **API Design**
   - RESTful APIs with OpenAPI 3.0 specs
   - HTTP Streaming for audio responses
   - Asynchronous job-based processing
   - No WebSocket dependencies

4. **Performance Optimization**
   - Target sub-100ms end-to-end latency
   - Implement frame-skipping in ASR
   - Use incremental NLP processing
   - Optimize TTS Time-to-First-Byte

5. **Security**
   - Input validation on all endpoints
   - Rate limiting and DDoS protection
   - Secure headers and CORS policies
   - JWT-based authentication

### Troubleshooting

See `docs/troubleshooting/` for common issues and solutions.

### Support

For issues and questions:
- Create an issue in the repository
- Check the troubleshooting guides
- Review the API documentation

---

**Version**: 3.0.0  
**Last Updated**: July 2025  
**Maintainer**: Dharsan Kumar 