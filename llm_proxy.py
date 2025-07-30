#!/usr/bin/env python3
"""
LLM Service Proxy
This proxy redirects LLM requests from the orchestrator to a local mock LLM service.
"""

import http.server
import socketserver
import urllib.request
import urllib.parse
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

class LLMProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Proxy GET requests to local LLM service"""
        try:
            # Forward to local LLM service
            local_url = f"http://localhost:11434{self.path}"
            print(f"🔗 Proxying GET {self.path} -> {local_url}")
            
            with urllib.request.urlopen(local_url) as response:
                self.send_response(response.status)
                for header, value in response.getheaders():
                    self.send_header(header, value)
                self.end_headers()
                self.wfile.write(response.read())
                
        except Exception as e:
            print(f"❌ Proxy GET error: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def do_POST(self):
        """Proxy POST requests to local LLM service"""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            # Forward to local LLM service
            local_url = f"http://localhost:11434{self.path}"
            print(f"🔗 Proxying POST {self.path} -> {local_url}")
            print(f"📊 Request body size: {len(body)} bytes")
            
            # Create request
            req = urllib.request.Request(local_url, data=body, method='POST')
            req.add_header('Content-Type', self.headers.get('Content-Type', 'application/json'))
            
            with urllib.request.urlopen(req) as response:
                self.send_response(response.status)
                for header, value in response.getheaders():
                    self.send_header(header, value)
                self.end_headers()
                self.wfile.write(response.read())
                
        except Exception as e:
            print(f"❌ Proxy POST error: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def log_message(self, format, *args):
        """Custom logging"""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")

def run_proxy(port=11434):
    """Run the LLM proxy server"""
    with HTTPServer(("", port), LLMProxyHandler) as httpd:
        print(f"🚀 Starting LLM Proxy on port {port}")
        print(f"📍 Proxy URL: http://localhost:{port}")
        print(f"🔗 Forwarding to: http://localhost:11434")
        print("Press Ctrl+C to stop")
        httpd.serve_forever()

if __name__ == "__main__":
    run_proxy() 