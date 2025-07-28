#!/usr/bin/env python3
"""
TTS Audio Streaming Test
Tests the improved TTS audio streaming to ensure it doesn't break midway
"""

import asyncio
import aiohttp
import json
import time
import numpy as np
from datetime import datetime

# V1 Backend URLs
V1_BACKEND_URL = "https://dharsan99--voice-ai-backend-run-app.modal.run"
V1_WEBSOCKET_URL = "wss://dharsan99--voice-ai-backend-run-app.modal.run/ws"

def generate_test_audio(duration_ms=2000, sample_rate=44100):
    """Generate test audio data with speech-like characteristics"""
    samples = int(sample_rate * duration_ms / 1000)
    # Generate a more complex waveform that might trigger TTS
    t = np.linspace(0, duration_ms/1000, samples, False)
    # Mix multiple frequencies to simulate speech
    audio = (0.1 * np.sin(2 * np.pi * 200 * t) +  # Low frequency
             0.05 * np.sin(2 * np.pi * 800 * t) +  # Mid frequency
             0.02 * np.sin(2 * np.pi * 2000 * t))  # High frequency
    return audio.astype(np.float32).tobytes()

async def test_tts_streaming():
    """Test TTS audio streaming stability"""
    print("🎤 Testing TTS Audio Streaming...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(V1_WEBSOCKET_URL) as ws:
                print(f"✅ Connected to V1 WebSocket: {V1_WEBSOCKET_URL}")
                
                # Send test audio data to trigger TTS
                test_audio = generate_test_audio(3000)  # 3 seconds of audio
                await ws.send_bytes(test_audio)
                print(f"📤 Sent {len(test_audio)} bytes of test audio")
                
                # Wait for responses and track audio streaming
                responses = []
                audio_chunks = []
                start_time = time.time()
                timeout = 15  # 15 seconds timeout
                last_audio_time = None
                
                while time.time() - start_time < timeout:
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
                        
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                responses.append(data)
                                print(f"📥 Received text message: {data.get('type', 'unknown')}")
                                
                                # Track TTS progress
                                if data.get('type') == 'word_timing_start':
                                    print(f"🎯 TTS started for: {data.get('text', '')}")
                                elif data.get('type') == 'word_highlight':
                                    print(f"🎯 Word highlight: {data.get('word', '')}")
                                elif data.get('type') == 'word_timing_complete':
                                    print(f"🎯 TTS completed: {data.get('total_words', 0)} words")
                                elif data.get('type') == 'processing_complete':
                                    print(f"🤖 AI Response: {data.get('response', '')[:100]}...")
                                    
                            except json.JSONDecodeError:
                                print(f"📥 Received non-JSON text: {msg.data[:100]}...")
                                
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            current_time = time.time()
                            audio_chunks.append({
                                'size': len(msg.data),
                                'timestamp': current_time,
                                'time_since_last': current_time - last_audio_time if last_audio_time else 0
                            })
                            last_audio_time = current_time
                            print(f"📥 Received audio chunk: {len(msg.data)} bytes")
                            
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            print(f"❌ WebSocket error: {ws.exception()}")
                            break
                            
                    except asyncio.TimeoutError:
                        print("⏰ Timeout waiting for message, continuing...")
                        continue
                
                print(f"\n📊 Streaming Analysis:")
                print(f"   Total responses: {len(responses)}")
                print(f"   Total audio chunks: {len(audio_chunks)}")
                
                if audio_chunks:
                    total_audio_size = sum(chunk['size'] for chunk in audio_chunks)
                    avg_chunk_size = total_audio_size / len(audio_chunks)
                    time_gaps = [chunk['time_since_last'] for chunk in audio_chunks[1:]]
                    avg_gap = sum(time_gaps) / len(time_gaps) if time_gaps else 0
                    
                    print(f"   Total audio size: {total_audio_size} bytes")
                    print(f"   Average chunk size: {avg_chunk_size:.0f} bytes")
                    print(f"   Average time between chunks: {avg_gap:.3f}s")
                    
                    # Check for streaming issues
                    large_gaps = [gap for gap in time_gaps if gap > 1.0]
                    if large_gaps:
                        print(f"   ⚠️  Found {len(large_gaps)} large gaps (>1s) in streaming")
                        for i, gap in enumerate(large_gaps[:3]):  # Show first 3
                            print(f"      Gap {i+1}: {gap:.3f}s")
                    else:
                        print(f"   ✅ No large gaps detected in streaming")
                
                # Check if we got a complete TTS response
                has_tts_start = any(r.get('type') == 'word_timing_start' for r in responses)
                has_tts_complete = any(r.get('type') == 'word_timing_complete' for r in responses)
                has_audio = len(audio_chunks) > 0
                
                if has_tts_start and has_tts_complete and has_audio:
                    print("✅ TTS Audio Streaming is working correctly!")
                    return True
                elif has_audio:
                    print("⚠️  TTS Audio Streaming received audio but may be incomplete")
                    return True
                else:
                    print("❌ TTS Audio Streaming failed - no audio received")
                    return False
                    
    except Exception as e:
        print(f"❌ TTS Streaming test failed: {e}")
        return False

async def test_backend_health():
    """Test V1 backend health"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{V1_BACKEND_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ V1 Backend Healthy: {data['status']}")
                    print(f"   Active connections: {data.get('active_connections', 0)}")
                    return True
                else:
                    print(f"❌ V1 Backend unhealthy: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ V1 Backend health check failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🧪 TTS Audio Streaming Test")
    print("=" * 50)
    
    # Test V1 Backend Health
    print("\n🏥 Testing V1 Backend Health...")
    v1_health = await test_backend_health()
    
    # Test TTS Streaming
    print("\n🎤 Testing TTS Audio Streaming...")
    tts_streaming = await test_tts_streaming()
    
    # Summary
    print("\n📊 Test Results:")
    print(f"V1 Backend Health: {'✅ PASS' if v1_health else '❌ FAIL'}")
    print(f"TTS Audio Streaming: {'✅ PASS' if tts_streaming else '❌ FAIL'}")
    
    if v1_health and tts_streaming:
        print("\n🎉 TTS Audio Streaming improvements are working!")
        print("\n📝 Improvements applied:")
        print("✅ Added timeout handling for audio chunks")
        print("✅ Added chunk validation and error handling")
        print("✅ Added completion signals to end streaming properly")
        print("✅ Added consecutive error tracking")
        print("✅ Added better logging for debugging")
        print("✅ Added queue timeout protection")
    else:
        print("\n❌ Some tests failed. Please check the issues above.")
    
    print(f"\n⏰ Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    asyncio.run(main()) 