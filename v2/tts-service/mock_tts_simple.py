#!/usr/bin/env python3
"""
Simple Mock TTS Service for Testing
Handles text-to-speech requests and returns mock audio data
"""

import json
import time
import random
import http.server
import socketserver
import wave
import numpy as np
import io

def generate_mock_audio(text, duration=2.0, sample_rate=16000):
    """Generate mock audio data for the given text"""
    # Generate a simple sine wave with varying frequency based on text length
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Vary frequency based on text length
    base_freq = 440 + (len(text) * 10)  # Higher frequency for longer text
    audio = np.sin(2 * np.pi * base_freq * t) * 0.3
    
    # Add some variation
    audio += np.sin(2 * np.pi * (base_freq * 1.5) * t) * 0.1
    
    # Convert to 16-bit PCM
    audio_int16 = (audio * 32767).astype(np.int16)
    
    return audio_int16.tobytes()

class MockTTSHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests (health check)"""
        if self.path == "/health":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"status": "healthy", "service": "mock-tts"}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        """Handle POST requests (text-to-speech)"""
        if self.path == "/synthesize" or self.path == "/":
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            try:
                # Parse JSON request
                request_data = json.loads(body)
                text = request_data.get('text', 'Hello, this is a test.')
                voice = request_data.get('voice', 'en-US-Neural2-A')
                speed = request_data.get('speed', 1.0)
                format_type = request_data.get('format', 'wav')
                
                # Simulate processing delay (0.5-2 seconds)
                processing_delay = random.uniform(0.5, 2.0)
                time.sleep(processing_delay)
                
                # Calculate duration based on text length and speed
                base_duration = len(text.split()) * 0.5  # Rough estimate
                duration = base_duration / speed
                
                # Generate mock audio
                audio_data = generate_mock_audio(text, duration)
                
                # Create WAV file in memory
                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(16000)  # 16kHz
                    wav_file.writeframes(audio_data)
                
                wav_data = wav_buffer.getvalue()
                
                # Prepare response
                response = {
                    "audio_size": len(wav_data),
                    "duration": duration,
                    "voice": voice,
                    "format": format_type,
                    "processing_time": processing_delay
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Content-Length', str(len(wav_data)))
                self.end_headers()
                
                # Send audio data
                self.wfile.write(wav_data)
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = {"error": f"Mock TTS error: {str(e)}"}
                self.wfile.write(json.dumps(error_response).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        """Custom logging to show requests"""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")

def run_server(port=5000):
    """Run the mock TTS server"""
    with socketserver.TCPServer(("", port), MockTTSHandler) as httpd:
        print(f"🚀 Starting Mock TTS Service on port {port}...")
        print(f"📍 Health check: http://localhost:{port}/health")
        print(f"🔊 Synthesize endpoint: http://localhost:{port}/synthesize")
        print("Press Ctrl+C to stop")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server() 