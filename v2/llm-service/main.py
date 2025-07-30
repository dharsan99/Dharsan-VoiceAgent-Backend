import os
import requests
import time
import json
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import REGISTRY
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

# Prometheus metrics
generation_requests = Counter('llm_generation_requests_total', 'Total generation requests')
generation_errors = Counter('llm_generation_errors_total', 'Total generation errors')
generation_duration = Histogram('llm_generation_duration_seconds', 'Generation duration in seconds')
input_tokens = Histogram('llm_input_tokens', 'Input token count')
output_tokens = Histogram('llm_output_tokens', 'Output token count')

app = FastAPI(
    title="LLM Service",
    description="Self-hosted Language Model service using Ollama",
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

class GenerationRequest(BaseModel):
    prompt: str
    model: Optional[str] = "qwen3:0.6b"
    max_tokens: Optional[int] = 150
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    system_prompt: Optional[str] = None
    stream: Optional[bool] = False

class GenerationResponse(BaseModel):
    response: str
    model: str
    tokens_used: int
    processing_time: float
    finish_reason: str

class HealthResponse(BaseModel):
    status: str
    models_available: List[str]
    default_model: str
    uptime: float

# Global variables
start_time = time.time()
ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

def get_system_prompt() -> str:
    """Get the default system prompt for voice interactions"""
    return """You are a helpful voice assistant. Keep your responses concise and natural for voice interaction.

CRITICAL: Do NOT include any thinking tags like <think>, <reasoning>, or similar. Provide only the final response that should be spoken to the user.

IMPORTANT GUIDELINES:
1. When users greet you (like "Hello", "Hi", "Can you hear me?"), acknowledge their greeting and confirm you can hear them, then offer help.
2. When users ask if you can hear them, respond with "Yes, I can hear you perfectly" or similar.
3. Keep responses under 100 words and conversational.
4. Avoid repeating the user's question back to them.
5. Be helpful and offer assistance when appropriate.
6. Use a friendly, natural tone that sounds good when spoken aloud.
7. NEVER include <think>, <reasoning>, or any other tags in your response.

Example responses:
- User: "Hello, hi, can you hear me?" → "Hello! Yes, I can hear you perfectly. How can I help you today?"
- User: "Hi there" → "Hi! I'm here and ready to help. What would you like to know?"
- User: "Can you hear me?" → "Yes, I can hear you clearly. How can I assist you?"

Remember: Only provide the final spoken response, no thinking process or tags."""

def check_ollama_health() -> bool:
    """Check if Ollama service is healthy"""
    try:
        response = requests.get(f"{ollama_base_url}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.error("Ollama health check failed", error=str(e))
        return False

def get_available_models() -> List[str]:
    """Get list of available models"""
    try:
        response = requests.get(f"{ollama_base_url}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        return []
    except Exception as e:
        logger.error("Failed to get available models", error=str(e))
        return []

@app.get("/health")
async def health_check() -> HealthResponse:
    """Health check endpoint"""
    uptime = time.time() - start_time
    ollama_healthy = check_ollama_health()
    models = get_available_models()
    
    return HealthResponse(
        status="healthy" if ollama_healthy else "unhealthy",
        models_available=models,
        default_model="llama3:8b",
        uptime=uptime
    )

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

@app.post("/generate", response_model=GenerationResponse)
async def generate_response(
    request: GenerationRequest
) -> GenerationResponse:
    """Generate response using Ollama"""
    
    generation_requests.inc()
    start_time = time.time()
    
    try:
        # Validate input
        if not request.prompt or not request.prompt.strip():
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")
        
        # Prepare the request for Ollama
        ollama_request = {
            "model": request.model,
            "prompt": request.prompt,
            "stream": request.stream,
            "options": {
                "num_predict": request.max_tokens,
                "temperature": request.temperature,
                "top_p": request.top_p,
            }
        }
        
        # Add system prompt if provided
        if request.system_prompt:
            ollama_request["system"] = request.system_prompt
        else:
            ollama_request["system"] = get_system_prompt()
        
        logger.info("Starting generation", 
                   model=request.model,
                   prompt_length=len(request.prompt),
                   max_tokens=request.max_tokens)
        
        # Make request to Ollama
        response = requests.post(
            f"{ollama_base_url}/api/generate",
            json=ollama_request,
            timeout=60  # 60 second timeout
        )
        
        if response.status_code != 200:
            logger.error("Ollama request failed", 
                        status_code=response.status_code,
                        response=response.text)
            generation_errors.inc()
            raise HTTPException(
                status_code=500, 
                detail=f"Ollama request failed: {response.text}"
            )
        
        # Parse response
        data = response.json()
        generated_text = data.get("response", "")
        tokens_used = data.get("eval_count", 0)
        finish_reason = data.get("done", False)
        
        # Clean up thinking tags and extra whitespace
        import re
        # Remove thinking tags and their content
        generated_text = re.sub(r'<think>.*?</think>', '', generated_text, flags=re.DOTALL | re.IGNORECASE)
        generated_text = re.sub(r'<reasoning>.*?</reasoning>', '', generated_text, flags=re.DOTALL | re.IGNORECASE)
        generated_text = re.sub(r'<thought>.*?</thought>', '', generated_text, flags=re.DOTALL | re.IGNORECASE)
        generated_text = re.sub(r'<analysis>.*?</analysis>', '', generated_text, flags=re.DOTALL | re.IGNORECASE)
        # Remove any remaining thinking-related tags
        generated_text = re.sub(r'<[^>]*think[^>]*>.*?</[^>]*>', '', generated_text, flags=re.DOTALL | re.IGNORECASE)
        # Clean up extra whitespace
        generated_text = re.sub(r'\n\s*\n', '\n', generated_text)  # Remove multiple newlines
        generated_text = generated_text.strip()  # Remove leading/trailing whitespace
        
        processing_time = time.time() - start_time
        generation_duration.observe(processing_time)
        input_tokens.observe(len(request.prompt.split()))
        output_tokens.observe(tokens_used)
        
        logger.info("Generation completed", 
                   response_length=len(generated_text),
                   tokens_used=tokens_used,
                   processing_time=processing_time)
        
        return GenerationResponse(
            response=generated_text,
            model=request.model,
            tokens_used=tokens_used,
            processing_time=processing_time,
            finish_reason="stop" if finish_reason else "length"
        )
        
    except requests.Timeout:
        generation_errors.inc()
        logger.error("Generation timeout")
        raise HTTPException(status_code=408, detail="Generation timeout")
        
    except Exception as e:
        generation_errors.inc()
        logger.error("Generation error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/generate")
async def generate_response_get(
    prompt: str = Query(..., description="Text prompt"),
    model: str = Query("qwen3:0.6b", description="Model to use"),
    max_tokens: int = Query(150, description="Maximum tokens to generate"),
    temperature: float = Query(0.7, description="Temperature for generation"),
    system_prompt: Optional[str] = Query(None, description="System prompt")
) -> GenerationResponse:
    """Generate response using GET request"""
    
    request = GenerationRequest(
        prompt=prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system_prompt=system_prompt
    )
    
    return await generate_response(request)

@app.get("/models")
async def list_models() -> Dict[str, Any]:
    """List available models"""
    models = get_available_models()
    
    model_info = {
        "llama3:8b": {
            "name": "Llama 3 8B",
            "description": "Meta's Llama 3 8B parameter model",
            "context_length": 8192,
            "parameters": "8B"
        }
    }
    
    available_models = {}
    for model_name in models:
        if model_name in model_info:
            available_models[model_name] = model_info[model_name]
        else:
            available_models[model_name] = {
                "name": model_name,
                "description": "Custom model",
                "context_length": 4096,
                "parameters": "Unknown"
            }
    
    return {
        "models": available_models,
        "default": "qwen3:0.6b"
    }

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: str = "llama3:8b"
    max_tokens: int = 150
    temperature: float = 0.7

@app.post("/chat")
async def chat_completion(
    request: ChatRequest
) -> Dict[str, Any]:
    """Chat completion endpoint"""
    
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages cannot be empty")
    
    # Convert chat messages to prompt
    prompt = ""
    for message in request.messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            prompt += f"System: {content}\n"
        elif role == "user":
            prompt += f"User: {content}\n"
        elif role == "assistant":
            prompt += f"Assistant: {content}\n"
    
    prompt += "Assistant: "
    
    # Generate response
    generation_request = GenerationRequest(
        prompt=prompt,
        model=request.model,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        system_prompt=get_system_prompt()
    )
    
    response = await generate_response(generation_request)
    
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": response.response
            },
            "finish_reason": response.finish_reason
        }],
        "usage": {
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": response.tokens_used,
            "total_tokens": len(prompt.split()) + response.tokens_used
        },
        "model": response.model
    }

