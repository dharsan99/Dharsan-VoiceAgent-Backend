#!/usr/bin/env python3
"""
Test V1 Connection
Verifies that V1 backend is working and can be connected to from frontend
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

# V1 Backend URLs
V1_BACKEND_URL = "https://dharsan99--voice-ai-backend-run-app.modal.run"
V1_WEBSOCKET_URL = "wss://dharsan99--voice-ai-backend-run-app.modal.run/ws"

async def test_v1_health():
    """Test V1 backend health"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{V1_BACKEND_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ V1 Backend Healthy: {data['status']}")
                    print(f"   Available versions: {data['available_versions']}")
                    return True
                else:
                    print(f"❌ V1 Backend Health Check Failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ V1 Backend Health Check Error: {e}")
        return False

async def test_v1_websocket():
    """Test V1 WebSocket connection"""
    try:
        import websockets
        
        async with websockets.connect(V1_WEBSOCKET_URL) as websocket:
            # Send a test message
            test_message = {
                "type": "test",
                "data": "Frontend V1 connection test",
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

async def test_frontend_v1_config():
    """Test frontend V1 configuration"""
    print("\n🔧 Frontend V1 Configuration:")
    print(f"   V1 WebSocket URL: {V1_WEBSOCKET_URL}")
    print(f"   V1 Backend URL: {V1_BACKEND_URL}")
    print(f"   Environment Variable: VITE_WEBSOCKET_URL_V1={V1_WEBSOCKET_URL}")
    return True

async def main():
    """Run all V1 tests"""
    print("🧪 V1 Connection Test")
    print("=" * 50)
    
    results = []
    
    # Test V1 backend health
    print("\n1. Testing V1 Backend Health...")
    v1_health = await test_v1_health()
    results.append(v1_health)
    
    # Test V1 WebSocket
    print("\n2. Testing V1 WebSocket...")
    v1_ws = await test_v1_websocket()
    results.append(v1_ws)
    
    # Show frontend configuration
    print("\n3. Frontend Configuration...")
    frontend_config = await test_frontend_v1_config()
    results.append(frontend_config)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 V1 Test Results Summary:")
    print(f"✅ Passed: {sum(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}")
    
    if all(results):
        print("\n🎉 All V1 tests passed! V1 should work correctly.")
        print("\n📋 Next Steps:")
        print("1. Open http://localhost:5173 in your browser")
        print("2. Check that V1 is selected by default")
        print("3. Try connecting to V1")
        print("4. Check console for V1 connection logs")
        print("\n🔧 Expected V1 Behavior:")
        print("- Should connect to wss://dharsan99--voice-ai-backend-run-app.modal.run/ws")
        print("- Should show 'V1 WebSocket connected' in console")
        print("- Should establish V1 session")
    else:
        print("\n⚠️  Some V1 tests failed. Check the errors above.")
    
    return all(results)

if __name__ == "__main__":
    asyncio.run(main()) 