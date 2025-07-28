# WHIP Implementation with Transcript Support

This document explains how to set up and use the WHIP (WebRTC-HTTP Ingestion Protocol) implementation with transcript functionality.

## 🏗️ Architecture

The WHIP implementation uses a dual-server architecture:

1. **Go Media Server** (port 8080) - Handles WHIP protocol and WebRTC audio streaming
2. **Python Backend** (port 8000) - Handles AI pipeline (STT, LLM, TTS) and WebSocket for transcripts

```
Frontend (WHIP Hook)
    ↓
Go Media Server (port 8080) - WHIP/WebRTC
    ↓ (audio streaming)
Python Backend (port 8000) - AI Pipeline
    ↓ (transcripts via WebSocket)
Frontend (transcript display)
```

## 🚀 Quick Start

### 1. Start Both Servers

```bash
cd v2
./start_servers.sh
```

This script will:
- Start Redpanda (Kafka) for message queuing
- Start the Go Media Server on port 8080
- Start the Python Backend on port 8000
- Set up all necessary connections

### 2. Test the Servers

Before testing the frontend, verify both servers are running:

```bash
python test_servers.py
```

This will test:
- Go Media Server connectivity (port 8080)
- Python Backend WebSocket (port 8000)
- Health endpoints

### 3. Test the Frontend

1. Open your frontend application
2. Navigate to the V2 Dashboard
3. Click "Start Conversation" to establish WHIP connection
4. Click "Start Listening" to begin voice activity detection
5. Speak into your microphone
6. Transcripts should appear in the transcript panel

## 🔧 Manual Setup

If you prefer to start servers manually:

### Start Go Media Server
```bash
cd v2/media-server
./media-server
```

### Start Python Backend
```bash
cd v2
source venv/bin/activate
python main.py
```

### Start Redpanda (Kafka)
```bash
cd v2
docker-compose up -d redpanda
```

## 📡 How It Works

### 1. WHIP Connection (Audio)
- Frontend establishes WebRTC connection via WHIP protocol
- Audio streams from browser to Go Media Server
- Media Server processes audio and can echo it back

### 2. WebSocket Connection (Transcripts)
- Frontend establishes WebSocket connection to Python Backend
- Python Backend runs AI pipeline:
  - **Speech-to-Text**: Deepgram Nova-3
  - **Language Model**: Groq Llama 3
  - **Text-to-Speech**: ElevenLabs
- Transcripts sent back via WebSocket

### 3. Dual Connection Benefits
- **Low Latency**: WHIP provides ultra-low latency audio streaming
- **AI Processing**: WebSocket enables full AI pipeline with transcripts
- **Scalability**: Separate concerns allow independent scaling

## 🐛 Troubleshooting

### No Transcripts Appearing

1. **Check WebSocket Connection**
   ```javascript
   // In browser console
   console.log('WebSocket state:', websocket.readyState);
   ```

2. **Check Python Backend**
   - Ensure it's running on port 8000
   - Check logs for WebSocket connections
   - Verify API keys are set

3. **Check Go Media Server**
   - Ensure it's running on port 8080
   - Check logs for WHIP connections

### Audio Issues

1. **Check WHIP Connection**
   - Verify Go Media Server is running
   - Check browser console for WebRTC errors

2. **Check Microphone Permissions**
   - Ensure browser has microphone access
   - Check browser console for media errors

### Environment Variables

Ensure these are set:
```bash
export DEEPGRAM_API_KEY="your_deepgram_key"
export GROQ_API_KEY="your_groq_key"
export ELEVENLABS_API_KEY="your_elevenlabs_key"
```

## 🔍 Debugging

### Frontend Logs
The WHIP hook provides detailed logging:
- `🚀 NEW HOOK FILE LOADED` - Hook initialization
- `🔗 Starting WHIP connection` - WHIP connection start
- `📡 Sending WHIP request` - WHIP request details
- `🔌 Establishing WebSocket connection` - WebSocket connection
- `📨 WebSocket message received` - Transcript messages

### Backend Logs
- **Go Media Server**: Check terminal for WHIP connection logs
- **Python Backend**: Check terminal for WebSocket and AI pipeline logs

## 📊 Performance

### Expected Latency
- **Audio Streaming**: <50ms (WHIP)
- **Transcript Generation**: 200-500ms (AI pipeline)
- **Total Response Time**: <1 second

### Optimization Tips
1. Use high-quality microphone
2. Ensure stable internet connection
3. Close unnecessary browser tabs
4. Use modern browser (Chrome/Firefox)

## 🔄 Next Steps

### Phase 2 Integration
The current implementation uses echo processing. For full AI integration:

1. **Enable Kafka Integration**: Connect Go Media Server to AI pipeline
2. **Audio Processing**: Route audio through STT → LLM → TTS
3. **Real-time Response**: Stream AI-generated audio back via WebRTC

### Advanced Features
- **Interruption Handling**: Detect and handle user interruptions
- **Context Management**: Maintain conversation context
- **Multi-modal Support**: Add video and other media types
- **Scalability**: Add load balancing and clustering

## 📚 Resources

- [WHIP Protocol Specification](https://www.ietf.org/archive/id/draft-ietf-wish-whip-01.html)
- [WebRTC Documentation](https://webrtc.org/)
- [Deepgram API](https://developers.deepgram.com/)
- [Groq API](https://console.groq.com/)
- [ElevenLabs API](https://elevenlabs.io/) 