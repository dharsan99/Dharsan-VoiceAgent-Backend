#!/usr/bin/env python3
"""
Mock LLM Service for Testing
Responds quickly with realistic responses to test the complete AI pipeline
"""

import json
import time
import random
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Mock LLM Service", version="1.0.0")

# Mock responses for different types of inputs
MOCK_RESPONSES = {
    "greeting": [
        "Hello! How can I help you today?",
        "Hi there! I'm here to assist you.",
        "Greetings! What would you like to know?",
        "Hello! I'm ready to help with any questions you have."
    ],
    "question": [
        "That's an interesting question. Let me think about that for you.",
        "I'd be happy to help you with that.",
        "That's a great question. Here's what I can tell you about that.",
        "I understand what you're asking. Let me provide some information."
    ],
    "general": [
        "I understand what you're saying. Is there anything specific you'd like to know?",
        "That's interesting! Tell me more about what you're looking for.",
        "I'm here to help. What would you like to explore?",
        "Thanks for sharing that with me. How can I assist you further?"
    ]
}

class MockLLMRequest(BaseModel):
    model: str
    prompt: str
    stream: bool = False
    options: Dict[str, Any] = {}
    system: str = None

class MockLLMResponse(BaseModel):
    model: str
    created_at: str
    response: str
    done: bool
    context: list
    total_duration: int
    load_duration: int
    prompt_eval_count: int
    prompt_eval_duration: int
    eval_count: int
    eval_duration: int

def get_mock_response(prompt: str) -> str:
    """Generate a realistic mock response based on the input prompt"""
    prompt_lower = prompt.lower()
    
    # Simple keyword matching for response selection
    if any(word in prompt_lower for word in ["hello", "hi", "hey", "greetings"]):
        category = "greeting"
    elif any(word in prompt_lower for word in ["what", "how", "why", "when", "where", "?"]):
        category = "question"
    else:
        category = "general"
    
    # Add some randomness and personalization
    base_response = random.choice(MOCK_RESPONSES[category])
    
    # Add context-aware elements
    if "test" in prompt_lower:
        base_response = "I can see this is a test. The voice agent system is working well! " + base_response
    
    return base_response

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "mock-llm"}

@app.get("/api/tags")
async def get_models():
    """Get available models (mock)"""
    return {
        "models": [
            {
                "name": "mock-llm:latest",
                "modified_at": "2025-07-26T08:00:00Z",
                "size": 1024
            }
        ]
    }

@app.post("/api/generate")
async def generate_response(request: MockLLMRequest):
    """Generate a mock LLM response"""
    try:
        # Simulate a small processing delay (50-200ms)
        processing_delay = random.uniform(0.05, 0.2)
        time.sleep(processing_delay)
        
        # Generate mock response
        response_text = get_mock_response(request.prompt)
        
        # Calculate mock metrics
        eval_count = len(response_text.split()) + random.randint(5, 15)
        total_duration = int(processing_delay * 1000000)  # Convert to nanoseconds
        
        response = MockLLMResponse(
            model=request.model,
            created_at="2025-07-26T08:00:00Z",
            response=response_text,
            done=True,
            context=[],
            total_duration=total_duration,
            load_duration=0,
            prompt_eval_count=len(request.prompt.split()),
            prompt_eval_duration=total_duration // 3,
            eval_count=eval_count,
            eval_duration=total_duration // 2
        )
        
        return response.dict()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mock LLM error: {str(e)}")

if __name__ == "__main__":
    print("🚀 Starting Mock LLM Service...")
    print("📍 Service will respond quickly with realistic responses")
    print("🔗 Health check: http://localhost:11434/health")
    print("🤖 Generate endpoint: http://localhost:11434/api/generate")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=11434,
        log_level="info"
    ) 