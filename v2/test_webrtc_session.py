#!/usr/bin/env python3
"""
WebRTC Session Test Script
Tests the session-based WebRTC connection flow
"""

import asyncio
import json
import websockets
import time
import requests
from datetime import datetime

async def test_webrtc_session_flow():
    """Test the complete WebRTC session flow"""
    base_url = "https://dharsan99--voice-ai-backend-v2-run-app.modal.run"
    
    print("🧪 Testing WebRTC Session Flow")
    print("=" * 50)
    
    # Step 1: Create session via HTTP
    print("1. Creating session via HTTP...")
    try:
        session_response = requests.post(f"{base_url}/v2/sessions")
        session_response.raise_for_status()
        session_data = session_response.json()
        session_id = session_data["session_id"]
        print(f"   ✅ Session created: {session_id}")
        print(f"   📋 Session data: {session_data}")
    except Exception as e:
        print(f"   ❌ Failed to create session: {e}")
        return
    
    # Step 2: Connect to WebSocket signaling
    print("\n2. Connecting to WebSocket signaling...")
    ws_url = f"wss://dharsan99--voice-ai-backend-v2-run-app.modal.run/ws/v2/{session_id}"
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print(f"   ✅ WebSocket connected to: {ws_url}")
            
            # Step 3: Send test signaling message
            print("\n3. Sending test signaling message...")
            test_message = {
                "type": "test",
                "data": "WebRTC session test",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(test_message))
            print(f"   📤 Sent: {test_message}")
            
            # Step 4: Wait for response
            print("\n4. Waiting for response...")
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"   📥 Received: {response}")
                
                # Parse response
                try:
                    response_data = json.loads(response)
                    print(f"   📋 Parsed response: {response_data}")
                except json.JSONDecodeError:
                    print(f"   📋 Raw response: {response}")
                    
            except asyncio.TimeoutError:
                print("   ⏰ Timeout waiting for response")
            
            # Step 5: Send ping to test heartbeat
            print("\n5. Testing heartbeat...")
            ping_message = {"type": "ping"}
            await websocket.send(json.dumps(ping_message))
            print(f"   📤 Sent ping")
            
            try:
                pong_response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                print(f"   📥 Received pong: {pong_response}")
            except asyncio.TimeoutError:
                print("   ⏰ No pong response received")
            
            print("\n   ✅ WebRTC session test completed successfully!")
            
    except Exception as e:
        print(f"   ❌ WebSocket connection failed: {e}")
    
    # Step 6: Check session status
    print("\n6. Checking session status...")
    try:
        sessions_response = requests.get(f"{base_url}/v2/sessions")
        sessions_response.raise_for_status()
        sessions_data = sessions_response.json()
        sessions = sessions_data.get("sessions", [])
        
        # Find our session
        our_session = None
        for session in sessions:
            if isinstance(session, dict) and session.get("id") == session_id:
                our_session = session
                break
        
        if our_session:
            print(f"   ✅ Session found in list")
            print(f"   📋 Session status: {our_session}")
        else:
            print(f"   ⚠️  Session not found in list")
            
    except Exception as e:
        print(f"   ❌ Failed to check session status: {e}")

async def main():
    """Main test function"""
    print("🚀 Starting WebRTC Session Tests")
    print("=" * 60)
    
    await test_webrtc_session_flow()
    
    print("\n" + "=" * 60)
    print("🏁 WebRTC Session Tests Completed")

if __name__ == "__main__":
    asyncio.run(main()) 