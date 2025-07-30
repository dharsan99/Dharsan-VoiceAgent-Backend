#!/usr/bin/env python3
"""
Test Pipeline with Mock LLM Service
This script starts the mock LLM service locally and tests the full pipeline.
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

class MockLLMPipelineTest:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.v2_dir = self.project_root / "v2"
        self.mock_llm_process = None
        self.test_results = {}
        
    def setup_environment(self):
        """Set up environment variables for local LLM service"""
        print("🔧 Setting up environment for local LLM service...")
        
        # Set LLM service URL to localhost
        os.environ["LLM_SERVICE_URL"] = "http://localhost:11434"
        
        # Keep other services as they are (they might work or we'll test them)
        print(f"✅ LLM_SERVICE_URL set to: {os.environ['LLM_SERVICE_URL']}")
        
    def start_mock_llm_service(self):
        """Start the mock LLM service locally"""
        print("🚀 Starting Mock LLM service...")
        
        try:
            llm_dir = self.v2_dir / "llm-service"
            self.mock_llm_process = subprocess.Popen([
                sys.executable, "mock_llm_simple.py"
            ], cwd=llm_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for service to start
            time.sleep(3)
            
            # Test if service is responding
            import requests
            try:
                response = requests.get("http://localhost:11434/health", timeout=5)
                if response.status_code == 200:
                    print("✅ Mock LLM service started and responding")
                    self.test_results["mock_llm_started"] = "PASS"
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
    
    def generate_test_audio(self, duration=2, sample_rate=16000):
        """Generate a simple test audio tone"""
        print(f"🎵 Generating {duration}s test audio...")
        
        # Generate a 440Hz sine wave
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio = np.sin(2 * np.pi * 440 * t) * 0.3
        
        # Convert to 16-bit PCM
        audio_int16 = (audio * 32767).astype(np.int16)
        
        # Create WAV file
        wav_path = self.project_root / "test_audio_mock.wav"
        with wave.open(str(wav_path), 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        
        print(f"✅ Test audio generated: {wav_path}")
        return wav_path
    
    async def test_websocket_connection(self):
        """Test the WebSocket connection to the orchestrator"""
        print("🔌 Testing WebSocket connection with local LLM service...")
        
        try:
            # Connect to the orchestrator
            uri = "ws://34.47.230.178:8001/ws"
            print(f"🔗 Connecting to: {uri}")
            
            async with websockets.connect(uri) as websocket:
                print("✅ WebSocket connected successfully")
                self.test_results["connection"] = "PASS"
                
                # Send greeting request
                session_id = f"mock_test_session_{int(time.time())}"
                greeting_msg = {
                    "event": "greeting_request",
                    "session_id": session_id
                }
                await websocket.send(json.dumps(greeting_msg))
                print("📤 Sent greeting request")
                
                # Wait for greeting response
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                print(f"📥 Received greeting: {data}")
                
                if data.get("event") == "greeting":
                    print("✅ Greeting received successfully")
                    self.test_results["greeting"] = "PASS"
                else:
                    print("❌ Unexpected greeting response")
                    self.test_results["greeting"] = "FAIL"
                
                # Test start listening
                start_msg = {
                    "event": "start_listening",
                    "session_id": session_id
                }
                await websocket.send(json.dumps(start_msg))
                print("📤 Sent start listening request")
                
                # Wait for listening confirmation
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                print(f"📥 Received listening response: {data}")
                
                if data.get("type") == "pipeline_state_update" and data.get("state") == "listening":
                    print("✅ Listening started successfully")
                    self.test_results["listening"] = "PASS"
                else:
                    print("❌ Unexpected listening response")
                    self.test_results["listening"] = "FAIL"
                
                # Test audio data sending
                print("🎵 Preparing to send audio data...")
                wav_path = self.generate_test_audio()
                with open(wav_path, 'rb') as f:
                    audio_data = f.read()
                
                # Convert to base64
                audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                print(f"📊 Audio data size: {len(audio_data)} bytes, base64: {len(audio_b64)} chars")
                
                audio_msg = {
                    "event": "audio_data",
                    "session_id": session_id,
                    "audio_data": audio_b64,
                    "is_final": True
                }
                await websocket.send(json.dumps(audio_msg))
                print("📤 Sent audio data")
                self.test_results["audio_sent"] = "PASS"
                
                # Wait for pipeline processing with detailed logging
                print("⏳ Waiting for pipeline processing with local LLM...")
                start_time = time.time()
                message_count = 0
                
                while time.time() - start_time < 60:  # Wait up to 60 seconds
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                        message_count += 1
                        data = json.loads(response)
                        
                        print(f"📥 Message #{message_count} ({time.time() - start_time:.1f}s): {data}")
                        
                        # Check for various response types
                        if data.get("event") == "llm_response_text":
                            print("✅ LLM response received!")
                            self.test_results["llm_response"] = "PASS"
                            break
                        elif data.get("event") == "tts_audio_chunk":
                            print("✅ TTS audio chunk received!")
                            self.test_results["tts_audio"] = "PASS"
                            break
                        elif data.get("type") == "pipeline_state_update":
                            state = data.get('state', 'unknown')
                            print(f"🔄 Pipeline state update: {state}")
                            if state == "processing":
                                self.test_results["processing_state"] = "PASS"
                            elif state == "complete":
                                print("✅ Pipeline completed!")
                                self.test_results["pipeline_complete"] = "PASS"
                                break
                        elif data.get("type") == "service_status":
                            service = data.get('service', 'unknown')
                            service_state = data.get('state', 'unknown')
                            message = data.get('message', '')
                            print(f"🔧 Service status - {service}: {service_state} - {message}")
                            
                            if service == "llm" and service_state == "complete":
                                print("✅ LLM service completed!")
                                self.test_results["llm_service_complete"] = "PASS"
                            elif service == "llm" and service_state == "error":
                                print("❌ LLM service error!")
                                self.test_results["llm_service_error"] = f"FAIL: {message}"
                                break
                        elif data.get("type") == "info":
                            message = data.get('message', '')
                            print(f"ℹ️  Info message: {message}")
                            if "transcription" in message.lower():
                                self.test_results["transcription_info"] = "PASS"
                        elif data.get("type") == "error":
                            error_msg = data.get('message', '')
                            print(f"❌ Error received: {error_msg}")
                            self.test_results["error"] = f"FAIL: {error_msg}"
                            break
                        else:
                            print(f"📝 Other message type: {data.get('type', 'unknown')}")
                            
                    except asyncio.TimeoutError:
                        print(f"⏳ Timeout waiting for response ({time.time() - start_time:.1f}s elapsed)")
                        continue
                
                if time.time() - start_time >= 60:
                    print("❌ Timeout waiting for pipeline response (60 seconds)")
                    self.test_results["pipeline_timeout"] = "FAIL"
                
                print(f"📊 Total messages received: {message_count}")
                
        except Exception as e:
            print(f"❌ WebSocket test failed: {e}")
            import traceback
            traceback.print_exc()
            self.test_results["websocket"] = f"FAIL: {e}"
    
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
        print("📊 MOCK LLM PIPELINE TEST RESULTS")
        print("="*50)
        
        for test_name, result in self.test_results.items():
            if result.startswith("PASS"):
                print(f"{test_name:25} ✅ PASS")
            else:
                print(f"{test_name:25} ❌ {result}")
        
        print("="*50)
        
        # Overall result
        passed = sum(1 for result in self.test_results.values() if result.startswith("PASS"))
        total = len(self.test_results)
        
        if passed == total:
            print("🎉 ALL TESTS PASSED!")
        else:
            print(f"⚠️  {passed}/{total} tests passed")
            
        # Analysis
        print("\n🔍 ANALYSIS:")
        if "llm_response" in self.test_results and self.test_results["llm_response"] == "PASS":
            print("✅ SUCCESS: LLM service connection issue resolved!")
            print("   The problem was that the orchestrator couldn't connect to the LLM service.")
            print("   Using a local mock LLM service fixed the issue.")
        elif "llm_service_error" in self.test_results:
            print("❌ LLM service error - there might be other issues")
        elif "pipeline_timeout" in self.test_results:
            print("❌ Pipeline timeout - LLM service might not be responding correctly")
        else:
            print("⚠️  Partial success - some components working")

async def main():
    """Main function"""
    print("🚀 Starting Mock LLM Pipeline Test")
    print("="*50)
    
    test = MockLLMPipelineTest()
    
    try:
        # Setup
        test.setup_environment()
        
        # Start mock LLM service
        if not test.start_mock_llm_service():
            print("❌ Failed to start Mock LLM service")
            return
        
        # Wait a moment for service to be ready
        time.sleep(2)
        
        # Run WebSocket test
        await test.test_websocket_connection()
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        test.cleanup()
        test.print_results()

if __name__ == "__main__":
    asyncio.run(main()) 