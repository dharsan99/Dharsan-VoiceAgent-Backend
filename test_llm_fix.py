#!/usr/bin/env python3
"""
LLM Service Connection Fix Test
This script specifically addresses the LLM service connection issue.
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

class LLMConnectionFixTest:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.v2_dir = self.project_root / "v2"
        self.mock_llm_process = None
        self.test_results = {}
        
    def setup_environment(self):
        """Set up environment variables"""
        print("🔧 Setting up environment...")
        
        # Set LLM service URL to localhost
        os.environ["LLM_SERVICE_URL"] = "http://localhost:11434"
        
        print("✅ LLM_SERVICE_URL set to: http://localhost:11434")
        
    def start_mock_llm_service(self):
        """Start the mock LLM service"""
        print("🚀 Starting Mock LLM service...")
        
        try:
            llm_dir = self.v2_dir / "llm-service"
            self.mock_llm_process = subprocess.Popen([
                sys.executable, "mock_llm_simple.py"
            ], cwd=llm_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for service to start
            time.sleep(3)
            
            # Test if service is responding
            try:
                response = requests.get("http://localhost:11434/health", timeout=5)
                if response.status_code == 200:
                    print("✅ Mock LLM service started and responding")
                    self.test_results["llm_service_started"] = "PASS"
                    return True
                else:
                    print(f"❌ Mock LLM service returned status {response.status_code}")
                    return False
            except Exception as e:
                print(f"❌ Mock LLM service not responding: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to start Mock LLM service: {e}")
            return False
    
    def test_llm_service_directly(self):
        """Test the LLM service directly"""
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
            test_request = {
                "model": "mock-llm:latest",
                "prompt": "Hello, this is a test.",
                "stream": False
            }
            
            response = requests.post(
                "http://localhost:11434/api/generate",
                json=test_request,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if "response" in data:
                    print(f"✅ LLM generate test passed: {data['response'][:50]}...")
                    self.test_results["llm_generate"] = "PASS"
                    return True
                else:
                    print("❌ LLM generate test failed: no response field")
                    self.test_results["llm_generate"] = "FAIL: No response field"
                    return False
            else:
                print(f"❌ LLM generate test failed: {response.status_code}")
                self.test_results["llm_generate"] = f"FAIL: HTTP {response.status_code}"
                return False
                
        except Exception as e:
            print(f"❌ LLM direct test failed: {e}")
            self.test_results["llm_direct_test"] = f"FAIL: {e}"
            return False
    
    def generate_test_audio(self, duration=2, sample_rate=16000):
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
        """Test the pipeline with focus on LLM service"""
        print("🔌 Testing pipeline with LLM focus...")
        
        try:
            # Connect to orchestrator
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
                
                # Monitor pipeline with LLM focus
                print("⏳ Monitoring pipeline with LLM focus...")
                start_time = time.time()
                llm_started = False
                llm_completed = False
                
                while time.time() - start_time < 60:
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        data = json.loads(response)
                        
                        print(f"📥 Received: {data}")
                        
                        # Track LLM service status
                        if data.get("type") == "service_status":
                            service = data.get('service', 'unknown')
                            state = data.get('state', 'unknown')
                            message = data.get('message', '')
                            
                            if service == "llm":
                                if state == "executing" and not llm_started:
                                    print("✅ LLM service started executing")
                                    llm_started = True
                                    self.test_results["llm_started"] = "PASS"
                                elif state == "complete":
                                    print("✅ LLM service completed!")
                                    llm_completed = True
                                    self.test_results["llm_completed"] = "PASS"
                                    break
                                elif state == "error":
                                    print(f"❌ LLM service error: {message}")
                                    self.test_results["llm_error"] = f"FAIL: {message}"
                                    break
                        
                        # Check for LLM response
                        elif data.get("event") == "llm_response_text":
                            print("✅ LLM response received!")
                            self.test_results["llm_response"] = "PASS"
                            llm_completed = True
                            break
                        
                        # Check for TTS audio
                        elif data.get("event") == "tts_audio_chunk":
                            print("✅ TTS audio received!")
                            self.test_results["tts_audio"] = "PASS"
                            break
                            
                    except asyncio.TimeoutError:
                        continue
                
                if not llm_completed:
                    print("❌ LLM service did not complete within timeout")
                    self.test_results["llm_timeout"] = "FAIL"
                
        except Exception as e:
            print(f"❌ Pipeline test failed: {e}")
            self.test_results["pipeline_test"] = f"FAIL: {e}"
    
    def cleanup(self):
        """Clean up the mock LLM service"""
        print("🛑 Cleaning up mock LLM service...")
        
        if self.mock_llm_process:
            try:
                self.mock_llm_process.terminate()
                self.mock_llm_process.wait(timeout=5)
                print("✅ Mock LLM service stopped")
            except subprocess.TimeoutExpired:
                self.mock_llm_process.kill()
                print("⚠️  Mock LLM service force killed")
            except Exception as e:
                print(f"❌ Error stopping Mock LLM service: {e}")
    
    def print_results(self):
        """Print test results"""
        print("\n" + "="*50)
        print("📊 LLM CONNECTION FIX TEST RESULTS")
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
            print("✅ LLM service connection issue resolved!")
        else:
            print(f"⚠️  {passed}/{total} tests passed")
            
        # Analysis
        print("\n🔍 ANALYSIS:")
        if "llm_completed" in self.test_results and self.test_results["llm_completed"] == "PASS":
            print("✅ SUCCESS: LLM service completed successfully!")
            print("   The local mock LLM service is working correctly.")
        elif "llm_response" in self.test_results and self.test_results["llm_response"] == "PASS":
            print("✅ SUCCESS: LLM response received!")
            print("   The pipeline is working with the local LLM service.")
        elif "llm_started" in self.test_results and self.test_results["llm_started"] == "PASS":
            print("⚠️  PARTIAL: LLM started but didn't complete")
            print("   The issue might be with the orchestrator's LLM service configuration.")
        else:
            print("❌ ISSUE: LLM service is not working")
            print("   Check the mock LLM service and orchestrator configuration.")

async def main():
    """Main function"""
    print("🚀 Starting LLM Connection Fix Test")
    print("="*50)
    
    test = LLMConnectionFixTest()
    
    try:
        # Setup
        test.setup_environment()
        
        # Start mock LLM service
        if not test.start_mock_llm_service():
            print("❌ Failed to start Mock LLM service")
            return
        
        # Test LLM service directly
        if not test.test_llm_service_directly():
            print("❌ LLM service direct test failed")
            return
        
        # Wait for service to be ready
        print("⏳ Waiting for service to be ready...")
        time.sleep(2)
        
        # Test pipeline
        await test.test_pipeline_with_llm_focus()
        
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