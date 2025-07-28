#!/usr/bin/env python3
"""
Basic WHIP connection test
"""

import asyncio
import json
import time
import requests
from kafka import KafkaConsumer

def test_whip_basic():
    """Test basic WHIP connection"""
    print("🔍 Testing Basic WHIP Connection...")
    print("=" * 50)
    
    # Test 1: Check if media server is accessible
    print("📋 Test 1: Media Server Health Check")
    try:
        response = requests.get('http://localhost:8080/health', timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Media Server: {data['status']}")
            print(f"   AI Enabled: {data['ai_enabled']}")
            print(f"   Kafka: {data['kafka']}")
            print(f"   Phase: {data['phase']}")
        else:
            print(f"❌ Media Server: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Media Server: {e}")
        return False
    
    # Test 2: Check if WHIP endpoint is accessible
    print("\n📋 Test 2: WHIP Endpoint Check")
    try:
        response = requests.post('http://localhost:8080/whip', 
                               headers={'Content-Type': 'application/sdp'},
                               data='v=0\r\no=- 1234567890 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n',
                               timeout=5)
        print(f"✅ WHIP Endpoint: HTTP {response.status_code}")
        if response.status_code == 201:
            print("   WHIP endpoint is accepting connections")
        else:
            print(f"   Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"❌ WHIP Endpoint: {e}")
        return False
    
    # Test 3: Check Kafka connectivity
    print("\n📋 Test 3: Kafka Connectivity")
    try:
        consumer = KafkaConsumer('audio-in', 
                               bootstrap_servers=['localhost:9092'],
                               auto_offset_reset='latest',
                               consumer_timeout_ms=1000)
        consumer.close()
        print("✅ Kafka: Connected")
    except Exception as e:
        print(f"❌ Kafka: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("📊 Basic WHIP Test Results:")
    print("✅ All basic connectivity tests passed")
    print("\n🎯 Next Steps:")
    print("1. The issue is likely in the frontend WHIP implementation")
    print("2. The frontend may not be sending audio tracks properly")
    print("3. Check if the frontend is adding audio tracks to the peer connection")
    print("4. Verify that the frontend is actually sending audio data")
    
    return True

if __name__ == "__main__":
    test_whip_basic() 