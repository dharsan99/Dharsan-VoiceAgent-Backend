#!/usr/bin/env python3
"""
Test script for STT Service
"""

import requests
import time
import json

def test_stt_service():
    """Test the STT service endpoints"""
    base_url = "http://localhost:8000"
    
    print("Testing STT Service...")
    
    # Test health endpoint
    print("\n1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            health_data = response.json()
            print(f"✓ Health check passed: {health_data['status']}")
            print(f"  Model loaded: {health_data['model_loaded']}")
            print(f"  Model size: {health_data['model_size']}")
            print(f"  Uptime: {health_data['uptime']:.2f}s")
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Health check error: {e}")
        return False
    
    # Test models endpoint
    print("\n2. Testing models endpoint...")
    try:
        response = requests.get(f"{base_url}/models")
        if response.status_code == 200:
            models_data = response.json()
            print(f"✓ Models endpoint working")
            print(f"  Current model: {models_data['current_model']}")
            print(f"  Available models: {models_data['available_models']}")
        else:
            print(f"✗ Models endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Models endpoint error: {e}")
        return False
    
    # Test metrics endpoint
    print("\n3. Testing metrics endpoint...")
    try:
        response = requests.get(f"{base_url}/metrics")
        if response.status_code == 200:
            print("✓ Metrics endpoint working")
        else:
            print(f"✗ Metrics endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Metrics endpoint error: {e}")
    
    print("\n✓ STT Service is running and responding correctly!")
    return True

if __name__ == "__main__":
    test_stt_service() 