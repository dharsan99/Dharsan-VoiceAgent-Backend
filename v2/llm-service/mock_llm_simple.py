#!/usr/bin/env python3
"""
Simple Mock LLM Service for Testing
Minimal dependencies to avoid build issues
"""

import json
import time
import random
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
import threading

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

def get_mock_response(prompt):
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

class MockLLMHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests (health check and model list)"""
        if self.path == "/health":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"status": "healthy", "service": "mock-llm"}
            self.wfile.write(json.dumps(response).encode())
            
        elif self.path == "/api/tags":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "models": [
                    {
                        "name": "mock-llm:latest",
                        "modified_at": "2025-07-26T08:00:00Z",
                        "size": 1024
                    }
                ]
            }
            self.wfile.write(json.dumps(response).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        """Handle POST requests (generate responses)"""
        if self.path == "/api/generate":
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            try:
                request_data = json.loads(body)
                prompt = request_data.get('prompt', '')
                model = request_data.get('model', 'mock-llm:latest')
                
                # Simulate a small processing delay (50-200ms)
                processing_delay = random.uniform(0.05, 0.2)
                time.sleep(processing_delay)
                
                # Generate mock response
                response_text = get_mock_response(prompt)
                
                # Calculate mock metrics
                eval_count = len(response_text.split()) + random.randint(5, 15)
                total_duration = int(processing_delay * 1000000)  # Convert to nanoseconds
                
                response = {
                    "model": model,
                    "created_at": "2025-07-26T08:00:00Z",
                    "response": response_text,
                    "done": True,
                    "context": [],
                    "total_duration": total_duration,
                    "load_duration": 0,
                    "prompt_eval_count": len(prompt.split()),
                    "prompt_eval_duration": total_duration // 3,
                    "eval_count": eval_count,
                    "eval_duration": total_duration // 2
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = {"error": f"Mock LLM error: {str(e)}"}
                self.wfile.write(json.dumps(error_response).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        """Custom logging to show requests"""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")

def run_server(port=11434):
    """Run the mock LLM server"""
    with socketserver.TCPServer(("", port), MockLLMHandler) as httpd:
        print(f"🚀 Starting Mock LLM Service on port {port}...")
        print(f"📍 Health check: http://localhost:{port}/health")
        print(f"🤖 Generate endpoint: http://localhost:{port}/api/generate")
        print(f"📋 Models endpoint: http://localhost:{port}/api/tags")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server() 