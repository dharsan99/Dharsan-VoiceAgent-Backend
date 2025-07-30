#!/usr/bin/env python3
"""
Simple Mock STT Service for Testing
Handles audio transcription requests and returns mock transcriptions
"""

import json
import time
import random
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
import threading
import wave
import io

# Mock transcriptions for different audio inputs
MOCK_TRANSCRIPTIONS = [
    "Hello, this is a test of the voice agent system.",
    "How are you doing today? I hope everything is going well.",
    "The weather is quite nice today, isn't it?",
    "I would like to know more about artificial intelligence.",
    "Can you help me with my question about machine learning?",
    "This is a demonstration of the speech to text functionality.",
    "The voice agent pipeline is working correctly.",
    "Thank you for testing the system with me.",
    "I understand what you're saying and I'm here to help.",
    "The transcription service is functioning properly."
]

def get_mock_transcription(audio_data):
    """Generate a realistic mock transcription based on audio data"""
    # Use audio data length to determine transcription
    audio_length = len(audio_data)
    
    # Simple heuristic: longer audio = longer transcription
    if audio_length < 10000:  # Very short audio
        return "Hello."
    elif audio_length < 20000:  # Short audio
        return random.choice(["Hi there.", "Hello.", "Yes."])
    elif audio_length < 50000:  # Medium audio
        return random.choice([
            "Hello, this is a test.",
            "How are you doing?",
            "The system is working."
        ])
    else:  # Longer audio
        return random.choice(MOCK_TRANSCRIPTIONS)

class MockSTTHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests (health check)"""
        if self.path == "/health":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"status": "healthy", "service": "mock-stt"}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        """Handle POST requests (transcribe audio)"""
        if self.path == "/transcribe":
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            try:
                # Parse multipart form data
                content_type = self.headers.get('Content-Type', '')
                if 'multipart/form-data' in content_type:
                    # Extract audio data from multipart form
                    boundary = content_type.split('boundary=')[1]
                    parts = body.split(b'--' + boundary.encode())
                    
                    audio_data = None
                    for part in parts:
                        if b'Content-Disposition: form-data; name="file"' in part:
                            # Extract audio data from file part
                            lines = part.split(b'\r\n')
                            for i, line in enumerate(lines):
                                if b'Content-Type:' in line:
                                    # Audio data starts after the empty line
                                    audio_data = b'\r\n'.join(lines[i+2:])
                                    break
                            break
                    
                    if audio_data:
                        # Simulate processing delay (1-3 seconds)
                        processing_delay = random.uniform(1.0, 3.0)
                        time.sleep(processing_delay)
                        
                        # Generate mock transcription
                        transcription = get_mock_transcription(audio_data)
                        
                        # Calculate mock metrics
                        audio_duration = len(audio_data) / 32000  # Approximate duration
                        confidence = random.uniform(0.85, 0.98)
                        
                        response = {
                            "transcription": transcription,
                            "language": "en",
                            "duration": audio_duration,
                            "confidence": confidence,
                            "model": "mock-stt:latest",
                            "processing_time": processing_delay,
                            "is_final": True
                        }
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(response).encode())
                    else:
                        raise Exception("No audio data found in request")
                else:
                    raise Exception("Unsupported content type")
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = {"error": f"Mock STT error: {str(e)}"}
                self.wfile.write(json.dumps(error_response).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        """Custom logging to show requests"""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")

def run_server(port=8000):
    """Run the mock STT server"""
    with socketserver.TCPServer(("", port), MockSTTHandler) as httpd:
        print(f"🚀 Starting Mock STT Service on port {port}...")
        print(f"📍 Health check: http://localhost:{port}/health")
        print(f"🎤 Transcribe endpoint: http://localhost:{port}/transcribe")
        print("Press Ctrl+C to stop")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server() 