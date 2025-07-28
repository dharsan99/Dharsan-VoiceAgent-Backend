#!/usr/bin/env python3
"""
WebSocket Test Script for Voice AI Backend v2
Tests the improved WebSocket connection handling
"""

import asyncio
import json
import websockets
import time
from datetime import datetime

async def test_websocket_connection():
    """Test WebSocket connection to the backend"""
    uri = "wss://dharsan99--voice-ai-backend-v2-run-app.modal.run/ws/test"
    
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connection established")
            
            # Wait for initial message
            initial_message = await websocket.recv()
            print(f"📨 Initial message: {initial_message}")
            
            # Send a test message
            test_message = {
                "type": "test",
                "message": "Hello from test client",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            print(f"📤 Sending test message: {json.dumps(test_message)}")
            await websocket.send(json.dumps(test_message))
            
            # Wait for echo response
            echo_response = await websocket.recv()
            print(f"📨 Echo response: {echo_response}")
            
            # Send another message
            test_message2 = {
                "type": "ping",
                "message": "Ping test",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            print(f"📤 Sending ping message: {json.dumps(test_message2)}")
            await websocket.send(json.dumps(test_message2))
            
            # Wait for response
            ping_response = await websocket.recv()
            print(f"📨 Ping response: {ping_response}")
            
            print("✅ WebSocket test completed successfully")
            
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ WebSocket connection closed: {e}")
    except Exception as e:
        print(f"❌ Error during WebSocket test: {e}")

async def test_webrtc_signaling():
    """Test WebRTC signaling endpoint"""
    # First create a session
    import requests
    
    session_url = "https://dharsan99--voice-ai-backend-v2-run-app.modal.run/v2/sessions"
    print(f"Creating session at {session_url}...")
    
    try:
        response = requests.post(session_url)
        response.raise_for_status()
        session_data = response.json()
        session_id = session_data["session_id"]
        print(f"✅ Session created: {session_id}")
        
        # Test WebRTC signaling WebSocket
        signaling_uri = f"wss://dharsan99--voice-ai-backend-v2-run-app.modal.run/ws/v2/{session_id}"
        print(f"Connecting to signaling endpoint: {signaling_uri}")
        
        async with websockets.connect(signaling_uri) as websocket:
            print("✅ WebRTC signaling connection established")
            
            # Wait for connection confirmation
            connection_msg = await websocket.recv()
            print(f"📨 Connection message: {connection_msg}")
            
            # Send a ping message
            ping_msg = {"type": "ping"}
            print(f"📤 Sending ping: {json.dumps(ping_msg)}")
            await websocket.send(json.dumps(ping_msg))
            
            # Wait for pong response
            pong_response = await websocket.recv()
            print(f"📨 Pong response: {pong_response}")
            
            print("✅ WebRTC signaling test completed successfully")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error creating session: {e}")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ WebSocket connection closed: {e}")
    except Exception as e:
        print(f"❌ Error during WebRTC signaling test: {e}")

async def main():
    """Run all tests"""
    print("🚀 Starting WebSocket Tests for Voice AI Backend v2")
    print("=" * 60)
    
    # Test 1: Basic WebSocket connection
    print("\n📋 Test 1: Basic WebSocket Connection")
    print("-" * 40)
    await test_websocket_connection()
    
    # Test 2: WebRTC signaling
    print("\n📋 Test 2: WebRTC Signaling")
    print("-" * 40)
    await test_webrtc_signaling()
    
    print("\n🎉 All tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 