#!/usr/bin/env python3
"""
Debug Orchestrator Processing
"""

import time
import json
import requests
from kafka import KafkaProducer, KafkaConsumer

def test_orchestrator_debug():
    """Debug orchestrator processing"""
    print("🔍 Debugging Orchestrator Processing...")
    print("=" * 50)
    
    # Test 1: Send multiple audio chunks to simulate real conversation
    print("📋 Test 1: Sending Multiple Audio Chunks")
    try:
        producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        session_id = "debug-session-" + str(int(time.time()))
        
        # Send multiple audio chunks to accumulate enough data
        for i in range(10):
            # Create realistic audio data (not all same bytes)
            import numpy as np
            sample_rate = 16000
            duration = 0.1  # 100ms chunks
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            # Generate a sine wave at 440 Hz
            audio_data = np.sin(2 * np.pi * 440 * t)
            # Convert to 16-bit PCM
            audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()
            
            # Create message
            message = {
                "session_id": session_id,
                "audio_data": audio_bytes.hex(),
                "timestamp": time.time()
            }
            
            # Send to audio-in topic
            producer.send('audio-in', message)
            print(f"📤 Sent audio chunk #{i+1} ({len(audio_bytes)} bytes)")
            time.sleep(0.1)  # Small delay between chunks
        
        producer.flush()
        print(f"✅ Sent 10 audio chunks for session: {session_id}")
        
    except Exception as e:
        print(f"❌ Failed to send audio chunks: {e}")
    
    # Test 2: Monitor for any processing activity
    print("\n📋 Test 2: Monitoring Processing Activity")
    print("📡 Monitoring for 20 seconds...")
    
    try:
        # Monitor both audio-in and audio-out topics
        consumer_in = KafkaConsumer('audio-in', 
                                  bootstrap_servers=['localhost:9092'],
                                  auto_offset_reset='latest',
                                  consumer_timeout_ms=5000)
        
        consumer_out = KafkaConsumer('audio-out', 
                                   bootstrap_servers=['localhost:9092'],
                                   auto_offset_reset='latest',
                                   consumer_timeout_ms=5000)
        
        start_time = time.time()
        in_count = 0
        out_count = 0
        
        # Check for recent messages
        for message in consumer_in:
            in_count += 1
            elapsed = time.time() - start_time
            print(f"📥 [{elapsed:.1f}s] Audio-in message #{in_count}")
        
        for message in consumer_out:
            out_count += 1
            elapsed = time.time() - start_time
            print(f"📤 [{elapsed:.1f}s] Audio-out message #{out_count}")
        
        print(f"\n📊 Summary:")
        print(f"   Audio-in messages: {in_count}")
        print(f"   Audio-out messages: {out_count}")
        
        if out_count == 0:
            print("⚠️  No AI responses generated")
            print("   This suggests the orchestrator is not processing audio")
            print("   Check orchestrator logs for errors")
        
    except Exception as e:
        print(f"❌ Failed to monitor: {e}")

if __name__ == "__main__":
    test_orchestrator_debug() 