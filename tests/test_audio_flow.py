#!/usr/bin/env python3
"""
Test script to verify audio flow through V2 pipeline
"""

import asyncio
import websockets
import json
import time
import requests
from kafka import KafkaProducer, KafkaConsumer

def test_media_server():
    """Test if media server is accessible"""
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

def test_orchestrator_websocket():
    """Test if orchestrator WebSocket is accessible"""
    try:
        # Test WebSocket connection
        async def test_ws():
            uri = "ws://localhost:8001/ws"
            async with websockets.connect(uri) as websocket:
                # Wait for welcome message
                message = await websocket.recv()
                data = json.loads(message)
                if data['type'] == 'connection_established':
                    print("✅ Orchestrator WebSocket: Connected")
                    return True
                else:
                    print(f"❌ Orchestrator WebSocket: Unexpected message {data}")
                    return False
        
        return asyncio.run(test_ws())
    except Exception as e:
        print(f"❌ Orchestrator WebSocket: {e}")
        return False

def test_kafka_audio_flow():
    """Test if audio messages flow through Kafka"""
    try:
        # Send test audio message
        producer = KafkaProducer(bootstrap_servers=['localhost:9092'])
        test_audio = b'test audio data for flow verification'
        producer.send('audio-in', key=b'test-session', value=test_audio)
        producer.flush()
        producer.close()
        
        print("✅ Kafka Audio Flow: Test message sent")
        
        # Check if message was consumed by orchestrator
        time.sleep(2)  # Wait for processing
        
        # Check audio-out topic for response
        consumer = KafkaConsumer('audio-out', 
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
            print("✅ Kafka Audio Flow: Response received")
            return True
        else:
            print("⚠️  Kafka Audio Flow: No response received")
            return False
            
    except Exception as e:
        print(f"❌ Kafka Audio Flow: {e}")
        return False

def test_complete_pipeline():
    """Test the complete pipeline"""
    print("🔍 Testing V2 Audio Pipeline...")
    print("=" * 50)
    
    tests = [
        ("Media Server", test_media_server),
        ("Orchestrator WebSocket", test_orchestrator_websocket),
        ("Kafka Audio Flow", test_kafka_audio_flow),
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
        print("🎉 Pipeline is working! Try speaking into your microphone.")
    else:
        print("⚠️  Pipeline has issues. Check the logs above.")

if __name__ == "__main__":
    test_complete_pipeline() 