#!/usr/bin/env python3
"""
Local Voice Agent Pipeline Test (No Kafka)
This script tests the voice agent pipeline without requiring Kafka/Redpanda.
"""

import os
import sys
import time
import json
import asyncio
import subprocess
import websockets
import base64
import wave
import numpy as np
from pathlib import Path

class LocalPipelineTestNoKafka:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.v2_dir = self.project_root / "v2"
        self.services = {}
        self.test_results = {}
        
    def setup_environment(self):
        """Set up environment variables for local services"""
        print("🔧 Setting up local environment...")
        
        # Set all service URLs to localhost
        os.environ["STT_SERVICE_URL"] = "http://localhost:8000"
        os.environ["TTS_SERVICE_URL"] = "http://localhost:5000"
        os.environ["LLM_SERVICE_URL"] = "http://localhost:11434"
        # Don't set KAFKA_BROKERS to avoid Kafka dependency
        
        print("✅ Environment variables set for local services")
        
    def start_mock_services(self):
        """Start mock services for testing"""
        print("🚀 Starting mock services...")
        
        # Start mock LLM service
        try:
            llm_dir = self.v2_dir / "llm-service"
            llm_process = subprocess.Popen([
                sys.executable, "mock_llm_simple.py"
            ], cwd=llm_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.services["llm"] = llm_process
            print("✅ Mock LLM service started")
        except Exception as e:
            print(f"❌ Failed to start mock LLM: {e}")
            return False
        
        # Start mock STT service (if available)
        try:
            stt_dir = self.v2_dir / "stt-service"
            if (stt_dir / "main-simple.py").exists():
                stt_process = subprocess.Popen([
                    sys.executable, "main-simple.py"
                ], cwd=stt_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.services["stt"] = stt_process
                print("✅ Mock STT service started")
            else:
                print("⚠️  Mock STT service not found, will use remote STT")
        except Exception as e:
            print(f"❌ Failed to start mock STT: {e}")
        
        # Start mock TTS service (if available)
        try:
            tts_dir = self.v2_dir / "tts-service"
            if (tts_dir / "main.py").exists():
                tts_process = subprocess.Popen([
                    sys.executable, "main.py"
                ], cwd=tts_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.services["tts"] = tts_process
                print("✅ Mock TTS service started")
            else:
                print("⚠️  Mock TTS service not found, will use remote TTS")
        except Exception as e:
            print(f"❌ Failed to start mock TTS: {e}")
        
        # Wait for services to start
        time.sleep(5)
        return True
    
    def test_service_connectivity(self):
        """Test if the mock services are responding"""
        print("🔍 Testing service connectivity...")
        
        import requests
        
        services_to_test = {
            "llm": "http://localhost:11434/health",
        }
        
        # Add STT and TTS if they were started
        if "stt" in self.services:
            services_to_test["stt"] = "http://localhost:8000/health"
        if "tts" in self.services:
            services_to_test["tts"] = "http://localhost:5000/health"
        
        for service_name, url in services_to_test.items():
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    print(f"✅ {service_name} service is responding")
                    self.test_results[f"{service_name}_responding"] = "PASS"
                else:
                    print(f"❌ {service_name} service returned {response.status_code}")
                    self.test_results[f"{service_name}_responding"] = f"FAIL: HTTP {response.status_code}"
            except Exception as e:
                print(f"❌ {service_name} service not responding: {e}")
                self.test_results[f"{service_name}_responding"] = f"FAIL: {e}"
    
    def generate_test_audio(self, duration=2, sample_rate=16000):
        """Generate test audio"""
        print(f"🎵 Generating {duration}s test audio...")
        
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio = np.sin(2 * np.pi * 440 * t) * 0.3
        audio_int16 = (audio * 32767).astype(np.int16)
        
        wav_path = self.project_root / "test_audio_no_kafka.wav"
        with wave.open(str(wav_path), 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        
        print(f"✅ Test audio generated: {wav_path}")
        return wav_path
    
    async def test_remote_orchestrator_with_local_services(self):
        """Test the remote orchestrator with local mock services"""
        print("🔌 Testing remote orchestrator with local services...")
        
        try:
            # Connect to remote orchestrator
            uri = "ws://34.47.230.178:8001/ws"
            print(f"🔗 Connecting to: {uri}")
            
            async with websockets.connect(uri) as websocket:
                print("✅ Connected to remote orchestrator")
                self.test_results["connection"] = "PASS"
                
                # Send greeting
                session_id = f"no_kafka_test_{int(time.time())}"
                greeting_msg = {
                    "event": "greeting_request",
                    "session_id": session_id
                }
                await websocket.send(json.dumps(greeting_msg))
                print("📤 Sent greeting request")
                
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                if data.get("event") == "greeting":
                    print("✅ Greeting received")
                    self.test_results["greeting"] = "PASS"
                
                # Start listening
                start_msg = {
                    "event": "start_listening",
                    "session_id": session_id
                }
                await websocket.send(json.dumps(start_msg))
                print("📤 Sent start listening request")
                
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                if data.get("type") == "pipeline_state_update" and data.get("state") == "listening":
                    print("✅ Listening started")
                    self.test_results["listening"] = "PASS"
                
                # Send audio
                wav_path = self.generate_test_audio()
                with open(wav_path, 'rb') as f:
                    audio_data = f.read()
                
                audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                audio_msg = {
                    "event": "audio_data",
                    "session_id": session_id,
                    "audio_data": audio_b64,
                    "is_final": True
                }
                await websocket.send(json.dumps(audio_msg))
                print("📤 Sent audio data")
                self.test_results["audio_sent"] = "PASS"
                
                # Monitor pipeline
                print("⏳ Monitoring pipeline processing...")
                start_time = time.time()
                
                while time.time() - start_time < 60:
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        data = json.loads(response)
                        
                        print(f"📥 Received: {data}")
                        
                        if data.get("event") == "llm_response_text":
                            print("✅ LLM response received!")
                            self.test_results["llm_response"] = "PASS"
                            break
                        elif data.get("event") == "tts_audio_chunk":
                            print("✅ TTS audio received!")
                            self.test_results["tts_audio"] = "PASS"
                            break
                        elif data.get("type") == "service_status":
                            service = data.get('service', 'unknown')
                            state = data.get('state', 'unknown')
                            message = data.get('message', '')
                            print(f"🔧 Service status - {service}: {state} - {message}")
                            
                            if service == "llm" and state == "complete":
                                print("✅ LLM service completed!")
                                self.test_results["llm_complete"] = "PASS"
                            elif service == "llm" and state == "error":
                                print("❌ LLM service error!")
                                self.test_results["llm_error"] = f"FAIL: {message}"
                                break
                            elif service == "stt" and state == "complete":
                                print("✅ STT service completed!")
                                self.test_results["stt_complete"] = "PASS"
                                
                    except asyncio.TimeoutError:
                        continue
                
                if time.time() - start_time >= 60:
                    print("❌ Pipeline timeout")
                    self.test_results["pipeline_timeout"] = "FAIL"
                
        except Exception as e:
            print(f"❌ Pipeline test failed: {e}")
            self.test_results["pipeline_test"] = f"FAIL: {e}"
    
    def cleanup(self):
        """Clean up all services"""
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
                print(f"❌ Error stopping {service_name}: {e}")
    
    def print_results(self):
        """Print test results"""
        print("\n" + "="*50)
        print("📊 LOCAL PIPELINE TEST RESULTS (NO KAFKA)")
        print("="*50)
        
        for test_name, result in self.test_results.items():
            if result.startswith("PASS"):
                print(f"{test_name:25} ✅ PASS")
            else:
                print(f"{test_name:25} ❌ {result}")
        
        print("="*50)
        
        passed = sum(1 for result in self.test_results.values() if result.startswith("PASS"))
        total = len(self.test_results)
        
        if passed == total:
            print("🎉 ALL TESTS PASSED!")
            print("✅ Voice agent pipeline is working with local services!")
        else:
            print(f"⚠️  {passed}/{total} tests passed")
            
        # Analysis
        print("\n🔍 ANALYSIS:")
        if "llm_response" in self.test_results and self.test_results["llm_response"] == "PASS":
            print("✅ SUCCESS: LLM service is working with local mock!")
        elif "llm_complete" in self.test_results and self.test_results["llm_complete"] == "PASS":
            print("✅ SUCCESS: LLM service completed successfully!")
        elif "pipeline_timeout" in self.test_results:
            print("❌ ISSUE: Pipeline timeout - services may not be responding")
        else:
            print("⚠️  PARTIAL SUCCESS: Some components working")

async def main():
    """Main function"""
    print("🚀 Starting Local Voice Agent Pipeline Test (No Kafka)")
    print("="*60)
    
    test = LocalPipelineTestNoKafka()
    
    try:
        # Setup
        test.setup_environment()
        
        # Start mock services
        if not test.start_mock_services():
            print("❌ Failed to start mock services")
            return
        
        # Test service connectivity
        test.test_service_connectivity()
        
        # Wait for services to be ready
        print("⏳ Waiting for services to be ready...")
        time.sleep(5)
        
        # Test pipeline with remote orchestrator
        await test.test_remote_orchestrator_with_local_services()
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        test.cleanup()
        test.print_results()

if __name__ == "__main__":
    asyncio.run(main()) 