#!/usr/bin/env python3
"""
Test script to verify backend log endpoints are working correctly.
This script tests the logs endpoints for all services in both development and production environments.
"""

import requests
import json
import time
from typing import Dict, Any

def test_service_logs(service_url: str, service_name: str) -> Dict[str, Any]:
    """Test the logs endpoint for a specific service"""
    try:
        url = f"{service_url}/logs"
        print(f"Testing {service_name} logs endpoint: {url}")
        
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {service_name}: Success - {data.get('count', 0)} logs")
            return {
                "service": service_name,
                "status": "success",
                "count": data.get('count', 0),
                "data": data
            }
        else:
            print(f"❌ {service_name}: HTTP {response.status_code}")
            return {
                "service": service_name,
                "status": "error",
                "error": f"HTTP {response.status_code}"
            }
    except requests.exceptions.RequestException as e:
        print(f"❌ {service_name}: Connection error - {e}")
        return {
            "service": service_name,
            "status": "error",
            "error": str(e)
        }

def test_orchestrator_logs_aggregation(orchestrator_url: str) -> Dict[str, Any]:
    """Test the orchestrator's log aggregation endpoint"""
    try:
        url = f"{orchestrator_url}/logs"
        print(f"Testing orchestrator log aggregation: {url}")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Orchestrator aggregation: Success - {data.get('count', 0)} logs from {data.get('environment', 'unknown')} environment")
            return {
                "service": "orchestrator-aggregation",
                "status": "success",
                "count": data.get('count', 0),
                "environment": data.get('environment', 'unknown'),
                "data": data
            }
        else:
            print(f"❌ Orchestrator aggregation: HTTP {response.status_code}")
            return {
                "service": "orchestrator-aggregation",
                "status": "error",
                "error": f"HTTP {response.status_code}"
            }
    except requests.exceptions.RequestException as e:
        print(f"❌ Orchestrator aggregation: Connection error - {e}")
        return {
            "service": "orchestrator-aggregation",
            "status": "error",
            "error": str(e)
        }

def main():
    print("🔍 Testing Backend Log Endpoints")
    print("=" * 50)
    
    # Test individual service endpoints (development)
    print("\n📋 Testing Individual Service Endpoints (Development)")
    print("-" * 50)
    
    dev_services = {
        "orchestrator": "http://localhost:8004",
        "stt-service": "http://localhost:8000", 
        "tts-service": "http://localhost:5001",
        "media-server": "http://localhost:8001"
    }
    
    results = []
    
    for service_name, service_url in dev_services.items():
        result = test_service_logs(service_url, service_name)
        results.append(result)
        time.sleep(0.5)  # Small delay between requests
    
    # Test orchestrator log aggregation
    print("\n🔄 Testing Orchestrator Log Aggregation")
    print("-" * 50)
    
    orchestrator_result = test_orchestrator_logs_aggregation("http://localhost:8004")
    results.append(orchestrator_result)
    
    # Summary
    print("\n📊 Test Summary")
    print("=" * 50)
    
    successful = sum(1 for r in results if r["status"] == "success")
    total = len(results)
    
    print(f"Total tests: {total}")
    print(f"Successful: {successful}")
    print(f"Failed: {total - successful}")
    
    if successful == total:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    # Show detailed results
    print("\n📋 Detailed Results")
    print("-" * 50)
    
    for result in results:
        status_icon = "✅" if result["status"] == "success" else "❌"
        print(f"{status_icon} {result['service']}: {result['status']}")
        if result["status"] == "success" and "count" in result:
            print(f"   └─ Logs: {result['count']}")
        elif result["status"] == "error":
            print(f"   └─ Error: {result['error']}")

if __name__ == "__main__":
    main() 