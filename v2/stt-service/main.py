import tempfile
import os
import time
import json
import logging
import io
from typing import Optional, Dict, Any
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
import soundfile as sf
import numpy as np
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import REGISTRY
import structlog
from transformers import WhisperProcessor, WhisperForConditionalGeneration
import torch

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

# Prometheus metrics
transcription_requests = Counter('stt_transcription_requests_total', 'Total transcription requests')
transcription_errors = Counter('stt_transcription_errors_total', 'Total transcription errors')
transcription_duration = Histogram('stt_transcription_duration_seconds', 'Transcription duration in seconds')
audio_duration = Histogram('stt_audio_duration_seconds', 'Audio duration in seconds')

app = FastAPI(
    title="STT Service",
    description="Self-hosted Speech-to-Text service using Whisper",
    version="1.0.0"
)

# Add CORS middleware
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TranscriptionRequest(BaseModel):
    language: Optional[str] = "en"
    model: Optional[str] = "base"
    threads: Optional[int] = 4
    temperature: Optional[float] = 0.0

class TranscriptionResponse(BaseModel):
    transcription: str
    language: str
    duration: float
    confidence: Optional[float] = None
    model: str
    processing_time: float

class HealthResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    status: str
    model_loaded: bool
    model_size: str
    uptime: float

# Global variables
start_time = time.time()
model_name = os.getenv("STT_MODEL", "base")  # Read from environment variable
processor = None
model = None
model_loading = False

# In-memory log storage for development
service_logs = []
MAX_LOGS = 1000

def add_service_log(level: str, message: str, session_id: str = None, **kwargs):
    """Add a log entry to the service logs"""
    global service_logs
    log_entry = {
        "timestamp": time.time(),
        "level": level,
        "message": message,
        "service": "stt-service",
        "session_id": session_id,
        **kwargs
    }
    service_logs.append(log_entry)
    
    # Keep only the last MAX_LOGS entries
    if len(service_logs) > MAX_LOGS:
        service_logs = service_logs[-MAX_LOGS:]
    
    # Also log to structlog
    if session_id:
        bound_logger = logger.bind(session_id=session_id)
    else:
        bound_logger = logger
    
    # Use appropriate log level method
    if level.lower() == "info":
        bound_logger.info(message, **kwargs)
    elif level.lower() == "error":
        bound_logger.error(message, **kwargs)
    elif level.lower() == "warning":
        bound_logger.warning(message, **kwargs)
    elif level.lower() == "debug":
        bound_logger.debug(message, **kwargs)
    else:
        bound_logger.info(message, **kwargs)

def load_whisper_model():
    """Load Whisper model and processor"""
    global processor, model, model_loading
    if model_loading:
        return False
    if processor is not None and model is not None:
        return True
    
    try:
        model_loading = True
        logger.info("Loading Whisper model", model_name=model_name)
        
        # Choose model based on environment variable
        if model_name == "ultra-minimal":
            model_id = "openai/whisper-tiny"
        elif model_name == "tiny":
            model_id = "openai/whisper-tiny"
        elif model_name == "base":
            model_id = "openai/whisper-base"
        elif model_name == "small":
            model_id = "openai/whisper-small"
        elif model_name == "medium":
            model_id = "openai/whisper-medium"
        elif model_name == "large":
            model_id = "openai/whisper-large"
        else:
            # Default to ultra-minimal for unknown models
            model_id = "openai/whisper-tiny"
            logger.warning("Unknown model name, using ultra-minimal", model_name=model_name)
        
        logger.info("Loading model from HuggingFace", model_id=model_id)
        processor = WhisperProcessor.from_pretrained(model_id)
        model = WhisperForConditionalGeneration.from_pretrained(model_id)
        logger.info("Whisper model loaded successfully", model_name=model_name, model_id=model_id)
        return True
    except Exception as e:
        logger.error("Failed to load Whisper model", error=str(e), model_name=model_name)
        return False
    finally:
        model_loading = False

def check_model_exists() -> bool:
    """Check if the STT model is available"""
    return model is not None and processor is not None

