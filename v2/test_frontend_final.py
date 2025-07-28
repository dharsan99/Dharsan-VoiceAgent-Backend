#!/usr/bin/env python3
"""
Final Frontend Integration Test
Tests both v1 and v2 backends to ensure frontend can connect to both
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

# Backend URLs
V1_BACKEND_URL = "https://dharsan99--voice-ai-backend-run-app.modal.run"
V2_BACKEND_URL = "https://dharsan99--voice-ai-backend-v2-run-app.modal.run"

async def test_backend_health(url, name):
    """Test backend health endpoint"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ {name} Backend Healthy: {data['status']}")
                    return True
                else:
                    print(f"❌ {name} Backend Health Check Failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ {name} Backend Health Check Error: {e}")
        return False

async def test_v1_websocket():
    """Test v1 WebSocket connection"""
    try:
        import websockets
        uri = "wss://dharsan99--voice-ai-backend-run-app.modal.run/ws"
        
        async with websockets.connect(uri) as websocket:
            # Send a test message
            test_message = {
                "type": "test",
                "data": "Frontend integration test",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(test_message))
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            
            print(f"✅ V1 WebSocket Test: {data}")
            return True
            
    except Exception as e:
        print(f"❌ V1 WebSocket Test Failed: {e}")
        return False

async def test_v2_session_creation():
    """Test v2 session creation and WebSocket"""
    try:
        import websockets
        
        # Create session
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{V2_BACKEND_URL}/v2/sessions") as response:
                if response.status == 200:
                    session_data = await response.json()
                    session_id = session_data['session_id']
                    print(f"✅ V2 Session Created: {session_id}")
                    
                    # Test WebSocket connection
                    uri = f"wss://dharsan99--voice-ai-backend-v2-run-app.modal.run/ws/v2/{session_id}"
                    async with websockets.connect(uri) as websocket:
                        # Send test message
                        test_message = {
                            "type": "test",
                            "data": "Frontend integration test",
                            "timestamp": datetime.now().isoformat()
                        }
                        await websocket.send(json.dumps(test_message))
                        
                        # Wait for response
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        data = json.loads(response)
                        
                        print(f"✅ V2 WebSocket Test: {data}")
                        return True
                else:
                    print(f"❌ V2 Session Creation Failed: {response.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ V2 WebSocket Test Failed: {e}")
        return False

async def test_versions_endpoint():
    """Test versions endpoint"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{V2_BACKEND_URL}/versions") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Versions Endpoint: {len(data['versions'])} versions available")
                    for version, info in data['versions'].items():
                        print(f"   - {version}: {info['name']} ({info['status']})")
                    return True
                else:
                    print(f"❌ Versions Endpoint Failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Versions Endpoint Error: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 Final Frontend Integration Test")
    print("=" * 50)
    
    results = []
    
    # Test backend health
    print("\n1. Testing Backend Health...")
    v1_health = await test_backend_health(V1_BACKEND_URL, "V1")
    v2_health = await test_backend_health(V2_BACKEND_URL, "V2")
    results.extend([v1_health, v2_health])
    
    # Test versions endpoint
    print("\n2. Testing Versions Endpoint...")
    versions_ok = await test_versions_endpoint()
    results.append(versions_ok)
    
    # Test v1 WebSocket
    print("\n3. Testing V1 WebSocket...")
    v1_ws = await test_v1_websocket()
    results.append(v1_ws)
    
    # Test v2 WebSocket
    print("\n4. Testing V2 WebSocket...")
    v2_ws = await test_v2_session_creation()
    results.append(v2_ws)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print(f"✅ Passed: {sum(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}")
    
    if all(results):
        print("\n🎉 All tests passed! Frontend should work correctly.")
        print("\n📋 Frontend Configuration:")
        print(f"   V1 Backend: {V1_BACKEND_URL}")
        print(f"   V2 Backend: {V2_BACKEND_URL}")
        print(f"   V1 WebSocket: wss://dharsan99--voice-ai-backend-run-app.modal.run/ws")
        print(f"   V2 WebSocket: wss://dharsan99--voice-ai-backend-v2-run-app.modal.run/ws/v2")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
    
    return all(results)

if __name__ == "__main__":
    asyncio.run(main()) 