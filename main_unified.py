"""
Unified Voice Agent Backend
Main entry point that can run V1, V2, and V3 voice agent implementations.
"""

import os
import sys
import logging
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import modal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_unified_app() -> FastAPI:
    """Create the unified FastAPI app with all versions"""
    app = FastAPI(
        title="Dharsan Voice Agent Backend",
        version="3.0.0",
        description="Unified backend for voice agent versions v1, v2, and v3"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Import version-specific modules
    try:
        from versions.v1.main import fastapi_app as v1_app
        from versions.v2.main import fastapi_app as v2_app
        from versions.v3.main import fastapi_app as v3_app
        
        # Mount V1 routes
        app.mount("/v1", v1_app)
        logger.info("V1 routes mounted at /v1")
        
        # Mount V2 routes
        app.mount("/v2", v2_app)
        logger.info("V2 routes mounted at /v2")
        
        # Mount V3 routes
        app.mount("/v3", v3_app)
        logger.info("V3 routes mounted at /v3")
        
    except ImportError as e:
        logger.error(f"Failed to import version modules: {e}")
        logger.warning("Version modules not available - providing fallback endpoints")
        
        # Add fallback endpoints for each version
        @app.get("/v1/health")
        async def v1_health_fallback():
            return {"status": "unavailable", "version": "v1", "reason": "module not found"}
        
        @app.get("/v2/health")
        async def v2_health_fallback():
            return {"status": "unavailable", "version": "v2", "reason": "module not found"}
        
        @app.get("/v3/health")
        async def v3_health_fallback():
            return {"status": "unavailable", "version": "v3", "reason": "module not found"}
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "message": "Dharsan Voice Agent Backend",
            "version": "3.0.0",
            "status": "running",
            "available_versions": {
                "v1": {
                    "description": "Basic voice agent with metrics",
                    "websocket": "/v1/ws",
                    "health": "/v1/health",
                    "metrics": "/v1/metrics/sessions"
                },
                "v2": {
                    "description": "Modular voice agent with session management",
                    "websocket": "/v2/ws/v2",
                    "health": "/v2/v2/health",
                    "sessions": "/v2/v2/sessions"
                },
                "v3": {
                    "description": "WebRTC-based voice agent",
                    "websocket": "/v3/ws/v3",
                    "health": "/v3/v3/health",
                    "webrtc_stats": "/v3/v3/webrtc/stats"
                }
            },
            "documentation": {
                "api_docs": "/docs",
                "redoc": "/redoc"
            }
        }
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "version": "3.0.0",
            "available_versions": ["v1", "v2", "v3"]
        }
    
    return app

# Create the unified app
fastapi_app = create_unified_app()

# Modal setup
app_image = modal.Image.debian_slim().pip_install([
    "fastapi",
    "websockets",
    "deepgram-sdk",
    "groq",
    "elevenlabs",
    "python-dotenv",
    "uvicorn",
    "pydantic",
    "numpy",
    "aiortc",
    "aiohttp",
    "azure-cognitiveservices-speech"
])

app = modal.App(
    "voice-ai-backend-unified",
    image=app_image,
    secrets=[
        modal.Secret.from_name("deepgram-secret"),
        modal.Secret.from_name("groq-secret"),
        modal.Secret.from_name("elevenlabs-secret"),
        modal.Secret.from_name("azure-speech-secret")
    ]
)

@app.function()
@modal.asgi_app()
def run_app():
    """Run the unified FastAPI app with Modal"""
    return fastapi_app

if __name__ == "__main__":
    import uvicorn
    
    # Check if specific version is requested
    version = os.environ.get("VOICE_AGENT_VERSION", "unified")
    
    if version == "v1":
        from versions.v1.main import fastapi_app
        logger.info("Starting V1 voice agent...")
        uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)
    elif version == "v2":
        from versions.v2.main import fastapi_app
        logger.info("Starting V2 voice agent...")
        uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)
    elif version == "v3":
        from versions.v3.main import fastapi_app
        logger.info("Starting V3 voice agent...")
        uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)
    else:
        logger.info("Starting unified voice agent backend...")
        uvicorn.run(fastapi_app, host="0.0.0.0", port=8000) 