# deploy_with_storage.py
# Deployment script for voice agent with full storage functionality

import modal
import os

# Create the Modal app
app = modal.App("voice-agent-app-with-storage")

# Create image with dependencies and local files
image = (
    modal.Image.debian_slim()
    .pip_install([
        "fastapi", "uvicorn", "websockets", "deepgram-sdk", "groq", "elevenlabs"
    ])
    .copy_local_dir(".", "/app")
)

@app.function(
    secrets=[modal.Secret.from_name("voice-agent-secrets")],
    image=image
)
def get_secrets():
    """Get API secrets from Modal"""
    return {
        "deepgram_api_key": os.environ.get("DEEPGRAM_API_KEY"),
        "groq_api_key": os.environ.get("GROQ_API_KEY"),
        "elevenlabs_api_key": os.environ.get("ELEVENLABS_API_KEY"),
        "azure_speech_key": os.environ.get("AZURE_SPEECH_KEY"),
    }

@app.function(
    secrets=[modal.Secret.from_name("voice-agent-secrets")],
    image=image
)
@modal.asgi_app()
def run_app():
    """Run the FastAPI app with full storage functionality"""
    import sys
    sys.path.append("/app")
    
    # Import the main application
    from main_with_storage import fastapi_app
    return fastapi_app

if __name__ == "__main__":
    print("Deploying voice agent with storage...")
    print("This will include modal_storage.py and all storage functions.") 