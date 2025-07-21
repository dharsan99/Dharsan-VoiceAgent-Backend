# Dharsan-VoiceAgent-Backend

A high-performance, serverless voice AI backend built with Python, FastAPI, and Modal. This project orchestrates real-time audio processing through a sophisticated pipeline of AI services, demonstrating advanced asynchronous programming patterns and ultra-low latency communication.

## 🚀 Features

- **Real-time Audio Processing**: WebSocket-based streaming with sub-300ms latency
- **Asynchronous AI Pipeline**: Concurrent STT, LLM, and TTS processing
- **Serverless Architecture**: Deployed on Modal for automatic scaling
- **Advanced Conversation Management**: Interruption handling and context memory
- **Production Ready**: Secure secrets management and error handling
- **High Performance**: Optimized for real-time voice interactions

## 🏗️ Architecture

### Technology Stack
- **Framework**: FastAPI with WebSocket support
- **Platform**: Modal (serverless Python)
- **AI Services**: 
  - Deepgram Nova-3 (Speech-to-Text)
  - Groq Llama 3 (Large Language Model)
  - ElevenLabs (Text-to-Speech)
- **Communication**: WebSocket for real-time bidirectional streaming
- **Async Processing**: asyncio with producer-consumer queues

### System Architecture

```
Client ←→ WebSocket ←→ FastAPI Server ←→ AI Pipeline
                    ↓
              asyncio.Queue System
                    ↓
        STT → LLM → TTS → Audio Output
```

### Core Components

```
├── main.py                    # Modal app and FastAPI server
├── requirements.txt           # Python dependencies
├── config/
│   └── settings.py           # Configuration management
├── services/
│   ├── stt_service.py        # Deepgram STT integration
│   ├── llm_service.py        # Groq LLM integration
│   └── tts_service.py        # ElevenLabs TTS integration
├── utils/
│   ├── audio_processor.py    # Audio format handling
│   └── conversation.py       # Conversation memory
└── tests/
    └── test_pipeline.py      # Pipeline testing
```

## 📋 Prerequisites

- Python 3.9+
- Modal CLI installed and authenticated
- API keys for:
  - Deepgram (Nova-3)
  - Groq (Llama 3)
  - ElevenLabs

## 🛠️ Installation & Setup

### 1. Install Modal CLI

```bash
pip install modal
modal token new
```

### 2. Clone and Setup Project

```bash
cd Dharsan-VoiceAgent-Backend
pip install -r requirements.txt
```

### 3. Configure Secrets

Create secrets in Modal dashboard or via CLI:

```bash
modal secret create voice-ai-secrets \
  DEEPGRAM_API_KEY=your_deepgram_key \
  GROQ_API_KEY=your_groq_key \
  ELEVENLABS_API_KEY=your_elevenlabs_key
```

### 4. Environment Variables

Create `.env` file for local development:

```env
DEEPGRAM_API_KEY=your_deepgram_key
GROQ_API_KEY=your_groq_key
ELEVENLABS_API_KEY=your_elevenlabs_key
```

## 🎯 Core Implementation Details

### Modal App Configuration

```python
import modal

# Define container image with all dependencies
image = modal.Image.debian_slim().pip_install([
    "fastapi",
    "websockets",
    "deepgram-sdk",
    "groq",
    "elevenlabs",
    "python-multipart"
])

# Create Modal app
app = modal.App("voice-ai-backend")

# WebSocket endpoint
@app.asgi_app(image=image, secrets=[modal.Secret.from_name("voice-ai-secrets")])
def fastapi_app():
    from fastapi import FastAPI, WebSocket
    from fastapi.middleware.cors import CORSMiddleware
    
    app = FastAPI(title="Voice AI Backend")
    
    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app
```

### Asynchronous Pipeline Architecture

The core innovation is the queue-based producer-consumer pattern:

