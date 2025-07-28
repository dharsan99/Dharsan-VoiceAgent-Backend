#!/usr/bin/env python3
"""
Test script for V2 Voice Agent Pipeline
Tests the complete flow: WHIP → Kafka → AI Orchestrator → Response
"""

import asyncio
import json
import time
import websockets
import requests
from kafka import KafkaProducer, KafkaConsumer
import threading

def test_media_server():
    """Test if media server is running and healthy"""
    try:
        response = requests.get('http://localhost:8080/health', timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Media Server: {data['status']}")
            print(f"   AI Enabled: {data['ai_enabled']}")
            print(f"   Kafka: {data['kafka']}")
            print(f"   Phase: {data['phase']}")
            return True
        else:
            print(f"❌ Media Server: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Media Server: {e}")
        return False

def test_kafka():
    """Test if Kafka is accessible"""
    try:
        producer = KafkaProducer(bootstrap_servers=['localhost:9092'])
        producer.close()
        print("✅ Kafka: Connected")
        return True
    except Exception as e:
        print(f"❌ Kafka: {e}")
        return False

def test_orchestrator():
    """Test if orchestrator is running"""
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if 'orchestrator' in proc.info['name']:
                print(f"✅ Orchestrator: Running (PID {proc.info['pid']})")
                return True
        print("❌ Orchestrator: Not found")
        return False
    except Exception as e:
        print(f"❌ Orchestrator check failed: {e}")
        return False

def test_kafka_messages():
    """Test if messages are flowing through Kafka"""
    try:
        # Test producer
        producer = KafkaProducer(bootstrap_servers=['localhost:9092'])
        test_message = b'test audio data for pipeline verification'
        producer.send('audio-in', key=b'test-session', value=test_message)
        producer.flush()
        producer.close()
        
        # Test consumer
        consumer = KafkaConsumer('audio-in', 
                               bootstrap_servers=['localhost:9092'],
                               auto_offset_reset='latest',
                               consumer_timeout_ms=5000)
        
        message_count = 0
        for message in consumer:
            message_count += 1
            if message_count >= 1:
                break
        
        consumer.close()
        
        if message_count > 0:
            print("✅ Kafka Messages: Flowing")
            return True
        else:
            print("⚠️  Kafka Messages: No recent messages")
            return False
            
    except Exception as e:
        print(f"❌ Kafka Messages: {e}")
        return False

def main():
    """Run all tests"""
    print("🔍 Testing V2 Voice Agent Pipeline...")
    print("=" * 50)
    
    tests = [
        ("Media Server", test_media_server),
        ("Kafka", test_kafka),
        ("Orchestrator", test_orchestrator),
        ("Kafka Messages", test_kafka_messages),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Testing {test_name}...")
        result = test_func()
        results.append((test_name, result))
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All systems are ready! Try speaking into your microphone.")
    else:
        print("⚠️  Some systems need attention. Check the logs above.")

if __name__ == "__main__":
    main() 