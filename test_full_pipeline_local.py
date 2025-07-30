#!/usr/bin/env python3
"""
Full Voice Agent Pipeline Test - Local Environment
This script sets up the local environment and tests the complete voice agent pipeline.
"""

import os
import sys
import time
import json
import asyncio
import subprocess
import threading
import websockets
import base64
import wave
import numpy as np
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

class LocalVoiceAgentTest:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.v2_dir = self.project_root / "v2"
        self.services = {}
        self.test_results = {}
        
    def setup_environment(self):
        """Set up environment variables for local services"""
        print("🔧 Setting up local environment variables...")
        
        # Set service URLs to localhost
        os.environ["STT_SERVICE_URL"] = "http://localhost:8000"
        os.environ["TTS_SERVICE_URL"] = "http://localhost:5000"
        os.environ["LLM_SERVICE_URL"] = "http://localhost:11434"
        os.environ["KAFKA_BROKERS"] = "localhost:9092"
        
        # Set API keys if available
        api_keys = {
            "DEEPGRAM_API_KEY": os.getenv("DEEPGRAM_API_KEY", ""),
            "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
            "ELEVENLABS_API_KEY": os.getenv("ELEVENLABS_API_KEY", ""),
            "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
        }
        
        for key, value in api_keys.items():
            if value:
                os.environ[key] = value
                print(f"✅ {key} is set")
            else:
                print(f"⚠️  {key} is not set (some features may not work)")
        
        print("✅ Environment setup complete")
    
    def start_redpanda(self):
        """Start Redpanda (Kafka) using docker-compose"""
        print("🚀 Starting Redpanda (Kafka)...")
        
        try:
            # Check if Redpanda is already running
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=redpanda", "--format", "{{.Names}}"],
                capture_output=True, text=True
            )
            
            if "redpanda" in result.stdout:
                print("✅ Redpanda is already running")
                return True
            
            # Start Redpanda
            subprocess.run([
                "docker-compose", "-f", str(self.v2_dir / "docker-compose.yml"), 
                "up", "-d", "redpanda"
            ], check=True)
            
            # Wait for Redpanda to be ready
            print("⏳ Waiting for Redpanda to be ready...")
            time.sleep(10)
            
            print("✅ Redpanda started successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to start Redpanda: {e}")
            return False
        except FileNotFoundError:
            print("❌ Docker not found. Please install Docker and try again.")
            return False
    
    def start_stt_service(self):
        """Start the STT service locally"""
        print("🚀 Starting STT service...")
        
        try:
            stt_dir = self.v2_dir / "stt-service"
            process = subprocess.Popen([
                sys.executable, "main-simple.py"
            ], cwd=stt_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            self.services["stt"] = process
            time.sleep(3)  # Wait for service to start
            
            print("✅ STT service started")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start STT service: {e}")
            return False
    
    def start_llm_service(self):
        """Start the LLM service locally"""
        print("🚀 Starting LLM service...")
        
        try:
            llm_dir = self.v2_dir / "llm-service"
            process = subprocess.Popen([
                sys.executable, "mock_llm_simple.py"
            ], cwd=llm_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            self.services["llm"] = process
            time.sleep(3)  # Wait for service to start
            
            print("✅ LLM service started")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start LLM service: {e}")
            return False
    
    def start_tts_service(self):
        """Start the TTS service locally"""
        print("🚀 Starting TTS service...")
        
        try:
            tts_dir = self.v2_dir / "tts-service"
            process = subprocess.Popen([
                sys.executable, "main.py"
            ], cwd=tts_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            self.services["tts"] = process
            time.sleep(3)  # Wait for service to start
            
            print("✅ TTS service started")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start TTS service: {e}")
            return False
    
    def start_orchestrator(self):
        """Start the orchestrator service"""
        print("🚀 Starting Orchestrator service...")
        
        try:
            orchestrator_dir = self.v2_dir / "orchestrator"
            process = subprocess.Popen([
                "go", "run", "main.go"
            ], cwd=orchestrator_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            self.services["orchestrator"] = process
            time.sleep(5)  # Wait for service to start
            
            print("✅ Orchestrator service started")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start Orchestrator service: {e}")
            return False
    
    def generate_test_audio(self, duration=3, sample_rate=16000):
        """Generate a simple test audio tone"""
        print(f"🎵 Generating {duration}s test audio...")
        
        # Generate a 440Hz sine wave
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio = np.sin(2 * np.pi * 440 * t) * 0.3
        
        # Convert to 16-bit PCM
        audio_int16 = (audio * 32767).astype(np.int16)
        
        # Create WAV file
        wav_path = self.project_root / "test_audio_local.wav"
        with wave.open(str(wav_path), 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        
        print(f"✅ Test audio generated: {wav_path}")
        return wav_path
    
    async def test_websocket_connection(self):
        """Test the WebSocket connection to the orchestrator"""
        print("🔌 Testing WebSocket connection...")
        
        try:
            uri = "ws://localhost:8001/ws"
            async with websockets.connect(uri) as websocket:
                print("✅ WebSocket connected successfully")
                
                # Send greeting request
                greeting_msg = {
                    "event": "greeting_request",
                    "session_id": f"test_session_{int(time.time())}"
                }
                await websocket.send(json.dumps(greeting_msg))
                print("📤 Sent greeting request")
                
                # Wait for greeting response
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                print(f"📥 Received: {data}")
                
                if data.get("event") == "greeting":
                    print("✅ Greeting received successfully")
                    self.test_results["greeting"] = "PASS"
                else:
                    print("❌ Unexpected greeting response")
                    self.test_results["greeting"] = "FAIL"
                
                # Test start listening
                start_msg = {
                    "event": "start_listening",
                    "session_id": greeting_msg["session_id"]
                }
                await websocket.send(json.dumps(start_msg))
                print("📤 Sent start listening request")
                
                # Wait for listening confirmation
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                print(f"📥 Received: {data}")
                
                if data.get("event") == "listening_started":
                    print("✅ Listening started successfully")
                    self.test_results["listening"] = "PASS"
                else:
                    print("❌ Unexpected listening response")
                    self.test_results["listening"] = "FAIL"
                
                # Test audio data sending
                wav_path = self.generate_test_audio()
                with open(wav_path, 'rb') as f:
                    audio_data = f.read()
                
                # Convert to base64
                audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                
                audio_msg = {
                    "event": "audio_data",
                    "session_id": greeting_msg["session_id"],
                    "audio_data": audio_b64,
                    "is_final": True
                }
                await websocket.send(json.dumps(audio_msg))
                print("📤 Sent audio data")
                
                # Wait for pipeline processing (this might take a while)
                print("⏳ Waiting for pipeline processing...")
                start_time = time.time()
                
                while time.time() - start_time < 60:  # Wait up to 60 seconds
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        data = json.loads(response)
                        print(f"📥 Received: {data}")
                        
                        # Check for various response types
                        if data.get("event") == "llm_response_text":
                            print("✅ LLM response received")
                            self.test_results["llm_response"] = "PASS"
                            break
                        elif data.get("type") == "pipeline_state_update":
                            print(f"🔄 Pipeline state: {data.get('state', 'unknown')}")
                        elif data.get("type") == "info":
                            print(f"ℹ️  Info: {data.get('message', '')}")
                        elif data.get("event") == "tts_audio_chunk":
                            print("✅ TTS audio chunk received")
                            self.test_results["tts_audio"] = "PASS"
                            break
                            
                    except asyncio.TimeoutError:
                        print("⏳ Still waiting for response...")
                        continue
                
                if time.time() - start_time >= 60:
                    print("❌ Timeout waiting for pipeline response")
                    self.test_results["pipeline_timeout"] = "FAIL"
                
        except Exception as e:
            print(f"❌ WebSocket test failed: {e}")
            self.test_results["websocket"] = "FAIL"
    
    def cleanup_services(self):
        """Clean up all started services"""
        print("🛑 Cleaning up services...")
        
        for service_name, process in self.services.items():
            try:
                process.terminate()
                process.wait(timeout=5)
                print(f"✅ {service_name} service stopped")
            except subprocess.TimeoutExpired:
                process.kill()
                print(f"⚠️  {service_name} service force killed")
            except Exception as e:
                print(f"❌ Error stopping {service_name} service: {e}")
        
        # Stop Redpanda
        try:
            subprocess.run([
                "docker-compose", "-f", str(self.v2_dir / "docker-compose.yml"), 
                "down"
            ], check=True)
            print("✅ Redpanda stopped")
        except Exception as e:
            print(f"⚠️  Error stopping Redpanda: {e}")
    
    def print_results(self):
        """Print test results"""
        print("\n" + "="*50)
        print("📊 TEST RESULTS")
        print("="*50)
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result == "PASS" else "❌ FAIL"
            print(f"{test_name:20} {status}")
        
        print("="*50)
        
        # Overall result
        passed = sum(1 for result in self.test_results.values() if result == "PASS")
        total = len(self.test_results)
        
        if passed == total:
            print("🎉 ALL TESTS PASSED!")
        else:
            print(f"⚠️  {passed}/{total} tests passed")
    
    def run_full_test(self):
        """Run the complete test suite"""
        print("🚀 Starting Full Voice Agent Pipeline Test")
        print("="*50)
        
        try:
            # Setup
            self.setup_environment()
            
            # Start services
            if not self.start_redpanda():
                print("❌ Failed to start Redpanda")
                return False
            
            if not self.start_stt_service():
                print("❌ Failed to start STT service")
                return False
            
            if not self.start_llm_service():
                print("❌ Failed to start LLM service")
                return False
            
            if not self.start_tts_service():
                print("❌ Failed to start TTS service")
                return False
            
            if not self.start_orchestrator():
                print("❌ Failed to start Orchestrator service")
                return False
            
            # Wait for all services to be ready
            print("⏳ Waiting for all services to be ready...")
            time.sleep(10)
            
            # Run WebSocket test
            asyncio.run(self.test_websocket_connection())
            
            return True
            
        except KeyboardInterrupt:
            print("\n🛑 Test interrupted by user")
            return False
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            return False
        finally:
            self.cleanup_services()
            self.print_results()

def main():
    """Main function"""
    test = LocalVoiceAgentTest()
    success = test.run_full_test()
    
    if success:
        print("\n🎉 Full pipeline test completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Full pipeline test failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 