```python
import asyncio
from typing import Dict, Any

class VoiceAIPipeline:
    def __init__(self):
        self.stt_to_llm_queue = asyncio.Queue()
        self.llm_to_tts_queue = asyncio.Queue()
        self.tts_to_client_queue = asyncio.Queue()
        self.conversation_memory = []
        self.is_ai_speaking = False

    async def handle_websocket(self, websocket: WebSocket):
        await websocket.accept()
        
        # Launch concurrent pipeline tasks
        tasks = [
            self.audio_receiver_task(websocket),
            self.stt_processor_task(),
            self.llm_processor_task(),
            self.tts_processor_task(),
            self.audio_sender_task(websocket)
        ]
        
        await asyncio.gather(*tasks)
```

### Speech-to-Text Integration (Deepgram)

```python
import asyncio
from deepgram import DeepgramClient, LiveTranscriptionEvents

class STTService:
    def __init__(self, api_key: str):
        self.deepgram = DeepgramClient(api_key)
    
    async def process_audio_stream(self, audio_queue: asyncio.Queue, 
                                 transcript_queue: asyncio.Queue):
        connection = self.deepgram.listen.live({
            "model": "nova-3",
            "language": "en-US",
            "interim_results": True,
            "endpointing": 200
        })
        
        async def on_message(self, result, **kwargs):
            if result.is_final:
                await transcript_queue.put(result.channel.alternatives[0].transcript)
        
        connection.on(LiveTranscriptionEvents.Transcript, on_message)
        
        # Stream audio from queue to Deepgram
        while True:
            audio_chunk = await audio_queue.get()
            connection.send(audio_chunk)
```

### Large Language Model Integration (Groq)

```python
import groq
from typing import List

class LLMService:
    def __init__(self, api_key: str):
        self.client = groq.Groq(api_key=api_key)
    
    async def generate_response(self, user_input: str, 
                              conversation_history: List[str]) -> str:
        # Build context-aware prompt
        context = self._build_context(conversation_history)
        prompt = f"{context}\nUser: {user_input}\nAssistant:"
        
        # Stream response from Groq
        response = self.client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            temperature=0.7,
            max_tokens=150
        )
        
        full_response = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content
        
        return full_response
```

### Text-to-Speech Integration (ElevenLabs)

```python
import elevenlabs
from elevenlabs import generate, stream

class TTSService:
    def __init__(self, api_key: str):
        elevenlabs.set_api_key(api_key)
    
    async def synthesize_speech(self, text: str, 
                               audio_queue: asyncio.Queue):
        # Stream audio from ElevenLabs
        audio_stream = generate(
            text=text,
            voice="Josh",  # Customizable voice
            model="eleven_monolingual_v1",
            stream=True
        )
        
        for chunk in audio_stream:
            await audio_queue.put(chunk)
```

### Conversation Memory Management

```python
class ConversationManager:
    def __init__(self, max_history: int = 10):
        self.history = []
        self.max_history = max_history
    
    def add_exchange(self, user_input: str, ai_response: str):
        self.history.append({
            "user": user_input,
            "assistant": ai_response,
            "timestamp": datetime.utcnow()
        })
        
        # Maintain history size
        if len(self.history) > self.max_history:
            self.history.pop(0)
    
    def get_context_summary(self) -> str:
        if not self.history:
            return ""
        
        # Create context from recent exchanges
        recent_exchanges = self.history[-3:]  # Last 3 exchanges
        context = "\n".join([
            f"User: {ex['user']}\nAssistant: {ex['assistant']}"
            for ex in recent_exchanges
        ])
        
        return f"Previous conversation:\n{context}\n"
```

## 🚀 Deployment

### Deploy to Modal

```bash
# Deploy the application
modal deploy main.py

# The output will include your WebSocket URL:
# wss://your-app-name.modal.run
```

### Environment Configuration

| Secret Name | Description | Required |
|-------------|-------------|----------|
| `DEEPGRAM_API_KEY` | Deepgram Nova-3 API key | Yes |
| `GROQ_API_KEY` | Groq API key for Llama 3 | Yes |
| `ELEVENLABS_API_KEY` | ElevenLabs API key | Yes |

### Monitoring and Logs

```bash
# View application logs
modal logs voice-ai-backend

# Monitor function executions
modal app list
```

## 🧪 Testing

### Unit Tests

```bash
python -m pytest tests/
```

### Integration Tests

```bash
# Test WebSocket connection
python tests/test_websocket.py

# Test AI pipeline
python tests/test_pipeline.py
```

### Performance Testing