def get_model_size() -> str:
    """Get the size of the loaded model"""
    if model is not None:
        # Calculate approximate model size
        param_size = sum(p.numel() * p.element_size() for p in model.parameters())
        size_mb = param_size / (1024 * 1024)
        return f"{size_mb:.1f} MB"
    return "Not loaded"

def convert_audio_to_wav(audio_data: bytes, sample_rate: int = 16000) -> bytes:
    """Convert audio data to 16kHz mono WAV format"""
    try:
        # Load audio data
        audio, sr = sf.read(io.BytesIO(audio_data))
        
        # Convert to mono if stereo
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)
        
        # Resample if needed
        if sr != sample_rate:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=sample_rate)
        
        # Convert to 16-bit PCM
        audio = (audio * 32767).astype(np.int16)
        
        # Write to WAV format
        output = io.BytesIO()
        sf.write(output, audio, sample_rate, format='WAV', subtype='PCM_16')
        return output.getvalue()
        
    except Exception as e:
        logger.error("Audio conversion failed", error=str(e))
        raise HTTPException(status_code=400, detail=f"Audio conversion failed: {str(e)}")

@app.get("/health")
async def health_check() -> HealthResponse:
    """Health check endpoint"""
    # Extract session_id from headers if available
    session_id = None
    # Note: FastAPI doesn't provide headers in GET requests by default
    # This is just for demonstration - in real usage, session_id would come from request context
    
    add_service_log("info", "Health check requested", session_id)
    
    model_loaded = check_model_exists()
    model_size = get_model_size() if model_loaded else "Not loaded"
    status = "healthy" if model_loaded else "loading"
    
    add_service_log("info", f"Health check completed - Status: {status}", session_id, 
                   model_loaded=model_loaded, model_size=model_size)
    
    return HealthResponse(
        status=status,  # Only healthy when model is loaded
        model_loaded=model_loaded,
        model_size=model_size,
        uptime=time.time() - start_time
    )

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

