#!/usr/bin/env python3
"""
Test AI Pipeline with real audio data
"""

import time
import json
import requests
from kafka import KafkaProducer, KafkaConsumer
import struct

def test_ai_pipeline():
    """Test the complete AI pipeline"""
    print("🔍 Testing AI Pipeline...")
    print("=" * 50)
    
    # Test 1: Check if orchestrator is running
    print("📋 Test 1: Orchestrator Health Check")
    try:
        response = requests.get('http://localhost:8001/health', timeout=5)
        if response.status_code == 200:
            print("✅ Orchestrator: Running")
        else:
            print(f"⚠️  Orchestrator: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Orchestrator: {e}")
    
    # Test 2: Send real audio data to Kafka
    print("\n📋 Test 2: Sending Real Audio Data")
    try:
        producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # Create realistic audio data (not all same bytes)
        import numpy as np
        sample_rate = 16000
        duration = 2  # seconds
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # Generate a sine wave at 440 Hz
        audio_data = np.sin(2 * np.pi * 440 * t)
        # Convert to 16-bit PCM
        audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()
        
        # Create test message
        test_message = {
            "session_id": "test-ai-pipeline",
            "audio_data": audio_bytes.hex(),  # Convert to hex string
            "timestamp": time.time()
        }
        
        # Send to audio-in topic
        producer.send('audio-in', test_message)
        producer.flush()
        print("✅ Real audio data sent to Kafka")
        
    except Exception as e:
        print(f"❌ Failed to send audio data: {e}")
    
    # Test 3: Monitor for AI responses
    print("\n📋 Test 3: Monitoring AI Responses")
    print("📡 Monitoring audio-out topic for 30 seconds...")
    
    try:
        consumer = KafkaConsumer('audio-out', 
                               bootstrap_servers=['localhost:9092'],
                               auto_offset_reset='latest',
                               consumer_timeout_ms=30000)
        
        response_count = 0
        start_time = time.time()
        
        for message in consumer:
            try:
                data = json.loads(message.value.decode('utf-8'))
                response_count += 1
                elapsed = time.time() - start_time
                
                print(f"🎵 [{elapsed:.1f}s] AI Response #{response_count}")
                print(f"   Session ID: {data.get('session_id', 'unknown')}")
                print(f"   Audio size: {len(data.get('audio_data', ''))} bytes")
                
            except Exception as e:
                print(f"❌ Failed to parse response: {e}")
        
        if response_count == 0:
            print("⏰ No AI responses received in 30 seconds")
            print("   Possible issues:")
            print("   - Audio format not compatible with Google Cloud STT")
            print("   - Google Cloud credentials not configured")
            print("   - AI processing pipeline failing")
        else:
            print(f"✅ Received {response_count} AI responses")
            
    except Exception as e:
        print(f"❌ Failed to monitor responses: {e}")

if __name__ == "__main__":
    test_ai_pipeline() 