```bash
# Latency testing
python tests/test_latency.py

# Load testing
python tests/test_load.py
```

## 🔧 Development

### Project Structure

```
├── main.py                    # Entry point and Modal app
├── requirements.txt           # Dependencies
├── config/
│   ├── __init__.py
│   └── settings.py           # Configuration
├── services/
│   ├── __init__.py
│   ├── stt_service.py        # Deepgram integration
│   ├── llm_service.py        # Groq integration
│   └── tts_service.py        # ElevenLabs integration
├── utils/
│   ├── __init__.py
│   ├── audio_processor.py    # Audio utilities
│   └── conversation.py       # Conversation management
├── tests/
│   ├── __init__.py
│   ├── test_pipeline.py      # Pipeline tests
│   └── test_websocket.py     # WebSocket tests
└── .env                      # Local environment variables
```

### Key Dependencies

```txt
fastapi>=0.104.0
websockets>=12.0
deepgram-sdk>=2.12.0
groq>=0.4.0
elevenlabs>=0.2.0
python-multipart>=0.0.6
pydantic>=2.0.0
asyncio-mqtt>=0.16.0
```

## 📊 Performance Optimization

### Latency Budget

| Component | Target Latency | Optimization Strategy |
|-----------|----------------|----------------------|
| Audio Capture | <20ms | AudioWorklet on client |
| Network (Up) | 20-50ms | Optimize connection |
| STT (Deepgram) | 50-100ms | Streaming with interim results |
| LLM (Groq) | 50-150ms | Time-to-first-token optimization |
| TTS (ElevenLabs) | 80-200ms | Streaming audio chunks |
| Network (Down) | 20-50ms | Optimize connection |
| Audio Playback | 20-50ms | Minimal buffering |
| **Total** | **<300ms** | Concurrent processing |

### Optimization Techniques

1. **Concurrent Processing**: All AI services run simultaneously
2. **Streaming**: No waiting for complete responses
3. **Queue Management**: Efficient producer-consumer pattern
4. **Connection Pooling**: Reuse WebSocket connections
5. **Audio Optimization**: 16kHz, 16-bit PCM format

## 🔒 Security

### Security Measures

- **API Key Management**: Secure secrets in Modal
- **Input Validation**: Pydantic models for data validation
- **Rate Limiting**: Prevent abuse
- **CORS Configuration**: Secure cross-origin requests
- **Error Handling**: No sensitive data in error messages

### Best Practices

```python
# Secure API key handling
api_key = os.environ.get("DEEPGRAM_API_KEY")
if not api_key:
    raise ValueError("DEEPGRAM_API_KEY not configured")

# Input validation
from pydantic import BaseModel

class AudioChunk(BaseModel):
    data: bytes
    timestamp: float
    sample_rate: int = 16000
```

## 🐛 Troubleshooting

### Common Issues

1. **WebSocket Connection Failures**
   - Check Modal deployment status
   - Verify CORS configuration
   - Ensure HTTPS/WSS connection

2. **High Latency**
   - Monitor network quality
   - Check AI service status
   - Verify concurrent processing

3. **Audio Quality Issues**
   - Check audio format (16kHz, 16-bit PCM)
   - Verify microphone permissions
   - Monitor audio buffer sizes

### Debug Mode

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Add debug endpoints
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}
```

## 📈 Monitoring & Analytics

### Metrics to Track

- **End-to-end Latency**: Target <300ms
- **WebSocket Connection Stability**: 99.9% uptime
- **AI Service Response Times**: Monitor each service
- **Error Rates**: Track and alert on failures
- **Audio Quality**: Monitor audio processing success

### Logging

```python
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

async def log_pipeline_metrics(stage: str, duration: float):
    logger.info(f"Pipeline stage {stage} completed in {duration:.2f}ms")
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🔗 Related Projects

- [Dharsan-VoiceAgent-Frontend](../Dharsan-VoiceAgent-Frontend) - React/TypeScript frontend
- [Real-time AI Audio Demo Guide](../Dharsan-VoiceAgent-Frontend/Real-time%20AI%20Audio%20Demo_.pdf) - Implementation guide

---

**Built with ❤️ for demonstrating advanced real-time voice AI capabilities**