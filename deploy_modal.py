#!/usr/bin/env python3
"""
Modal Deployment Script for Voice Agent with Cloud Storage
Deploys the voice agent backend with Modal cloud storage integration
"""

import modal
import os
from pathlib import Path

# Define the container image with necessary dependencies
image = modal.Image.debian_slim().pip_install([
    "fastapi",
    "websockets",
    "deepgram-sdk",
    "groq",
    "elevenlabs",
    "python-dotenv",
    "uvicorn",
    "pydantic",
    "numpy",      # For audio processing
    "modal"       # Ensure Modal is available
])

# Define the Modal application
app = modal.App("voice-agent-cloud-storage")

# Mount the current directory to include all Python files
app = app.mount("/app", modal.Mount.from_local_dir(".", remote_path="/app"))

# Cloud Storage Resources
metrics_volume = modal.Volume.from_name("voice-agent-metrics", create_if_missing=True)
conversation_store = modal.Dict.from_name("voice-conversations", create_if_missing=True)
voice_queue = modal.Queue.from_name("voice-processing", create_if_missing=True)
session_store = modal.Dict.from_name("voice-sessions", create_if_missing=True)

@app.function(
    image=image,
    volumes={"/metrics": metrics_volume},
    secrets=[
        modal.Secret.from_name("voice-agent-secrets")  # Create this in Modal dashboard
    ],
    timeout=3600,  # 1 hour timeout
    memory=2048,   # 2GB RAM
    cpu=2.0        # 2 CPU cores
)
@modal.asgi_app()
def voice_agent_app():
    """Deploy the voice agent as a Modal ASGI app"""
    
    # Import the FastAPI app from main.py
    from main import fastapi_app
    
    # Add CORS middleware for frontend access
    from fastapi.middleware.cors import CORSMiddleware
    
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure this properly for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return fastapi_app

@app.function(
    image=image,
    volumes={"/metrics": metrics_volume},
    timeout=300,  # 5 minutes
    memory=1024,  # 1GB RAM
)
def test_cloud_storage():
    """Test cloud storage functionality"""
    import json
    import time
    from datetime import datetime
    
    # Import the Modal storage functions
    from modal_storage import (
        store_session, store_conversation, queue_voice_processing,
        store_session_metrics, session_store, conversation_store, voice_queue
    )
    
    # Test session storage
    test_session = {
        "session_id": f"test_session_{int(time.time())}",
        "test_data": "This is a test session",
        "timestamp": datetime.now().isoformat()
    }
    
    # Test metrics storage
    test_metrics = {
        "session_id": test_session["session_id"],
        "metrics_data": {
            "processing_time": 1.5,
            "response_length": 100,
            "word_count": 20
        },
        "timestamp": datetime.now().isoformat()
    }
    
    # Test conversation storage
    test_conversation = {
        "user_input": "Hello, this is a test",
        "ai_response": "Hi! This is a test response.",
        "processing_time": 1.2,
        "timestamp": datetime.now().isoformat()
    }
    
    results = {
        "session_stored": False,
        "metrics_stored": False,
        "conversation_stored": False,
        "queue_tested": False
    }
    
    try:
        # Test session storage
        session_store[test_session["session_id"]] = test_session
        results["session_stored"] = True
        print(f"✅ Session stored: {test_session['session_id']}")
        
        # Test metrics storage
        metrics_file = f"/metrics/test_{test_session['session_id']}.json"
        with open(metrics_file, "w") as f:
            json.dump(test_metrics, f, indent=2)
        metrics_volume.commit()
        results["metrics_stored"] = True
        print(f"✅ Metrics stored: {metrics_file}")
        
        # Test conversation storage
        if test_session["session_id"] not in conversation_store:
            conversation_store[test_session["session_id"]] = []
        conversation_store[test_session["session_id"]].append(test_conversation)
        results["conversation_stored"] = True
        print(f"✅ Conversation stored for session: {test_session['session_id']}")
        
        # Test queue
        test_task = {
            "task_id": f"test_task_{int(time.time())}",
            "data": {"test": "queue functionality"},
            "timestamp": datetime.now().isoformat()
        }
        voice_queue.put(test_task)
        results["queue_tested"] = True
        print(f"✅ Task queued: {test_task['task_id']}")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
    
    return results

