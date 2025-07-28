# test_websocket.py
# Simple WebSocket test client for Voice AI Backend

import asyncio
import websockets
import json
import sys

async def test_websocket_connection(websocket_url: str):
    """Test WebSocket connection to the voice AI backend"""
    
    print(f"🔗 Testing WebSocket connection to: {websocket_url}")
    
    try:
        async with websockets.connect(websocket_url) as websocket:
            print("✅ WebSocket connection established successfully!")
            
            # Send a test binary message (simulating audio data)
            test_audio_data = b'\x00\x00\x00\x00' * 1024  # 4KB of silence
            print(f"📤 Sending test audio data: {len(test_audio_data)} bytes")
            
            # Note: The actual implementation expects binary audio data
            # This is just a connection test
            await websocket.send(test_audio_data)
            
            # Wait for a response (if any)
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📥 Received response: {response}")
            except asyncio.TimeoutError:
                print("⏰ No response received within 5 seconds (expected for audio-only endpoint)")
            
            print("✅ WebSocket test completed successfully!")
            
    except websockets.exceptions.InvalidURI:
        print("❌ Invalid WebSocket URL")
        return False
    except websockets.exceptions.ConnectionClosed:
        print("❌ WebSocket connection was closed")
        return False
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False
    
    return True

async def test_health_endpoint(base_url: str):
    """Test the health endpoint"""
    
    import httpx
    
    health_url = f"{base_url}/health"
    print(f"🏥 Testing health endpoint: {health_url}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(health_url)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed: {data}")
                return True
            else:
                print(f"❌ Health check failed with status {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

async def main():
    """Main test function"""
    
    if len(sys.argv) < 2:
        print("Usage: python test_websocket.py <websocket_url>")
        print("Example: python test_websocket.py wss://your-app.modal.run")
        sys.exit(1)
    
    websocket_url = sys.argv[1]
    
    # Extract base URL for health check
    if websocket_url.startswith("wss://"):
        base_url = websocket_url.replace("wss://", "https://")
        # Remove /ws from the base URL for health check
        if base_url.endswith("/ws"):
            base_url = base_url[:-3]
    else:
        base_url = websocket_url
    
    print("🧪 Voice AI Backend Test Suite")
    print("==============================")
    
    # Test health endpoint
    health_success = await test_health_endpoint(base_url)
    
    # Test WebSocket connection
    websocket_success = await test_websocket_connection(websocket_url)
    
    print("\n📊 Test Results:")
    print(f"Health Endpoint: {'✅ PASS' if health_success else '❌ FAIL'}")
    print(f"WebSocket Connection: {'✅ PASS' if websocket_success else '❌ FAIL'}")
    
    if health_success and websocket_success:
        print("\n🎉 All tests passed! Your backend is ready for the frontend.")
    else:
        print("\n⚠️  Some tests failed. Please check your deployment.")

if __name__ == "__main__":
    asyncio.run(main()) 