@app.get("/logs")
async def get_logs(session_id: Optional[str] = None, limit: Optional[int] = 100):
    """Get service logs with optional filtering by session_id"""
    global service_logs
    
    # Filter logs by session_id if provided
    filtered_logs = service_logs
    if session_id:
        filtered_logs = [log for log in service_logs if log.get("session_id") == session_id]
    
    # Apply limit
    if limit and limit > 0:
        filtered_logs = filtered_logs[-limit:]
    
    # Convert timestamps to ISO format
    for log in filtered_logs:
        if "timestamp" in log and isinstance(log["timestamp"], (int, float)):
            log["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(log["timestamp"]))
    
    return {
        "status": "success",
        "service": "stt-service",
        "logs": filtered_logs,
        "count": len(filtered_logs),
        "session_id": session_id,
        "limit": limit
    }

@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = "en",
    threads: Optional[int] = 4,
    temperature: Optional[float] = 0.0
) -> TranscriptionResponse:
    """Transcribe audio using OpenAI Whisper"""
    
    transcription_requests.inc()
    start_time = time.time()
    
    # Extract session_id from headers if available
    session_id = None
    if hasattr(file, 'headers') and 'x-session-id' in file.headers:
        session_id = file.headers['x-session-id']
    
    add_service_log("info", "Transcription request received", session_id, 
                   file_size=len(await file.read()) if hasattr(file, 'read') else 0,
                   language=language, model=model_name)
    
    try:
        # Validate file
        if not file.filename:
            add_service_log("error", "No file provided", session_id)
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Load model if not already loaded
        if not check_model_exists():
            add_service_log("info", "Loading Whisper model", session_id, model=model_name)
            if not load_whisper_model():
                add_service_log("error", "STT model failed to load", session_id, model=model_name)
                raise HTTPException(status_code=503, detail="STT model failed to load")
        
        # Read audio data
        audio_data = await file.read()
        if not audio_data:
            add_service_log("error", "Empty audio file", session_id)
            raise HTTPException(status_code=400, detail="Empty audio file")
        
        add_service_log("info", "Audio file read successfully", session_id, 
                       file_size=len(audio_data), filename=file.filename)
        
        # Convert audio to WAV format if needed
        if not file.filename.lower().endswith('.wav'):
            add_service_log("info", "Converting audio to WAV format", session_id, 
                           original_format=file.filename.split('.')[-1])
            audio_data = convert_audio_to_wav(audio_data)
        
        # Create temporary file for processing
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio_file:
            temp_audio_file.write(audio_data)
            temp_audio_file.flush()
            
            # Calculate audio duration
            audio_info = sf.info(temp_audio_file.name)
            duration = audio_info.duration
            audio_duration.observe(duration)
            
            add_service_log("info", "Starting transcription", session_id,
                           file_size=len(audio_data), 
                           duration=duration,
                           language=language,
                           model=model_name)
            
            try:
                # Load and preprocess audio
                audio, sr = sf.read(temp_audio_file.name)
                
                # Convert to mono if stereo
                if len(audio.shape) > 1:
                    audio = np.mean(audio, axis=1)
                    add_service_log("debug", "Converted stereo to mono", session_id)
                
                # Resample to 16kHz if needed
                if sr != 16000:
                    import librosa
                    audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
                    add_service_log("debug", f"Resampled audio from {sr}Hz to 16000Hz", session_id)
                
                # Process audio with Whisper
                inputs = processor(audio, sampling_rate=16000, return_tensors="pt")
                
                # Generate transcription
                with torch.no_grad():
                    predicted_ids = model.generate(
                        inputs.input_features,
                        language=language,
                        task="transcribe",
                        temperature=temperature
                    )
                
                # Decode transcription
                transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
                
                processing_time = time.time() - start_time
                transcription_duration.observe(processing_time)
                
                add_service_log("info", "Transcription completed successfully", session_id,
                               transcription_length=len(transcription),
                               processing_time=processing_time,
                               confidence=0.95)  # Whisper doesn't provide confidence scores
                
                return TranscriptionResponse(
                    transcription=transcription,
                    language=language,
                    duration=duration,
                    confidence=0.95,
                    model=model_name,
                    processing_time=processing_time
                )
                
            except Exception as e:
                processing_time = time.time() - start_time
                add_service_log("error", f"Transcription failed: {str(e)}", session_id,
                               processing_time=processing_time, error=str(e))
                transcription_errors.inc()
                raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_audio_file.name)
                except:
                    pass
                    
    except HTTPException:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        add_service_log("error", f"Unexpected error during transcription: {str(e)}", session_id,
                       processing_time=processing_time, error=str(e))
        transcription_errors.inc()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.post("/transcribe/batch")
async def transcribe_batch(
    files: list[UploadFile] = File(...),
    language: Optional[str] = "en",
    threads: Optional[int] = 4
) -> list[TranscriptionResponse]:
    """Transcribe multiple audio files"""
    
    results = []
    for file in files:
        try:
            result = await transcribe_audio(file, language, threads)
            results.append(result)
        except Exception as e:
            logger.error("Batch transcription failed for file", 
                        filename=file.filename, 
                        error=str(e))
            results.append(TranscriptionResponse(
                transcription=f"[Error: {str(e)}]",
                language=language,
                duration=0.0,
                model=model_name,
                processing_time=0.0
            ))
    
    return results

@app.get("/models")
async def list_models() -> Dict[str, Any]:
    """List available models"""
    return {
        "current_model": model_name,
        "model_loaded": check_model_exists(),
        "model_size": get_model_size(),
        "available_models": ["whisper-base", "whisper-small", "whisper-medium", "whisper-large"]
    }

@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    add_service_log("info", "STT Service starting up")
    logger.info("Starting STT Service")
    
    # Load the Whisper model on startup
    add_service_log("info", "Loading Whisper model on startup", model=model_name)
    logger.info("Loading Whisper model on startup")
    
    if load_whisper_model():
        add_service_log("info", "Whisper model loaded successfully on startup", model=model_name)
        logger.info("Whisper model loaded successfully on startup")
    else:
        add_service_log("error", "Failed to load Whisper model on startup", model=model_name)
        logger.error("Failed to load Whisper model on startup")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down STT Service")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 