@app.function(
    image=image,
    volumes={"/metrics": metrics_volume},
    timeout=300,
    memory=1024
)
def get_storage_stats():
    """Get comprehensive storage statistics"""
    import os
    import glob
    
    # Import the Modal storage functions
    from modal_storage import session_store, conversation_store
    
    stats = {
        "sessions": len(session_store),
        "conversations": sum(len(conv_list) for conv_list in conversation_store.values()),
        "metrics_files": 0,
        "queue_items": 0
    }
    
    try:
        # Count metrics files
        pattern = "/metrics/*.json"
        metrics_files = glob.glob(pattern)
        stats["metrics_files"] = len(metrics_files)
        
        # Estimate queue size (Modal doesn't expose this directly)
        stats["queue_items"] = "dynamic"
        
    except Exception as e:
        print(f"Error getting stats: {e}")
    
    return stats

@app.function(
    image=image,
    volumes={"/metrics": metrics_volume},
    timeout=600,
    memory=2048
)
def cleanup_test_data():
    """Clean up test data from storage"""
    import glob
    import os
    
    cleaned = {
        "sessions_cleaned": 0,
        "conversations_cleaned": 0,
        "metrics_files_cleaned": 0
    }
    
    try:
        # Clean test sessions
        test_sessions = [k for k in session_store.keys() if k.startswith("test_session_")]
        for session_id in test_sessions:
            del session_store[session_id]
            cleaned["sessions_cleaned"] += 1
        
        # Clean test conversations
        test_conversations = [k for k in conversation_store.keys() if k.startswith("test_session_")]
        for session_id in test_conversations:
            del conversation_store[session_id]
            cleaned["conversations_cleaned"] += 1
        
        # Clean test metrics files
        pattern = "/metrics/test_*.json"
        test_files = glob.glob(pattern)
        for file_path in test_files:
            os.remove(file_path)
            cleaned["metrics_files_cleaned"] += 1
        
        # Commit volume changes
        metrics_volume.commit()
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
    
    return cleaned

# CLI commands
@app.local_entrypoint()
def main(command: str = "deploy"):
    """Main entry point for deployment commands"""
    
    if command == "deploy":
        print("🚀 Deploying Voice Agent with Cloud Storage...")
        print("📊 Cloud Storage Resources:")
        print(f"   - Metrics Volume: voice-agent-metrics")
        print(f"   - Conversation Store: voice-conversations")
        print(f"   - Voice Queue: voice-processing")
        print(f"   - Session Store: voice-sessions")
        print("\n🌐 App will be available at the Modal URL")
        
    elif command == "test":
        print("🧪 Testing Cloud Storage...")
        results = test_cloud_storage.remote()
        print(f"Test Results: {results}")
        
    elif command == "stats":
        print("📊 Getting Storage Statistics...")
        stats = get_storage_stats.remote()
        print(f"Storage Stats: {stats}")
        
    elif command == "cleanup":
        print("🧹 Cleaning up test data...")
        cleaned = cleanup_test_data.remote()
        print(f"Cleanup Results: {cleaned}")
        
    elif command == "serve":
        print("🌐 Starting Voice Agent Server...")
        voice_agent_app.serve()
        
    else:
        print("Available commands:")
        print("  deploy   - Deploy the voice agent")
        print("  test     - Test cloud storage functionality")
        print("  stats    - Get storage statistics")
        print("  cleanup  - Clean up test data")
        print("  serve    - Start the server")

if __name__ == "__main__":
    main() 