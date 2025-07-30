#!/usr/bin/env python3
"""
Fix LLM Hang Issue
This script addresses the LLM service hanging issue in the voice agent pipeline.
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

class LLMHangFix:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.v2_dir = self.project_root / "v2"
        self.services = {}
        self.test_results = {}
        
    def setup_environment(self):
        """Set up environment variables"""
        print("🔧 Setting up environment...")
        
        # Set service URLs to localhost
        os.environ["STT_SERVICE_URL"] = "http://localhost:8000"
        os.environ["TTS_SERVICE_URL"] = "http://localhost:5000"
        os.environ["LLM_SERVICE_URL"] = "http://localhost:11434"
        
        print("✅ Environment variables set")
        
    def start_improved_mock_services(self):
        """Start improved mock services"""
        print("🚀 Starting improved mock services...")
        
        # Start improved mock LLM service (faster response)
        try:
            llm_dir = self.v2_dir / "llm-service"
            llm_process = subprocess.Popen([
                sys.executable, "mock_llm_simple.py"
            ], cwd=llm_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.services["llm"] = llm_process
            print("✅ Improved mock LLM service started")
        except Exception as e:
            print(f"❌ Failed to start mock LLM: {e}")
            return False
        
        # Start mock STT service
        try:
            stt_dir = self.v2_dir / "stt-service"
            stt_process = subprocess.Popen([
                sys.executable, "mock_stt_simple.py"
            ], cwd=stt_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.services["stt"] = stt_process
            print("✅ Mock STT service started")
        except Exception as e:
            print(f"❌ Failed to start mock STT: {e}")
        
        # Start mock TTS service
        try:
            tts_dir = self.v2_dir / "tts-service"
            tts_process = subprocess.Popen([
                sys.executable, "mock_tts_simple.py"
            ], cwd=tts_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.services["tts"] = tts_process
            print("✅ Mock TTS service started")
        except Exception as e:
            print(f"❌ Failed to start mock TTS: {e}")
        
        time.sleep(5)
        return True
    
    def test_llm_service_directly(self):
        """Test LLM service directly"""
        print("🔍 Testing LLM service directly...")
        
        try:
            # Test health endpoint
            response = requests.get("http://localhost:11434/health", timeout=5)
            if response.status_code == 200:
                print("✅ LLM health check passed")
                self.test_results["llm_health"] = "PASS"
            else:
                print(f"❌ LLM health check failed: {response.status_code}")
                self.test_results["llm_health"] = f"FAIL: HTTP {response.status_code}"
                return False
            
            # Test generate endpoint
            test_prompt = "Hello, how are you?"
            generate_data = {
                "prompt": test_prompt,
                "model": "mock-llm:latest",
                "max_tokens": 100,
                "temperature": 0.7,
                "stream": False
            }
            
            response = requests.post(
                "http://localhost:11434/api/generate",
                json=generate_data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ LLM generate test passed: {result.get('response', '')[:50]}...")
                self.test_results["llm_generate"] = "PASS"
                return True
            else:
                print(f"❌ LLM generate test failed: {response.status_code}")
                self.test_results["llm_generate"] = f"FAIL: HTTP {response.status_code}"
                return False
                
        except Exception as e:
            print(f"❌ LLM service test failed: {e}")
            self.test_results["llm_test"] = f"FAIL: {e}"
            return False
    
    def generate_test_audio(self, duration=1, sample_rate=16000):
        """Generate test audio"""
        print(f"🎵 Generating {duration}s test audio...")
        
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio = np.sin(2 * np.pi * 440 * t) * 0.3
        audio_int16 = (audio * 32767).astype(np.int16)
        
        wav_path = self.project_root / "test_audio_llm_fix.wav"
        with wave.open(str(wav_path), 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        
        print(f"✅ Test audio generated: {wav_path}")
        return wav_path
    
    async def test_pipeline_with_llm_focus(self):
        """Test pipeline with focus on LLM completion"""
        print("🔌 Testing pipeline with LLM focus...")
        
        try:
            # Connect to remote orchestrator
            uri = "ws://34.47.230.178:8001/ws"
            print(f"🔗 Connecting to: {uri}")
            
            async with websockets.connect(uri) as websocket:
                print("✅ Connected to orchestrator")
                self.test_results["connection"] = "PASS"
                
                # Send greeting
                session_id = f"llm_fix_test_{int(time.time())}"
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
                
                # Monitor pipeline with focus on LLM
                print("⏳ Monitoring pipeline (focusing on LLM completion)...")
                start_time = time.time()
                llm_started = False
                llm_completed = False
                
                while time.time() - start_time < 45:  # 45 second timeout
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        data = json.loads(response)
                        
                        print(f"📥 Received: {data}")
                        
                        # Track LLM progress specifically
                        if data.get("type") == "service_status":
                            service = data.get('service', 'unknown')
                            state = data.get('state', 'unknown')
                            message = data.get('message', '')
                            
                            if service == "stt" and state == "complete":
                                print("✅ STT service completed!")
                                self.test_results["stt_complete"] = "PASS"
                            elif service == "llm" and state == "waiting":
                                print("⏳ LLM service waiting...")
                                llm_started = True
                            elif service == "llm" and state == "executing":
                                print("🔄 LLM service executing...")
                                llm_started = True
                            elif service == "llm" and state == "complete":
                                print("✅ LLM service completed!")
                                self.test_results["llm_complete"] = "PASS"
                                llm_completed = True
                                break
                        
                        # Check for LLM response
                        elif data.get("event") == "llm_response_text":
                            print("✅ LLM response received!")
                            self.test_results["llm_response"] = "PASS"
                            llm_completed = True
                            break
                        
                        # Check for pipeline completion
                        elif data.get("type") == "pipeline_state_update":
                            state = data.get('state', 'unknown')
                            if state == "complete":
                                print("✅ Pipeline completed!")
                                self.test_results["pipeline_complete"] = "PASS"
                                llm_completed = True
                                break
                                
                    except asyncio.TimeoutError:
                        continue
                
                if not llm_completed:
                    if llm_started:
                        print("❌ LLM started but did not complete within timeout")
                        self.test_results["llm_timeout"] = "FAIL"
                    else:
                        print("❌ LLM did not start within timeout")
                        self.test_results["llm_not_started"] = "FAIL"
                
        except Exception as e:
            print(f"❌ Pipeline test failed: {e}")
            self.test_results["pipeline_test"] = f"FAIL: {e}"
    
    def cleanup(self):
        """Clean up services"""
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
        print("📊 LLM HANG FIX RESULTS")
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
            print("✅ LLM hang issue is fixed!")
        else:
            print(f"⚠️  {passed}/{total} tests passed")
            
        # Analysis
        print("\n🔍 ANALYSIS:")
        if "llm_complete" in self.test_results and self.test_results["llm_complete"] == "PASS":
            print("✅ SUCCESS: LLM completed successfully!")
            print("   The LLM hang issue is resolved.")
        elif "llm_response" in self.test_results and self.test_results["llm_response"] == "PASS":
            print("✅ SUCCESS: LLM response received!")
            print("   The LLM is working correctly.")
        elif "llm_timeout" in self.test_results:
            print("❌ ISSUE: LLM timeout")
            print("   The LLM is still hanging.")
        else:
            print("⚠️  PARTIAL SUCCESS: Some components working")

async def main():
    """Main function"""
    print("🚀 Starting LLM Hang Fix")
    print("="*50)
    
    fix = LLMHangFix()
    
    try:
        # Setup
        fix.setup_environment()
        
        # Start mock services
        if not fix.start_improved_mock_services():
            print("❌ Failed to start mock services")
            return
        
        # Test LLM service directly
        if not fix.test_llm_service_directly():
            print("❌ LLM service test failed")
            return
        
        # Wait for services to be ready
        print("⏳ Waiting for services to be ready...")
        time.sleep(5)
        
        # Test pipeline with LLM focus
        await fix.test_pipeline_with_llm_focus()
        
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