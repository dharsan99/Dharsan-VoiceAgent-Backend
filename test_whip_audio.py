#!/usr/bin/env python3
"""
Test script to verify WHIP audio flow to Kafka
"""

import asyncio
import json
import time
import requests
from kafka import KafkaConsumer

def test_whip_audio_flow():
    """Test if WHIP sends audio to Kafka"""
    print("🔍 Testing WHIP Audio Flow...")
    print("=" * 50)
    
    print("📋 Instructions:")
    print("1. Open your frontend (React app)")
    print("2. Navigate to V2 Dashboard")
    print("3. Click 'Start Conversation'")
    print("4. Speak into your microphone for 10 seconds")
    print("5. Watch for Kafka messages below...")
    print()
    
    # Monitor Kafka audio-in topic in real-time
    print("📡 Monitoring Kafka audio-in topic...")
    print("   (Press Ctrl+C to stop)")
    print()
    
    try:
        consumer = KafkaConsumer('audio-in', 
                               bootstrap_servers=['localhost:9092'],
                               auto_offset_reset='latest',
                               consumer_timeout_ms=1000)
        
        message_count = 0
        start_time = time.time()
        
        while True:
            try:
                for message in consumer:
                    message_count += 1
                    elapsed = time.time() - start_time
                    print(f"🎵 [{elapsed:.1f}s] Audio message #{message_count} received")
                    print(f"   Session ID: {message.key.decode() if message.key else 'None'}")
                    print(f"   Audio size: {len(message.value)} bytes")
                    print(f"   Headers: {[h.key.decode() for h in message.headers]}")
                    print()
                    
                    # If we get audio messages, the pipeline is working
                    if message_count >= 3:
                        print("✅ SUCCESS: WHIP is sending audio to Kafka!")
                        print("   The media server is receiving audio from WHIP")
                        print("   The issue might be in the orchestrator processing")
                        consumer.close()
                        return True
                        
            except Exception as e:
                # No messages in this iteration, continue
                pass
                
            # Check if we've been monitoring for too long
            if time.time() - start_time > 30:  # 30 seconds timeout
                print("⏰ Timeout: No audio messages received in 30 seconds")
                print("   This means WHIP is not sending audio to Kafka")
                print("   Possible issues:")
                print("   - Media server not receiving WHIP audio")
                print("   - Media server not publishing to Kafka")
                print("   - WHIP connection not established properly")
                consumer.close()
                return False
                
    except KeyboardInterrupt:
        print("\n⏹️  Monitoring stopped by user")
        consumer.close()
        return message_count > 0

if __name__ == "__main__":
    test_whip_audio_flow() 