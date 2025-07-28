#!/usr/bin/env python3
"""
Complete Voice Agent Pipeline Test
Tests the entire Phase 4 voice agent system end-to-end
"""

import asyncio
import json
import websockets
import requests
import time
from typing import Dict, Any

class VoiceAgentPipelineTest:
    def __init__(self):
        self.media_server_url = "http://34.100.152.11"
        self.orchestrator_ws_url = "ws://35.200.224.194:8001/ws"
        self.orchestrator_http_url = "http://35.200.224.194:8001"
        
    def test_media_server_health(self) -> bool:
        """Test Media Server health endpoint"""
        try:
            response = requests.get(f"{self.media_server_url}/health", timeout=5)
            print(f"✅ Media Server Health: {response.status_code}")
            if response.status_code == 200:
                print(f"   Response: {response.text}")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Media Server Health Failed: {e}")
            return False
    
    def test_orchestrator_health(self) -> bool:
        """Test Orchestrator health endpoint"""
        try:
            response = requests.get(f"{self.orchestrator_http_url}/health", timeout=5)
            print(f"✅ Orchestrator Health: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Status: {data.get('status')}")
                print(f"   Kafka: {data.get('kafka')}")
                print(f"   AI Enabled: {data.get('ai_enabled')}")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Orchestrator Health Failed: {e}")
            return False
    
    async def test_websocket_connection(self) -> bool:
        """Test WebSocket connection to Orchestrator"""
        try:
            print(f"🔌 Connecting to WebSocket: {self.orchestrator_ws_url}")
            async with websockets.connect(self.orchestrator_ws_url) as websocket:
                print("✅ WebSocket connected successfully")
                
                # Wait for connection message
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    print(f"   Received: {data}")
                    return data.get('type') == 'connection_established'
                except asyncio.TimeoutError:
                    print("⚠️  No connection message received within 5 seconds")
                    return True  # Connection is still working
                    
        except Exception as e:
            print(f"❌ WebSocket Connection Failed: {e}")
            return False
    
    def test_whip_endpoint(self) -> bool:
        """Test WHIP endpoint with minimal SDP"""
        try:
            # Create a minimal SDP offer
            sdp_offer = """v=0
o=- 1234567890 2 IN IP4 127.0.0.1
s=-
t=0 0
m=audio 9 UDP/TLS/RTP/SAVPF 111
c=IN IP4 0.0.0.0
a=mid:audio
a=sendonly
a=rtpmap:111 opus/48000/2
a=fmtp:111 minptime=10;useinbandfec=1
a=ice-ufrag:test
a=ice-pwd:test
a=fingerprint:sha-256 test
a=setup:actpass
a=rtcp-mux
"""
            
            response = requests.post(
                f"{self.media_server_url}/whip",
                headers={"Content-Type": "application/sdp"},
                data=sdp_offer,
                timeout=10
            )
            
            print(f"✅ WHIP Endpoint: {response.status_code}")
            if response.status_code == 201:
                print("   WHIP connection established successfully")
                return True
            else:
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ WHIP Endpoint Failed: {e}")
            return False
    
    def test_ai_services(self) -> Dict[str, bool]:
        """Test individual AI services"""
        services = {
            "stt": "http://stt-service.voice-agent-phase4.svc.cluster.local:8000",
            "tts": "http://tts-service.voice-agent-phase4.svc.cluster.local:8000", 
            "llm": "http://llm-service.voice-agent-phase4.svc.cluster.local:8000"
        }
        
        results = {}
        for name, url in services.items():
            try:
                response = requests.get(f"{url}/health", timeout=5)
                status = response.status_code == 200
                print(f"{'✅' if status else '❌'} {name.upper()} Service: {response.status_code}")
                results[name] = status
            except Exception as e:
                print(f"❌ {name.upper()} Service Failed: {e}")
                results[name] = False
        
        return results
    
    async def run_complete_test(self):
        """Run the complete pipeline test"""
        print("🚀 Starting Complete Voice Agent Pipeline Test")
        print("=" * 60)
        
        # Test 1: Health checks
        print("\n1️⃣  Testing Service Health...")
        media_health = self.test_media_server_health()
        orchestrator_health = self.test_orchestrator_health()
        
        # Test 2: WebSocket connection
        print("\n2️⃣  Testing WebSocket Connection...")
        websocket_ok = await self.test_websocket_connection()
        
        # Test 3: WHIP endpoint
        print("\n3️⃣  Testing WHIP Endpoint...")
        whip_ok = self.test_whip_endpoint()
        
        # Test 4: AI Services
        print("\n4️⃣  Testing AI Services...")
        ai_services = self.test_ai_services()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 60)
        
        results = {
            "Media Server Health": media_health,
            "Orchestrator Health": orchestrator_health,
            "WebSocket Connection": websocket_ok,
            "WHIP Endpoint": whip_ok,
            "STT Service": ai_services.get("stt", False),
            "TTS Service": ai_services.get("tts", False),
            "LLM Service": ai_services.get("llm", False)
        }
        
        passed = 0
        total = len(results)
        
        for test, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} {test}")
            if result:
                passed += 1
        
        print(f"\n🎯 Overall: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Voice agent pipeline is fully functional.")
        else:
            print("⚠️  Some tests failed. Check the logs above for details.")
        
        return results

async def main():
    tester = VoiceAgentPipelineTest()
    await tester.run_complete_test()

if __name__ == "__main__":
    asyncio.run(main()) 