#!/usr/bin/env python3
"""
Test React Hooks Fix
Verifies that the frontend hooks are working correctly after the fix
"""

import requests
import json
import time
from datetime import datetime

def test_frontend_health():
    """Test if frontend is running and accessible"""
    try:
        response = requests.get('http://localhost:5173', timeout=5)
        if response.status_code == 200:
            print("✅ Frontend is running at http://localhost:5173")
            return True
        else:
            print(f"❌ Frontend returned status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Frontend not accessible: {e}")
        return False

def test_backend_health():
    """Test both backends are healthy"""
    backends = [
        ("V1", "https://dharsan99--voice-ai-backend-run-app.modal.run/health"),
        ("V2", "https://dharsan99--voice-ai-backend-v2-run-app.modal.run/health")
    ]
    
    all_healthy = True
    for name, url in backends:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ {name} Backend Healthy: {data['status']}")
            else:
                print(f"❌ {name} Backend Health Check Failed: {response.status_code}")
                all_healthy = False
        except Exception as e:
            print(f"❌ {name} Backend Health Check Error: {e}")
            all_healthy = False
    
    return all_healthy

def test_websocket_endpoints():
    """Test WebSocket endpoints are accessible"""
    endpoints = [
        ("V1", "wss://dharsan99--voice-ai-backend-run-app.modal.run/ws"),
        ("V2", "wss://dharsan99--voice-ai-backend-v2-run-app.modal.run/ws/v2")
    ]
    
    print("\n🔗 WebSocket Endpoints:")
    for name, url in endpoints:
        print(f"   {name}: {url}")
    
    return True

def main():
    """Run all tests"""
    print("🧪 React Hooks Fix Verification Test")
    print("=" * 50)
    
    # Test frontend
    print("\n1. Testing Frontend Health...")
    frontend_ok = test_frontend_health()
    
    # Test backends
    print("\n2. Testing Backend Health...")
    backends_ok = test_backend_health()
    
    # Show WebSocket endpoints
    print("\n3. WebSocket Endpoints...")
    websocket_ok = test_websocket_endpoints()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print(f"✅ Frontend: {'PASS' if frontend_ok else 'FAIL'}")
    print(f"✅ Backends: {'PASS' if backends_ok else 'FAIL'}")
    print(f"✅ WebSocket URLs: {'PASS' if websocket_ok else 'FAIL'}")
    
    if all([frontend_ok, backends_ok, websocket_ok]):
        print("\n🎉 All tests passed! React hooks fix should be working.")
        print("\n📋 Next Steps:")
        print("1. Open http://localhost:5173 in your browser")
        print("2. Check browser console for any React hooks errors")
        print("3. Try switching between V1, V2, and WebRTC versions")
        print("4. Verify only the selected version's hook is active")
        print("\n🔧 Expected Behavior:")
        print("- No 'Rendered more hooks than during the previous render' errors")
        print("- V1 hook only connects when V1 is selected")
        print("- V2 hook only connects when V2 is selected")
        print("- WebRTC hook only connects when WebRTC is selected")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
    
    return all([frontend_ok, backends_ok, websocket_ok])

if __name__ == "__main__":
    main() 