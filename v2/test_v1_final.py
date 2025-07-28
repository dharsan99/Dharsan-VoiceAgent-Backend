#!/usr/bin/env python3
"""
Final V1 Integration Test
Verifies that V1 backend and frontend are working correctly after all fixes
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

# Backend URLs
V1_BACKEND_URL = "https://dharsan99--voice-ai-backend-run-app.modal.run"
V1_WEBSOCKET_URL = "wss://dharsan99--voice-ai-backend-run-app.modal.run/ws"
FRONTEND_URL = "http://localhost:5173"

async def test_v1_backend_health():
    """Test V1 backend health"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{V1_BACKEND_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ V1 Backend Healthy: {data['status']}")
                    print(f"   Router: {data['router']}")
                    print(f"   Available versions: {data['available_versions']}")
                    return True
                else:
                    print(f"❌ V1 Backend unhealthy: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ V1 Backend health check failed: {e}")
        return False

async def test_v1_websocket():
    """Test V1 WebSocket connection and echo messages"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(V1_WEBSOCKET_URL) as ws:
                print(f"✅ V1 WebSocket connected to: {V1_WEBSOCKET_URL}")
                
                # Wait for initial info message
                msg = await ws.receive_json()
                print(f"📥 Received initial message: {msg['type']} - {msg['message']}")
                
                # Send test message
                test_data = "Hello V1 Backend!"
                await ws.send_str(test_data)
                print(f"📤 Sent test message: {test_data}")
                
                # Wait for echo response
                echo_msg = await ws.receive_json()
                print(f"📥 Received echo: {echo_msg['type']} - {echo_msg['data']}")
                
                if echo_msg['type'] == 'echo' and echo_msg['data'] == test_data:
                    print("✅ Echo message working correctly!")
                    return True
                else:
                    print(f"❌ Echo message mismatch: {echo_msg}")
                    return False
                    
    except Exception as e:
        print(f"❌ V1 WebSocket test failed: {e}")
        return False

def test_frontend_health():
    """Test frontend health"""
    try:
        import requests
        response = requests.get(FRONTEND_URL, timeout=5)
        if response.status_code == 200:
            print(f"✅ Frontend running at: {FRONTEND_URL}")
            return True
        else:
            print(f"❌ Frontend returned status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Frontend health check failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🧪 Final V1 Integration Test")
    print("=" * 50)
    
    # Test V1 Backend Health
    print("\n🏥 Testing V1 Backend Health...")
    v1_health = await test_v1_backend_health()
    
    # Test V1 WebSocket
    print("\n🔗 Testing V1 WebSocket...")
    v1_websocket = await test_v1_websocket()
    
    # Test Frontend
    print("\n🌐 Testing Frontend...")
    frontend_health = test_frontend_health()
    
    # Summary
    print("\n📊 Test Results:")
    print(f"V1 Backend Health: {'✅ PASS' if v1_health else '❌ FAIL'}")
    print(f"V1 WebSocket: {'✅ PASS' if v1_websocket else '❌ FAIL'}")
    print(f"Frontend Health: {'✅ PASS' if frontend_health else '❌ FAIL'}")
    
    if v1_health and v1_websocket and frontend_health:
        print("\n🎉 All tests passed! V1 is working correctly.")
        print("\n📝 Summary of fixes applied:")
        print("✅ Fixed JSON message format in V1 backend")
        print("✅ Reduced excessive logging in frontend")
        print("✅ Fixed multiple app initializations")
        print("✅ V1 hook now connects to correct endpoint")
        print("✅ Echo messages working correctly")
    else:
        print("\n❌ Some tests failed. Please check the issues above.")
    
    print(f"\n⏰ Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    asyncio.run(main()) 