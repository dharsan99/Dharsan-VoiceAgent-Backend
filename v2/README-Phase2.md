# Voice Agent Phase 2: AI-Powered Conversational Agent

## Overview

Phase 2 evolves the simple "parrot" echo service from Phase 1 into a fully intelligent conversational AI agent. This implementation introduces a decoupled microservices architecture with **Google Cloud managed AI services** for Speech-to-Text (STT), Large Language Model (LLM), and Text-to-Speech (TTS).

## Architecture

### Components

1. **React Frontend** (Unchanged from Phase 1)
   - Captures user audio via WebRTC/WHIP
   - Displays audio visualization and controls
   - Communicates with Media Server

2. **Media Server (Go)**
   - Manages WebRTC connections
   - Publishes incoming audio to `audio-in` topic
   - Consumes AI-generated audio from `audio-out` topic
   - Streams audio back to client

3. **Redpanda Message Bus**
   - Kafka-compatible streaming platform
   - `audio-in` topic: Raw Opus packets from Media Server
   - `audio-out` topic: Synthesized audio from Orchestrator

4. **Orchestrator (Go)**
   - Core AI processing hub
   - Consumes audio from `audio-in`
   - Processes through STT → LLM → TTS pipeline
   - Publishes synthesized audio to `audio-out`

5. **Google Cloud AI Services**
   - **Google Speech-to-Text**: Converts audio to text
   - **Google Generative AI (Gemini)**: Generates conversational responses
   - **Google Text-to-Speech**: Converts text back to speech

## Setup Instructions

### Prerequisites

- Docker and Docker Compose
- Go 1.24.5+
- Node.js 18+ (for frontend)
- Google Cloud account with the following APIs enabled:
  - Speech-to-Text API
  - Text-to-Speech API
  - Generative Language API
- Google API Key for Gemini (from Google AI Studio)

### Step 1: Set up Redpanda Message Bus

```bash
# Start Redpanda
cd v2
docker compose up -d

# Wait for Redpanda to be healthy, then create topics
docker exec -it $(docker ps -q --filter "name=redpanda") rpk topic create audio-in
docker exec -it $(docker ps -q --filter "name=redpanda") rpk topic create audio-out
```

### Step 2: Configure Environment Variables

#### Media Server
No additional configuration needed - it will automatically fall back to echo mode if Kafka is unavailable.

#### Orchestrator
Copy the example environment file and configure your Google Cloud credentials:

```bash
cd v2/orchestrator
cp env.example .env
```

Edit `.env` with your actual credentials:

```env
# Kafka/Redpanda Configuration
KAFKA_BROKERS=localhost:9092

# Google Cloud Configuration
# Path to your Google Cloud service account JSON file (for STT and TTS)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/speechtotext-466820-7aba77a3b0a0.json

# Google API Key for Generative AI (Gemini)
# Get this from: https://makersuite.google.com/app/apikey
GOOGLE_API_KEY=your-actual-google-api-key

# AI Service Configuration
STT_MODEL=latest_long
LLM_MODEL=gemini-1.5-flash
TTS_VOICE=en-US-Neural2-A
TTS_LANGUAGE=en-US
```

### Step 3: Build and Start Services

#### Media Server
```bash
cd v2/media-server
go build -o media-server
./media-server
```

#### Orchestrator
```bash
cd v2/orchestrator
go build -o orchestrator
./orchestrator
```

#### Frontend (if not already running)
```bash
cd ../Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend
npm install
npm run dev
```

### Step 4: Test the System

1. Open the frontend in your browser
2. Allow microphone access
3. Click "Start Streaming"
4. Speak into the microphone
5. You should hear the AI's response after processing

## API Endpoints

### Media Server
- `POST /whip` - WHIP protocol endpoint
- `GET /health` - Health check (shows AI status)
- `GET /metrics` - Server metrics
- `GET /` - Root endpoint with service info

