# Quick Start Guide - WHIP with Transcripts

## 🎉 Current Status

✅ **Go Media Server** (port 8080) - Running and working  
✅ **Python Backend** (port 8000) - Running but needs API keys for transcripts  
✅ **WHIP Connection** - Should work now  
⚠️ **Transcripts** - Need API keys to be set

## 🚀 Test the WHIP Connection

The WHIP connection should work now! Try:

1. Open your frontend application
2. Navigate to V2 Dashboard
3. Click "Start Conversation"
4. You should see successful WHIP connection logs

## 🔑 Set Up API Keys for Transcripts

To get transcripts working, you need to set up API keys:

### 1. Get API Keys

- **Deepgram**: [Get API Key](https://console.deepgram.com/)
- **Groq**: [Get API Key](https://console.groq.com/)
- **ElevenLabs**: [Get API Key](https://elevenlabs.io/)

### 2. Set Environment Variables

```bash
# Create .env file
cp env.example .env

# Edit .env file with your actual API keys
export DEEPGRAM_API_KEY="your_actual_deepgram_key"
export GROQ_API_KEY="your_actual_groq_key"
export ELEVENLABS_API_KEY="your_actual_elevenlabs_key"
```

### 3. Restart the Backend

```bash
# Stop current backend
pkill -f "python.*main.py"

# Start with new environment
source venv/bin/activate
export DEEPGRAM_API_KEY="your_key"
export GROQ_API_KEY="your_key"
export ELEVENLABS_API_KEY="your_key"
python main.py
```

## 🧪 Test Everything

Once API keys are set:

1. **Test servers**: `python test_servers.py`
2. **Test frontend**: Start conversation and speak
3. **Check logs**: Look for transcript messages

## 🔧 Troubleshooting

### WHIP Connection Fails
- Ensure Go Media Server is running: `curl http://localhost:8080/`
- Check browser console for WebRTC errors

### No Transcripts
- Verify API keys are set: `echo $DEEPGRAM_API_KEY`
- Check backend logs for API errors
- Ensure WebSocket connection is established

### Audio Issues
- Check microphone permissions in browser
- Verify audio tracks are being added to WebRTC

## 📊 Expected Behavior

### With API Keys Set:
- ✅ WHIP connection established
- ✅ WebSocket connection established
- ✅ Audio streaming to both servers
- ✅ Transcripts appear in real-time
- ✅ AI responses generated

### Without API Keys:
- ✅ WHIP connection established
- ✅ Audio streaming to Go Media Server
- ❌ No transcripts (WebSocket rejects connection)
- ❌ No AI responses

## 🎯 Next Steps

1. **Test WHIP connection** (should work now)
2. **Set up API keys** for full functionality
3. **Test complete pipeline** with transcripts
4. **Enjoy your voice agent!**

## 📞 Support

If you encounter issues:
1. Check server logs
2. Verify all services are running
3. Ensure API keys are valid
4. Check browser console for errors 