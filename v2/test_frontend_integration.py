#!/usr/bin/env python3
"""
Frontend Integration Test Script
Tests the complete frontend-backend integration flow
"""

import asyncio
import json
import websockets
import time
import requests
from datetime import datetime

async def test_frontend_integration():
    """Test the complete frontend-backend integration flow"""
    base_url = "https://dharsan99--voice-ai-backend-v2-run-app.modal.run"
    
    print("🧪 Testing Frontend-Backend Integration")
    print("=" * 60)
    
    # Step 1: Check backend health
    print("1. Checking backend health...")
    try:
        health_response = requests.get(f"{base_url}/health")
        health_response.raise_for_status()
        health_data = health_response.json()
        print(f"   ✅ Backend healthy: {health_data['status']}")
        print(f"   📋 Version: {health_data['version']}")
        print(f"   📊 Active sessions: {health_data['active_sessions']}")
    except Exception as e:
        print(f"   ❌ Backend health check failed: {e}")
        return
    
    # Step 2: Test session creation (simulating frontend V2 hook)
    print("\n2. Testing session creation (V2 hook simulation)...")
    try:
        session_response = requests.post(f"{base_url}/v2/sessions")
        session_response.raise_for_status()
        session_data = session_response.json()
        session_id = session_data["session_id"]
        print(f"   ✅ Session created: {session_id}")
        print(f"   📋 Session data: {session_data}")
    except Exception as e:
        print(f"   ❌ Session creation failed: {e}")
        return
    
    # Step 3: Test WebSocket connection (simulating frontend connection)
    print("\n3. Testing WebSocket connection (V2 hook simulation)...")
    ws_url = f"wss://dharsan99--voice-ai-backend-v2-run-app.modal.run/ws/v2/{session_id}"
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print(f"   ✅ WebSocket connected to: {ws_url}")
            
            # Step 4: Test message handling (simulating frontend message processing)
            print("\n4. Testing message handling...")
            
            # Send a test message
            test_message = {
                "type": "test",
                "data": "Frontend integration test",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(test_message))
            print(f"   📤 Sent test message: {test_message}")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"   📥 Received response: {response}")
                
                try:
                    response_data = json.loads(response)
                    print(f"   📋 Parsed response: {response_data}")
                    
                    # Check if it's a connection_established message
                    if response_data.get("type") == "connection_established":
                        print("   ✅ Connection established successfully")
                    else:
                        print("   ⚠️  Unexpected response type")
                        
                except json.JSONDecodeError:
                    print(f"   📋 Raw response: {response}")
                    
            except asyncio.TimeoutError:
                print("   ⏰ Timeout waiting for response")
            
            # Step 5: Test heartbeat (simulating frontend heartbeat)
            print("\n5. Testing heartbeat mechanism...")
            ping_message = {"type": "ping"}
            await websocket.send(json.dumps(ping_message))
            print(f"   📤 Sent ping")
            
            try:
                pong_response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                print(f"   📥 Received pong: {pong_response}")
                
                try:
                    pong_data = json.loads(pong_response)
                    if pong_data.get("type") == "pong":
                        print("   ✅ Heartbeat working correctly")
                    else:
                        print("   ⚠️  Unexpected pong response")
                except json.JSONDecodeError:
                    print("   ⚠️  Invalid pong response format")
                    
            except asyncio.TimeoutError:
                print("   ⏰ No pong response received")
            
            print("\n   ✅ Frontend integration test completed successfully!")
            
    except Exception as e:
        print(f"   ❌ WebSocket connection failed: {e}")
    
    # Step 6: Check final session status
    print("\n6. Checking final session status...")
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
            print(f"   📊 Messages received: {our_session.get('metrics', {}).get('messages_received', 0)}")
            print(f"   📊 Errors count: {our_session.get('metrics', {}).get('errors_count', 0)}")
        else:
            print(f"   ⚠️  Session not found in list")
            
    except Exception as e:
        print(f"   ❌ Failed to check session status: {e}")

async def main():
    """Main test function"""
    print("🚀 Starting Frontend Integration Tests")
    print("=" * 70)
    
    await test_frontend_integration()
    
    print("\n" + "=" * 70)
    print("🏁 Frontend Integration Tests Completed")

if __name__ == "__main__":
    asyncio.run(main()) 