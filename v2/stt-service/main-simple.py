import os
import time
import tempfile
import logging
from typing import Optional
from pathlib import Path

import whisper
import soundfile as sf
import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

app = FastAPI(title="STT Service", version="1.0.0")

# Global variables
start_time = time.time()
whisper_model = None
model_loaded = False

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_size: str
    uptime: float

class STTRequest(BaseModel):
    audio_data: bytes

class STTResponse(BaseModel):
    transcript: str
    confidence: float
    language: str
    processing_time: float

def load_whisper_model():
    """Load the Whisper model"""
    global whisper_model, model_loaded
    try:
        logger.info("Loading Whisper model...")
        # Use the smallest model for faster loading
        whisper_model = whisper.load_model("tiny")
        model_loaded = True
        logger.info("Whisper model loaded successfully")
    except Exception as e:
        logger.error("Failed to load Whisper model", error=str(e))
        model_loaded = False
        raise

def check_model_exists() -> bool:
    """Check if the model is loaded"""
    return model_loaded and whisper_model is not None

def get_model_size() -> str:
    """Get model size information"""
    if not check_model_exists():
        return "Not loaded"
    return "tiny"  # We're using the tiny model

@app.on_event("startup")
async def startup_event():
    """Load the model on startup"""
    try:
        load_whisper_model()
    except Exception as e:
        logger.error("Failed to load model on startup", error=str(e))
        # Don't fail startup, allow health checks to work

@app.get("/health")
async def health_check() -> HealthResponse:
    """Health check endpoint"""
    model_loaded_status = check_model_exists()
    model_size = get_model_size()
    
    return HealthResponse(
        status="healthy" if model_loaded_status else "loading",
        model_loaded=model_loaded_status,
        model_size=model_size,
        uptime=time.time() - start_time
    )

@app.post("/transcribe", response_model=STTResponse)
async def transcribe_audio(audio_file: UploadFile = File(...)):
    """Transcribe audio file"""
    start_time_transcribe = time.time()
    
    try:
        # Check if model is loaded
        if not check_model_exists():
            logger.error("Whisper model not loaded")
            raise HTTPException(status_code=503, detail="STT model not loaded")
        
        # Validate file type
        if not audio_file.content_type or not audio_file.content_type.startswith('audio/'):
            raise HTTPException(status_code=400, detail="Invalid file type. Expected audio file.")
        
        logger.info("Starting transcription", filename=audio_file.filename, content_type=audio_file.content_type)
        
        # Read audio data
        audio_data = await audio_file.read()
        if not audio_data:
            raise HTTPException(status_code=400, detail="Empty audio file")
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_file_path = temp_file.name
        
        try:
            # Load audio with soundfile
            audio_array, sample_rate = sf.read(temp_file_path)
            
            # Convert to mono if stereo
            if len(audio_array.shape) > 1:
                audio_array = np.mean(audio_array, axis=1)
            
            # Normalize audio
            audio_array = audio_array / np.max(np.abs(audio_array))
            
            logger.info("Audio loaded", sample_rate=sample_rate, duration=len(audio_array)/sample_rate)
            
            # Transcribe with Whisper
            result = whisper_model.transcribe(audio_array)
            
            transcript = result["text"].strip()
            language = result.get("language", "unknown")
            
            # Calculate confidence (Whisper doesn't provide confidence scores, so we estimate)
            confidence = 0.85  # Placeholder confidence
            
            processing_time = time.time() - start_time_transcribe
            
            logger.info("Transcription completed", 
                       transcript=transcript, 
                       language=language, 
                       processing_time=processing_time)
            
            return STTResponse(
                transcript=transcript,
                confidence=confidence,
                language=language,
                processing_time=processing_time
            )
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error("Transcription failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "STT Service is running", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 