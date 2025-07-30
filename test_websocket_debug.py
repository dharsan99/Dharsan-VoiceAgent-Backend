#!/usr/bin/env python3
"""
WebSocket Debug Test
This script tests the WebSocket connection to the existing orchestrator
and identifies where the pipeline is getting stuck.
"""

import asyncio
import json
import time
import base64
import wave
import numpy as np
import websockets
from pathlib import Path

class WebSocketDebugTest:
    def __init__(self):
        self.test_results = {}
        
    def generate_test_audio(self, duration=2, sample_rate=16000):
        """Generate a simple test audio tone"""
        print(f"🎵 Generating {duration}s test audio...")
        
        # Generate a 440Hz sine wave
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio = np.sin(2 * np.pi * 440 * t) * 0.3
        
        # Convert to 16-bit PCM
        audio_int16 = (audio * 32767).astype(np.int16)
        
        # Create WAV file
        wav_path = Path("test_audio_debug.wav")
        with wave.open(str(wav_path), 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        
        print(f"✅ Test audio generated: {wav_path}")
        return wav_path
    
    async def test_websocket_connection(self):
        """Test the WebSocket connection to the orchestrator"""
        print("🔌 Testing WebSocket connection to orchestrator...")
        
        try:
            # Connect to the orchestrator
            uri = "ws://34.47.230.178:8001/ws"
            print(f"🔗 Connecting to: {uri}")
            
            async with websockets.connect(uri) as websocket:
                print("✅ WebSocket connected successfully")
                self.test_results["connection"] = "PASS"
                
                # Send greeting request
                session_id = f"debug_session_{int(time.time())}"
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
                
                if data.get("event") == "listening_started":
                    print("✅ Listening started successfully")
                    self.test_results["listening"] = "PASS"
                else:
                    print("❌ Unexpected listening response")
                    self.test_results["listening"] = "FAIL"
                
                # Wait for pipeline state update
                print("⏳ Waiting for pipeline state update...")
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                print(f"📥 Received state update: {data}")
                
                if data.get("type") == "pipeline_state_update":
                    print(f"✅ Pipeline state: {data.get('state', 'unknown')}")
                    self.test_results["state_update"] = "PASS"
                else:
                    print("❌ Unexpected state update response")
                    self.test_results["state_update"] = "FAIL"
                
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
                print("⏳ Waiting for pipeline processing...")
                start_time = time.time()
                message_count = 0
                
                while time.time() - start_time < 120:  # Wait up to 2 minutes
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
                
                if time.time() - start_time >= 120:
                    print("❌ Timeout waiting for pipeline response (2 minutes)")
                    self.test_results["pipeline_timeout"] = "FAIL"
                
                print(f"📊 Total messages received: {message_count}")
                
        except Exception as e:
            print(f"❌ WebSocket test failed: {e}")
            import traceback
            traceback.print_exc()
            self.test_results["websocket"] = f"FAIL: {e}"
    
    def print_results(self):
        """Print test results"""
        print("\n" + "="*50)
        print("📊 DEBUG TEST RESULTS")
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
        if "pipeline_timeout" in self.test_results:
            print("❌ Pipeline timeout - The orchestrator is not processing audio data")
            print("   Possible causes:")
            print("   - STT service is not responding")
            print("   - LLM service is not responding") 
            print("   - TTS service is not responding")
            print("   - Internal service communication issues")
        elif "error" in self.test_results:
            print("❌ Error received from orchestrator")
        elif "llm_response" in self.test_results and self.test_results["llm_response"] == "PASS":
            print("✅ Full pipeline working - LLM response received")
        elif "tts_audio" in self.test_results and self.test_results["tts_audio"] == "PASS":
            print("✅ Full pipeline working - TTS audio received")
        else:
            print("⚠️  Partial pipeline working - some components may be failing")

async def main():
    """Main function"""
    print("🚀 Starting WebSocket Debug Test")
    print("="*50)
    
    test = WebSocketDebugTest()
    await test.test_websocket_connection()
    test.print_results()

if __name__ == "__main__":
    asyncio.run(main()) 