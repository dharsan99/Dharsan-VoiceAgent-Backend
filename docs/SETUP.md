# Quick Setup Guide - Voice AI Backend

This guide will help you get the Voice AI Backend up and running on Modal in minutes.

## 🚀 Prerequisites

1. **Python 3.9+** installed
2. **Modal CLI** installed and authenticated
3. **API Keys** for the AI services

## 📋 Step-by-Step Setup

### 1. Install Modal CLI

```bash
pip install modal
modal token new
```

### 2. Get API Keys

You'll need API keys from these services:

- **Deepgram**: [Get API Key](https://console.deepgram.com/)
- **Groq**: [Get API Key](https://console.groq.com/)
- **ElevenLabs**: [Get API Key](https://elevenlabs.io/)

### 3. Set Up Secrets

Run the deployment script to create secrets:

```bash
./deploy.sh setup
```

This will prompt you for each API key and create the necessary secrets in Modal.

### 4. Deploy the Backend

```bash
./deploy.sh deploy
```

The deployment will output a WebSocket URL like:
`wss://your-username--voice-ai-backend-run-app.modal.run`

### 5. Test the Deployment

```bash
./deploy.sh test
```

Or test manually with the WebSocket URL:

```bash
python test_websocket.py wss://your-username--voice-ai-backend-run-app.modal.run
```

## 🔧 Manual Setup (Alternative)

If you prefer to set up secrets manually:

```bash
# Create secrets individually
modal secret create deepgram-secret DEEPGRAM_API_KEY="your_key"
modal secret create groq-secret GROQ_API_KEY="your_key"
modal secret create elevenlabs-secret ELEVENLABS_API_KEY="your_key"

# Deploy
modal deploy main.py
```

## 📊 Monitoring

- **View logs**: `./deploy.sh logs`
- **List secrets**: `./deploy.sh secrets`
- **Health check**: Visit `https://your-app.modal.run/health`

## 🔗 Next Steps

Once your backend is deployed:

1. Copy the WebSocket URL from the deployment output
2. Update your frontend's environment variables
3. Test the full voice agent system

## 🐛 Troubleshooting

### Common Issues

1. **"Missing API configuration"**
   - Ensure all secrets are created in Modal
   - Check that API keys are valid

2. **"WebSocket connection failed"**
   - Verify the WebSocket URL is correct
   - Check that the app is deployed and running

3. **"Health check failed"**
   - The app might still be starting up
   - Check Modal logs for errors

### Getting Help

- Check the logs: `./deploy.sh logs`
- Review the main README.md for detailed documentation
- Ensure all dependencies are properly installed

## 🎯 What's Next?

Your backend is now ready to handle real-time voice conversations! The next step is to:

1. **Build the Frontend**: Create the React/TypeScript frontend
2. **Connect the Pieces**: Link frontend to backend
3. **Test the System**: Have your first voice conversation

---

**Need help?** Check the main README.md for comprehensive documentation. 