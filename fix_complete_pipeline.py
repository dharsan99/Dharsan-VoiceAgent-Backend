#!/usr/bin/env python3
"""
Complete Voice Agent Pipeline Fix
This script sets up the complete voice agent pipeline with all services working locally.
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
import requests
from pathlib import Path

class CompletePipelineFix:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.v2_dir = self.project_root / "v2"
        self.services = {}
        self.test_results = {}
        
    def setup_environment(self):
        """Set up environment variables for local services"""
        print("🔧 Setting up environment for complete pipeline...")
        
        # Set all service URLs to localhost
        os.environ["STT_SERVICE_URL"] = "http://localhost:8000"
        os.environ["TTS_SERVICE_URL"] = "http://localhost:5000"
        os.environ["LLM_SERVICE_URL"] = "http://localhost:11434"
        os.environ["KAFKA_BROKERS"] = "localhost:9092"
        
        # Set other required environment variables
        os.environ["STT_MODEL"] = "latest_long"
        os.environ["LLM_MODEL"] = "mock-llm:latest"
        os.environ["TTS_VOICE"] = "en-US-Neural2-A"
        os.environ["TTS_LANGUAGE"] = "en-US"
        
        print("✅ Environment variables set for local services")
        print(f"   STT_SERVICE_URL: {os.environ['STT_SERVICE_URL']}")
        print(f"   TTS_SERVICE_URL: {os.environ['TTS_SERVICE_URL']}")
        print(f"   LLM_SERVICE_URL: {os.environ['LLM_SERVICE_URL']}")
        
    def start_redpanda(self):
        """Start Redpanda (Kafka)"""
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
            
            time.sleep(10)
            print("✅ Redpanda started")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start Redpanda: {e}")
            print("⚠️  Continuing without Kafka (some features may not work)")
            return False
    
    def start_mock_services(self):
        """Start all mock services"""
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
        
        # Start mock STT service
        try:
            stt_dir = self.v2_dir / "stt-service"
            if (stt_dir / "mock_stt_simple.py").exists():
                stt_process = subprocess.Popen([
                    sys.executable, "mock_stt_simple.py"
                ], cwd=stt_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.services["stt"] = stt_process
                print("✅ Mock STT service started")
            else:
                print("⚠️  Mock STT service not found, will use remote STT")
        except Exception as e:
            print(f"❌ Failed to start mock STT: {e}")
        
        # Start mock TTS service
        try:
            tts_dir = self.v2_dir / "tts-service"
            if (tts_dir / "mock_tts_simple.py").exists():
                tts_process = subprocess.Popen([
                    sys.executable, "mock_tts_simple.py"
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
    
    def start_local_orchestrator(self):
        """Start the orchestrator locally"""
        print("🚀 Starting local orchestrator...")
        
        try:
            orchestrator_dir = self.v2_dir / "orchestrator"
            
            # Check if Go is available
            result = subprocess.run(["go", "version"], capture_output=True, text=True)
            if result.returncode != 0:
                print("❌ Go not found. Please install Go to run the orchestrator locally.")
                return False
            
            # Start orchestrator with environment variables
            orchestrator_process = subprocess.Popen([
                "go", "run", "main.go"
            ], cwd=orchestrator_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=os.environ.copy())
            self.services["orchestrator"] = orchestrator_process
            
            # Wait for orchestrator to start
            time.sleep(10)
            print("✅ Local orchestrator started")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start local orchestrator: {e}")
            return False
    
    def test_service_connectivity(self):
        """Test if all services are responding"""
        print("🔍 Testing service connectivity...")
        
        services_to_test = {
            "llm": "http://localhost:11434/health",
        }
        
        # Add STT and TTS if they were started
        if "stt" in self.services:
            services_to_test["stt"] = "http://localhost:8000/health"
        if "tts" in self.services:
            services_to_test["tts"] = "http://localhost:5000/health"
        
        # Test orchestrator
        services_to_test["orchestrator"] = "http://localhost:8001/health"
        
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
        
        wav_path = self.project_root / "test_audio_complete_pipeline.wav"
        with wave.open(str(wav_path), 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        
        print(f"✅ Test audio generated: {wav_path}")
        return wav_path
    
    async def test_complete_pipeline(self):
        """Test the complete pipeline"""
        print("🔌 Testing complete pipeline...")
        
        try:
            # Connect to local orchestrator
            uri = "ws://localhost:8001/ws"
            print(f"🔗 Connecting to: {uri}")
            
            async with websockets.connect(uri) as websocket:
                print("✅ Connected to local orchestrator")
                self.test_results["connection"] = "PASS"
                
                # Send greeting
                session_id = f"complete_pipeline_test_{int(time.time())}"
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
                
                # Monitor complete pipeline
                print("⏳ Monitoring complete pipeline...")
                start_time = time.time()
                pipeline_complete = False
                
                while time.time() - start_time < 120:  # Wait up to 2 minutes
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        data = json.loads(response)
                        
                        print(f"📥 Received: {data}")
                        
                        # Track pipeline progress
                        if data.get("type") == "service_status":
                            service = data.get('service', 'unknown')
                            state = data.get('state', 'unknown')
                            message = data.get('message', '')
                            
                            if service == "stt" and state == "complete":
                                print("✅ STT service completed!")
                                self.test_results["stt_complete"] = "PASS"
                            elif service == "llm" and state == "complete":
                                print("✅ LLM service completed!")
                                self.test_results["llm_complete"] = "PASS"
                            elif service == "tts" and state == "complete":
                                print("✅ TTS service completed!")
                                self.test_results["tts_complete"] = "PASS"
                                pipeline_complete = True
                                break
                        
                        # Check for final responses
                        elif data.get("event") == "llm_response_text":
                            print("✅ LLM response received!")
                            self.test_results["llm_response"] = "PASS"
                        elif data.get("event") == "tts_audio_chunk":
                            print("✅ TTS audio received!")
                            self.test_results["tts_audio"] = "PASS"
                            pipeline_complete = True
                            break
                        elif data.get("type") == "pipeline_state_update":
                            state = data.get('state', 'unknown')
                            if state == "complete":
                                print("✅ Pipeline completed!")
                                self.test_results["pipeline_complete"] = "PASS"
                                pipeline_complete = True
                                break
                                
                    except asyncio.TimeoutError:
                        continue
                
                if not pipeline_complete:
                    print("❌ Pipeline did not complete within timeout")
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
        print("\n" + "="*60)
        print("📊 COMPLETE PIPELINE FIX RESULTS")
        print("="*60)
        
        for test_name, result in self.test_results.items():
            if result.startswith("PASS"):
                print(f"{test_name:30} ✅ PASS")
            else:
                print(f"{test_name:30} ❌ {result}")
        
        print("="*60)
        
        passed = sum(1 for result in self.test_results.values() if result.startswith("PASS"))
        total = len(self.test_results)
        
        if passed == total:
            print("🎉 ALL TESTS PASSED!")
            print("✅ Complete voice agent pipeline is working!")
        else:
            print(f"⚠️  {passed}/{total} tests passed")
            
        # Analysis
        print("\n🔍 ANALYSIS:")
        if "pipeline_complete" in self.test_results and self.test_results["pipeline_complete"] == "PASS":
            print("✅ SUCCESS: Complete pipeline is working!")
            print("   All services are functioning correctly.")
        elif "tts_audio" in self.test_results and self.test_results["tts_audio"] == "PASS":
            print("✅ SUCCESS: TTS audio received!")
            print("   The pipeline is working end-to-end.")
        elif "llm_response" in self.test_results and self.test_results["llm_response"] == "PASS":
            print("✅ SUCCESS: LLM response received!")
            print("   The LLM service is working correctly.")
        elif "pipeline_timeout" in self.test_results:
            print("❌ ISSUE: Pipeline timeout")
            print("   Some services may not be responding correctly.")
        else:
            print("⚠️  PARTIAL SUCCESS: Some components working")

async def main():
    """Main function"""
    print("🚀 Starting Complete Voice Agent Pipeline Fix")
    print("="*60)
    
    fix = CompletePipelineFix()
    
    try:
        # Setup
        fix.setup_environment()
        
        # Start services
        fix.start_redpanda()
        
        if not fix.start_mock_services():
            print("❌ Failed to start mock services")
            return
        
        if not fix.start_local_orchestrator():
            print("❌ Failed to start local orchestrator")
            print("💡 Try using the remote orchestrator instead")
            return
        
        # Test service connectivity
        fix.test_service_connectivity()
        
        # Wait for all services to be ready
        print("⏳ Waiting for all services to be ready...")
        time.sleep(10)
        
        # Test complete pipeline
        await fix.test_complete_pipeline()
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        fix.cleanup()
        fix.print_results()

if __name__ == "__main__":
    asyncio.run(main()) 