# Voice AI Backend - Versioned Architecture

This project now supports multiple versions of the Voice AI backend, allowing for easy switching between different implementations and gradual migration to new features.

## 📁 Directory Structure

```
Dharsan-VoiceAgent-Backend/
├── main.py                 # Version router (routes to v1 or v2)
├── v1/                     # Legacy implementation
│   ├── main.py            # Original voice AI implementation
│   ├── main_backup.py     # Backup of original implementation
│   ├── requirements.txt   # V1 dependencies
│   └── deploy.sh          # V1 deployment script
├── v2/                     # New modular implementation
│   ├── main.py            # Clean, modular voice AI v2.0
│   ├── requirements.txt   # V2 dependencies
│   └── deploy.sh          # V2 deployment script
└── VERSIONING.md          # This file
```

## 🔄 Version Comparison

### V1 (Legacy)
- **Status**: Stable, Production Ready
- **Features**: 
  - Basic voice AI functionality
  - WebSocket communication
  - ElevenLabs TTS integration
  - Groq LLM integration
  - Deepgram STT
  - Error handling and recovery
- **Architecture**: Monolithic
- **Use Case**: Production environments, stability-focused

### V2 (Advanced)
- **Status**: Beta, Feature Rich
- **Features**:
  - Modular architecture
  - Enhanced session management
  - Multi-provider TTS support
  - Improved error handling
  - Better WebSocket management
  - Session analytics
  - Heartbeat and auto-reconnection
- **Architecture**: Modular, Service-oriented
- **Use Case**: Development, new features, scalability

## 🚀 Deployment

### Deploy All Versions
```bash
# Deploy the version router (supports both v1 and v2)
modal deploy main.py
```

### Deploy Specific Version
```bash
# Deploy V1 only
cd v1
./deploy.sh

# Deploy V2 only
cd v2
./deploy.sh
```

## 🌐 API Endpoints

### Version Router (main.py)
- `GET /` - Version information and router
- `GET /versions` - Detailed version comparison
- `GET /health` - Router health check
- `GET /v1/*` - Proxy to V1 endpoints
- `GET /v2/*` - Proxy to V2 endpoints

### V1 Endpoints
- `WS /ws` - WebSocket connection
- `GET /health` - Health check
- `GET /errors` - Error statistics

### V2 Endpoints
- `WS /ws/v2` - WebSocket connection
- `GET /v2/health` - Health check
- `GET /v2/sessions` - Session information
- `GET /v2/config` - Configuration details

## 🎯 Frontend Integration

The frontend now includes a version switcher that allows users to choose between V1 and V2:

### Version Switcher Component
- Displays available versions
- Shows version status (stable/beta)
- Allows easy switching
- Maintains separate state for each version

### V1 Frontend
- Uses `useVoiceAgent` hook
- Original UI and functionality
- Stable, tested interface

### V2 Frontend
- Uses `useVoiceAgentV2` hook
- Enhanced UI with session info
- Better error handling
- Improved user experience

## 🔧 Configuration

### Environment Variables
Both versions use the same environment variables:
- `DEEPGRAM_API_KEY` - Speech-to-text
- `GROQ_API_KEY` - Language model
- `ELEVENLABS_API_KEY` - Text-to-speech
- `AZURE_SPEECH_KEY` - Alternative TTS (V2)

### Version-Specific Settings
- V1: Uses hardcoded configuration
- V2: Supports dynamic configuration via `/v2/config` endpoint

## 📊 Monitoring

### V1 Monitoring
- Basic health checks
- Error statistics
- Connection status

### V2 Monitoring
- Enhanced health checks
- Session analytics
- Real-time metrics
- Performance monitoring

## 🔄 Migration Guide

### From V1 to V2
1. **Backend Migration**:
   ```bash
   # Deploy V2 alongside V1
   cd v2
   ./deploy.sh
   
   # Test V2 endpoints
   curl https://your-app.modal.run/v2/health
   ```

2. **Frontend Migration**:
   ```typescript
   // Switch to V2 in your app
   setCurrentVersion('v2');
   ```

3. **Gradual Rollout**:
   - Deploy both versions
   - Test V2 with subset of users
   - Monitor performance and errors
   - Gradually migrate users

### Rollback Strategy
If issues arise with V2:
1. Switch back to V1 immediately
2. Investigate V2 issues
3. Fix and redeploy V2
4. Resume migration

## 🛠️ Development

### Adding New Features
1. **V1**: Add to existing monolithic structure
2. **V2**: Create new service modules
3. **Testing**: Test both versions
4. **Deployment**: Deploy to appropriate version

### Code Organization
- **V1**: Single file with all functionality
- **V2**: Modular structure with separate services:
  - `VoiceService` - TTS functionality
  - `AIService` - LLM interactions
  - `STTService` - Speech recognition
  - `SessionManager` - Session handling

## 📈 Performance Comparison

| Metric | V1 | V2 |
|--------|----|----|
| Startup Time | Fast | Moderate |
| Memory Usage | Low | Moderate |
| Scalability | Limited | High |
| Feature Set | Basic | Advanced |
| Stability | High | Moderate |
| Maintainability | Low | High |

## 🎯 Recommendations

### Use V1 When:
- You need maximum stability
- Running in production
- Simple voice AI requirements
- Limited resources

### Use V2 When:
- You need advanced features
- Developing new functionality
- Planning to scale
- Want better maintainability

## 🔮 Future Plans

### V3 Roadmap
- Microservices architecture
- Kubernetes deployment
- Advanced analytics
- Multi-tenant support
- Plugin system

### Migration Timeline
- **Phase 1**: V1 + V2 coexistence ✅
- **Phase 2**: V2 feature parity
- **Phase 3**: V2 as default
- **Phase 4**: V1 deprecation
- **Phase 5**: V3 development

## 📞 Support

For questions about versioning:
1. Check this documentation
2. Review version-specific README files
3. Test both versions locally
4. Contact the development team

---

**Note**: This versioned approach ensures backward compatibility while allowing for innovation and improvement. Choose the version that best fits your needs! 