#!/usr/bin/env python3
"""
Debug WHIP connection and audio flow
"""

import time
import subprocess
import threading
from kafka import KafkaConsumer
import json

def monitor_kafka():
    """Monitor Kafka audio-in topic"""
    print("🔍 Starting Kafka monitoring...")
    try:
        consumer = KafkaConsumer('audio-in', 
                               bootstrap_servers=['localhost:9092'],
                               auto_offset_reset='latest',
                               consumer_timeout_ms=1000)
        
        message_count = 0
        start_time = time.time()
        
        while True:
            try:
                message = next(consumer)
                message_count += 1
                elapsed = time.time() - start_time
                print(f"📨 Kafka message #{message_count} received after {elapsed:.1f}s")
                print(f"   Key: {message.key}")
                print(f"   Value length: {len(message.value)} bytes")
                print(f"   Topic: {message.topic}")
                print(f"   Partition: {message.partition}")
                print(f"   Offset: {message.offset}")
                print()
                
            except StopIteration:
                # No more messages, continue monitoring
                time.sleep(0.1)
                
    except Exception as e:
        print(f"❌ Kafka monitoring error: {e}")

def monitor_media_server():
    """Monitor media server logs"""
    print("🔍 Starting media server log monitoring...")
    try:
        # Use tail to follow media server logs
        process = subprocess.Popen(
            ['tail', '-f', '/tmp/media_server.log'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        while True:
            line = process.stdout.readline()
            if line:
                if 'Received remote track' in line or 'processAIAudio' in line or 'audio' in line.lower():
                    print(f"📡 Media Server: {line.strip()}")
            time.sleep(0.1)
            
    except Exception as e:
        print(f"❌ Media server monitoring error: {e}")

def main():
    print("🔍 WHIP Debug Test")
    print("=" * 50)
    print("📋 Instructions:")
    print("1. Open http://localhost:3000/test_whip_simple.html")
    print("2. Click 'Start WHIP Connection'")
    print("3. Speak into your microphone")
    print("4. Watch for Kafka messages and media server logs below...")
    print()
    
    # Start monitoring threads
    kafka_thread = threading.Thread(target=monitor_kafka, daemon=True)
    media_thread = threading.Thread(target=monitor_media_server, daemon=True)
    
    kafka_thread.start()
    media_thread.start()
    
    try:
        print("⏳ Monitoring for 60 seconds...")
        print("   (Press Ctrl+C to stop)")
        print()
        
        start_time = time.time()
        while time.time() - start_time < 60:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped by user")
    
    print("\n📊 Debug Test Complete")
    print("If no Kafka messages were received, the issue is:")
    print("1. Media server not receiving audio tracks")
    print("2. Media server not processing audio through AI pipeline")
    print("3. Kafka service not publishing messages")

if __name__ == "__main__":
    main() 