#!/usr/bin/env python3
"""
Test script to verify that both servers are running and accessible.
"""

import asyncio
import aiohttp
import websockets
import json
import sys
from urllib.parse import urljoin

async def test_media_server():
    """Test the Go Media Server (WHIP endpoint)"""
    print("🔍 Testing Go Media Server (port 8080)...")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test basic connectivity
            async with session.get('http://localhost:8080/') as response:
                if response.status == 200:
                    print("✅ Media server is running")
                    return True
                else:
                    print(f"❌ Media server returned status {response.status}")
                    return False
    except aiohttp.ClientConnectorError:
        print("❌ Cannot connect to media server (port 8080)")
        print("   Make sure to run: cd media-server && ./media-server")
        return False
    except Exception as e:
        print(f"❌ Error testing media server: {e}")
        return False

async def test_python_backend():
    """Test the Python Backend (WebSocket endpoint)"""
    print("🔍 Testing Python Backend (port 8000)...")
    
    try:
        # Test WebSocket connection
        uri = "ws://localhost:8000/ws/v2"
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connection established")
            
            # Send a test message
            test_message = {
                "type": "test",
                "message": "Hello from test script"
            }
            await websocket.send(json.dumps(test_message))
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                print(f"✅ Received response: {data.get('type', 'unknown')}")
                return True
            except asyncio.TimeoutError:
                print("⚠️  No response received (this might be normal)")
                return True
                
    except (websockets.exceptions.ConnectionClosed, OSError):
        print("❌ Cannot connect to Python backend (port 8000)")
        print("   Make sure to run: python main.py")
        return False
    except Exception as e:
        print(f"❌ Error testing Python backend: {e}")
        return False

async def test_health_endpoints():
    """Test health endpoints"""
    print("🔍 Testing health endpoints...")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test Python backend health
            async with session.get('http://localhost:8000/v2/health') as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Python backend health: {data}")
                else:
                    print(f"❌ Python backend health check failed: {response.status}")
                    
            # Test Python backend sessions
            async with session.get('http://localhost:8000/v2/sessions') as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Python backend sessions: {data}")
                else:
                    print(f"❌ Python backend sessions check failed: {response.status}")
                    
    except Exception as e:
        print(f"❌ Error testing health endpoints: {e}")

async def main():
    """Run all tests"""
    print("🚀 Testing Voice AI Backend v2.0 servers...")
    print("=" * 50)
    
    # Test media server
    media_server_ok = await test_media_server()
    print()
    
    # Test Python backend
    python_backend_ok = await test_python_backend()
    print()
    
    # Test health endpoints
    await test_health_endpoints()
    print()
    
    # Summary
    print("=" * 50)
    print("📊 Test Results:")
    print(f"   Go Media Server (WHIP): {'✅ OK' if media_server_ok else '❌ FAILED'}")
    print(f"   Python Backend (WebSocket): {'✅ OK' if python_backend_ok else '❌ FAILED'}")
    
    if media_server_ok and python_backend_ok:
        print("\n🎉 Both servers are running correctly!")
        print("   You can now test the frontend application.")
    else:
        print("\n⚠️  Some servers are not running correctly.")
        print("   Please check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 