### Health Check Response
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "phase": "2",
  "kafka": "connected",
  "ai_enabled": true
}
```

## Development

### Project Structure

```
v2/
├── docker-compose.yml          # Redpanda setup
├── media-server/               # Go media server
│   ├── main.go
│   ├── internal/
│   │   ├── kafka/             # Kafka integration
│   │   ├── server/            # HTTP server
│   │   ├── whip/              # WHIP protocol handler
│   │   └── webrtc/            # WebRTC configuration
│   └── pkg/
│       ├── config/            # Configuration
│       └── logger/            # Logging
└── orchestrator/              # Go orchestrator
    ├── main.go
    ├── internal/
    │   ├── ai/                # Google AI service integration
    │   ├── kafka/             # Kafka operations
    │   ├── logger/            # Logging
    │   └── session/           # Audio session management
    └── pkg/
        └── config/            # Configuration
```

### Key Features

#### Graceful Fallback
- Media Server automatically falls back to echo mode if Kafka is unavailable
- Health endpoint shows current mode (AI enabled/disabled)

#### Session Management
- Each WebRTC connection gets a unique session ID
- Audio is buffered per session for optimal processing
- Sessions are automatically cleaned up after inactivity

#### Error Handling
- Comprehensive error handling and logging
- Graceful degradation when AI services are unavailable
- Automatic retry mechanisms for transient failures

#### Performance Optimizations
- Audio buffering to ensure sufficient data for STT
- Concurrent processing of multiple sessions
- Efficient memory management with session cleanup

## Troubleshooting

### Common Issues

1. **Redpanda Connection Failed**
   - Ensure Docker is running
   - Check if ports 9092, 8081 are available
   - Verify Redpanda container is healthy

2. **Google AI Services Not Working**
   - Check Google API key in `.env` file
   - Verify Google Cloud credentials path
   - Ensure required APIs are enabled in Google Cloud Console
   - Check if service account has proper permissions

3. **No Audio Response**
   - Check orchestrator logs for errors
   - Verify Kafka topics exist
   - Check if audio is being published to `audio-in`

4. **High Latency**
   - Monitor Kafka message throughput
   - Check Google AI service response times
   - Consider adjusting audio buffer sizes

### Logs

#### Media Server
```bash
cd v2/media-server
./media-server
```

#### Orchestrator
```bash
cd v2/orchestrator
./orchestrator
```

Both services use structured JSON logging for easy debugging.

## Google Cloud Setup

### Required APIs
Enable the following APIs in your Google Cloud Console:
- Speech-to-Text API
- Text-to-Speech API
- Generative Language API

### Service Account Setup
1. Create a service account in Google Cloud Console
2. Download the JSON credentials file
3. Set the path in `GOOGLE_APPLICATION_CREDENTIALS`

### Gemini API Key
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Set it in `GOOGLE_API_KEY`

## Next Steps

### Phase 3 Considerations
- Implement streaming STT for lower latency
- Add conversation context management
- Implement user authentication
- Add conversation analytics
- Optimize audio codec handling
- Add support for multiple languages

### Production Deployment
- Use Kubernetes for orchestration
- Implement proper monitoring and alerting
- Add rate limiting and security measures
- Use managed Kafka service (e.g., Confluent Cloud)
- Implement proper secrets management

## Performance Metrics

### Target Latencies
- **Time to First Sound**: < 2 seconds
- **End-to-End Response**: < 3 seconds
- **Audio Quality**: 16kHz, 16-bit PCM

### Scalability
- Supports multiple concurrent sessions
- Horizontally scalable architecture
- Independent scaling of Media Server and Orchestrator

## Security Considerations

- API keys stored in environment variables
- No sensitive data logged
- CORS properly configured
- Input validation on all endpoints
- Rate limiting recommended for production

---

This Phase 2 implementation provides a solid foundation for a production-ready voice AI system using **Google Cloud's comprehensive AI services**, with proper separation of concerns, error handling, and scalability considerations. 