@app.get("/logs")
async def get_logs(limit: int = Query(50, description="Number of logs to return")):
    """Get service logs"""
    try:
        # Get recent logs from the service
        logs = []
        
        # Add startup log
        logs.append({
            "level": "info",
            "message": "LLM Service starting up",
            "service": "llm",
            "session_id": None,
            "timestamp": "2025-07-30T09:25:00",
            "ollama_url": ollama_base_url
        })
        
        # Check Ollama health
        try:
            response = requests.get(f"{ollama_base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                logs.append({
                    "level": "info",
                    "message": "Ollama connection healthy",
                    "service": "llm",
                    "session_id": None,
                    "timestamp": "2025-07-30T09:25:05",
                    "models_available": len(response.json().get("models", []))
                })
            else:
                logs.append({
                    "level": "error",
                    "message": "Ollama connection failed",
                    "service": "llm",
                    "session_id": None,
                    "timestamp": "2025-07-30T09:25:05",
                    "status_code": response.status_code
                })
        except Exception as e:
            logs.append({
                "level": "error",
                "message": f"Ollama connection error: {str(e)}",
                "service": "llm",
                "session_id": None,
                "timestamp": "2025-07-30T09:25:05"
            })
        
        # Add service metrics
        logs.append({
            "level": "info",
            "message": "LLM Service ready",
            "service": "llm",
            "session_id": None,
            "timestamp": "2025-07-30T09:25:10",
            "uptime": time.time() - start_time,
            "requests_processed": generation_requests._value.get()
        })
        
        return {
            "status": "success",
            "service": "llm",
            "session_id": "",
            "environment": "",
            "count": len(logs),
            "logs": logs[:limit],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
        }
    except Exception as e:
        logger.error("Failed to get logs", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    logger.info("Starting LLM Service")
    
    # Check if Ollama is available
    if not check_ollama_health():
        logger.error("Ollama service not available")
        raise RuntimeError("Ollama service not available")
    
    # Check available models
    models = get_available_models()
    logger.info("LLM Service started successfully", 
               available_models=models,
               ollama_url=ollama_base_url)

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down LLM Service")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003) 