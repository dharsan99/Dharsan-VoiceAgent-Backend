#!/usr/bin/env python3
"""
Voice Agent Pipeline Analysis and Test
This script analyzes the voice agent pipeline issue and provides solutions.
"""

import asyncio
import json
import time
import base64
import wave
import numpy as np
import websockets
import requests
from pathlib import Path

class VoiceAgentPipelineAnalysis:
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
        wav_path = Path("test_audio_analysis.wav")
        with wave.open(str(wav_path), 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        
        print(f"✅ Test audio generated: {wav_path}")
        return wav_path
    
    def test_service_connectivity(self):
        """Test connectivity to various services"""
        print("🔍 Testing service connectivity...")
        
        services = {
            "orchestrator": "http://34.47.230.178:8001/health",
            "stt_service": "http://stt-service.voice-agent-phase5.svc.cluster.local:8000/health",
            "llm_service": "http://llm-service.voice-agent-phase5.svc.cluster.local:11434/health",
            "tts_service": "http://tts-service.voice-agent-phase5.svc.cluster.local:5000/health",
        }
        
        for service_name, url in services.items():
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    print(f"✅ {service_name}: Accessible")
                    self.test_results[f"{service_name}_accessible"] = "PASS"
                else:
                    print(f"❌ {service_name}: HTTP {response.status_code}")
                    self.test_results[f"{service_name}_accessible"] = f"FAIL: HTTP {response.status_code}"
            except Exception as e:
                print(f"❌ {service_name}: {e}")
                self.test_results[f"{service_name}_accessible"] = f"FAIL: {e}"
    
    async def test_pipeline_step_by_step(self):
        """Test the pipeline step by step to identify the exact failure point"""
        print("🔌 Testing pipeline step by step...")
        
        try:
            # Connect to orchestrator
            uri = "ws://34.47.230.178:8001/ws"
            print(f"🔗 Connecting to: {uri}")
            
            async with websockets.connect(uri) as websocket:
                print("✅ WebSocket connected successfully")
                self.test_results["websocket_connection"] = "PASS"
                
                # Step 1: Greeting
                session_id = f"analysis_session_{int(time.time())}"
                greeting_msg = {
                    "event": "greeting_request",
                    "session_id": session_id
                }
                await websocket.send(json.dumps(greeting_msg))
                print("📤 Step 1: Sent greeting request")
                
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                if data.get("event") == "greeting":
                    print("✅ Step 1: Greeting successful")
                    self.test_results["step1_greeting"] = "PASS"
                else:
                    print("❌ Step 1: Greeting failed")
                    self.test_results["step1_greeting"] = "FAIL"
                
                # Step 2: Start listening
                start_msg = {
                    "event": "start_listening",
                    "session_id": session_id
                }
                await websocket.send(json.dumps(start_msg))
                print("📤 Step 2: Sent start listening request")
                
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                if data.get("type") == "pipeline_state_update" and data.get("state") == "listening":
                    print("✅ Step 2: Listening started successfully")
                    self.test_results["step2_listening"] = "PASS"
                else:
                    print("❌ Step 2: Listening failed")
                    self.test_results["step2_listening"] = "FAIL"
                
                # Step 3: Send audio data
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
                print("📤 Step 3: Sent audio data")
                self.test_results["step3_audio_sent"] = "PASS"
                
                # Step 4: Monitor pipeline processing
                print("📤 Step 4: Monitoring pipeline processing...")
                start_time = time.time()
                step4_success = False
                
                while time.time() - start_time < 30:  # Wait up to 30 seconds
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        data = json.loads(response)
                        
                        # Check for STT completion
                        if (data.get("type") == "service_status" and 
                            data.get("service") == "stt" and 
                            data.get("state") == "complete"):
                            print("✅ Step 4a: STT completed successfully")
                            self.test_results["step4a_stt_complete"] = "PASS"
                        
                        # Check for LLM start
                        elif (data.get("type") == "service_status" and 
                              data.get("service") == "llm" and 
                              data.get("state") == "executing"):
                            print("✅ Step 4b: LLM started executing")
                            self.test_results["step4b_llm_started"] = "PASS"
                        
                        # Check for LLM completion
                        elif (data.get("type") == "service_status" and 
                              data.get("service") == "llm" and 
                              data.get("state") == "complete"):
                            print("✅ Step 4c: LLM completed successfully")
                            self.test_results["step4c_llm_complete"] = "PASS"
                            step4_success = True
                            break
                        
                        # Check for LLM error
                        elif (data.get("type") == "service_status" and 
                              data.get("service") == "llm" and 
                              data.get("state") == "error"):
                            print("❌ Step 4c: LLM failed")
                            self.test_results["step4c_llm_complete"] = f"FAIL: {data.get('message', 'Unknown error')}"
                            break
                        
                        # Check for LLM response
                        elif data.get("event") == "llm_response_text":
                            print("✅ Step 4d: LLM response received")
                            self.test_results["step4d_llm_response"] = "PASS"
                            step4_success = True
                            break
                            
                    except asyncio.TimeoutError:
                        continue
                
                if not step4_success:
                    print("❌ Step 4: Pipeline processing failed or timed out")
                    self.test_results["step4_pipeline"] = "FAIL: Timeout"
                
        except Exception as e:
            print(f"❌ Pipeline test failed: {e}")
            self.test_results["pipeline_test"] = f"FAIL: {e}"
    
    def print_analysis(self):
        """Print comprehensive analysis"""
        print("\n" + "="*60)
        print("🔍 VOICE AGENT PIPELINE ANALYSIS")
        print("="*60)
        
        # Test results
        print("\n📊 TEST RESULTS:")
        for test_name, result in self.test_results.items():
            if result.startswith("PASS"):
                print(f"  {test_name:30} ✅ PASS")
            else:
                print(f"  {test_name:30} ❌ {result}")
        
        # Analysis
        print("\n🔍 ROOT CAUSE ANALYSIS:")
        
        # Check service connectivity
        orchestrator_ok = self.test_results.get("orchestrator_accessible", "").startswith("PASS")
        stt_ok = self.test_results.get("stt_service_accessible", "").startswith("PASS")
        llm_ok = self.test_results.get("llm_service_accessible", "").startswith("PASS")
        tts_ok = self.test_results.get("tts_service_accessible", "").startswith("PASS")
        
        if not orchestrator_ok:
            print("❌ Orchestrator service is not accessible")
            print("   - The orchestrator at 34.47.230.178:8001 is not responding")
            print("   - This could be a network issue or the service is down")
        elif not stt_ok:
            print("❌ STT service is not accessible")
            print("   - The STT service at stt-service.voice-agent-phase5.svc.cluster.local:8000 is not reachable")
            print("   - This is a Kubernetes service that's not accessible from outside the cluster")
        elif not llm_ok:
            print("❌ LLM service is not accessible")
            print("   - The LLM service at llm-service.voice-agent-phase5.svc.cluster.local:11434 is not reachable")
            print("   - This is a Kubernetes service that's not accessible from outside the cluster")
        elif not tts_ok:
            print("❌ TTS service is not accessible")
            print("   - The TTS service at tts-service.voice-agent-phase5.svc.cluster.local:5000 is not reachable")
            print("   - This is a Kubernetes service that's not accessible from outside the cluster")
        else:
            print("✅ All services are accessible")
        
        # Check pipeline steps
        step1_ok = self.test_results.get("step1_greeting", "").startswith("PASS")
        step2_ok = self.test_results.get("step2_listening", "").startswith("PASS")
        step3_ok = self.test_results.get("step3_audio_sent", "").startswith("PASS")
        step4a_ok = self.test_results.get("step4a_stt_complete", "").startswith("PASS")
        step4b_ok = self.test_results.get("step4b_llm_started", "").startswith("PASS")
        step4c_ok = self.test_results.get("step4c_llm_complete", "").startswith("PASS")
        
        print("\n🔧 PIPELINE STEP ANALYSIS:")
        if step1_ok and step2_ok and step3_ok and step4a_ok and step4b_ok and not step4c_ok:
            print("❌ ISSUE IDENTIFIED: LLM service is not completing")
            print("   - STT works fine")
            print("   - LLM starts but never completes")
            print("   - This confirms the LLM service connectivity issue")
        elif step1_ok and step2_ok and step3_ok and not step4a_ok:
            print("❌ ISSUE IDENTIFIED: STT service is not working")
            print("   - Audio is sent but STT never completes")
        elif step1_ok and step2_ok and not step3_ok:
            print("❌ ISSUE IDENTIFIED: Audio sending is not working")
        elif step1_ok and not step2_ok:
            print("❌ ISSUE IDENTIFIED: Listening setup is not working")
        elif not step1_ok:
            print("❌ ISSUE IDENTIFIED: Basic WebSocket communication is not working")
        else:
            print("✅ All pipeline steps are working")
        
        # Solutions
        print("\n💡 SOLUTIONS:")
        print("1. LOCAL TESTING:")
        print("   - Run the services locally using docker-compose or individual service scripts")
        print("   - Use the test_full_pipeline_local.py script")
        print("   - This bypasses Kubernetes networking issues")
        
        print("\n2. KUBERNETES ACCESS:")
        print("   - Set up kubectl port-forwarding to access services:")
        print("     kubectl port-forward svc/stt-service 8000:8000")
        print("     kubectl port-forward svc/llm-service 11434:11434")
        print("     kubectl port-forward svc/tts-service 5000:5000")
        
        print("\n3. SERVICE CONFIGURATION:")
        print("   - Update orchestrator to use localhost URLs when running locally")
        print("   - Add environment variable overrides for local development")
        
        print("\n4. MOCK SERVICES:")
        print("   - Use mock services for testing (already available)")
        print("   - Run mock_llm_simple.py, mock_stt_service.py, etc.")
        
        # Overall assessment
        print("\n📋 OVERALL ASSESSMENT:")
        if step4c_ok:
            print("🎉 FULL PIPELINE IS WORKING!")
        elif step4a_ok and step4b_ok:
            print("⚠️  PARTIAL SUCCESS: STT works, LLM starts but doesn't complete")
            print("   - This is likely a service connectivity issue")
        elif step3_ok:
            print("⚠️  PARTIAL SUCCESS: Audio sending works, but processing fails")
        else:
            print("❌ MAJOR ISSUES: Basic communication is not working")

async def main():
    """Main function"""
    print("🚀 Starting Voice Agent Pipeline Analysis")
    print("="*60)
    
    analysis = VoiceAgentPipelineAnalysis()
    
    # Test service connectivity
    analysis.test_service_connectivity()
    
    # Test pipeline step by step
    await analysis.test_pipeline_step_by_step()
    
    # Print comprehensive analysis
    analysis.print_analysis()

if __name__ == "__main__":
    asyncio.run(main()) 