#!/usr/bin/env python3
"""
TTS Pinpoint Logging Test
Tests the pinpoint logging to identify exactly where TTS audio breaks
"""

import asyncio
import aiohttp
import json
import time
import numpy as np
from datetime import datetime

# URLs
V1_BACKEND_URL = "https://dharsan99--voice-ai-backend-run-app.modal.run"
V1_WEBSOCKET_URL = "wss://dharsan99--voice-ai-backend-run-app.modal.run/ws"
FRONTEND_URL = "http://localhost:5173"

def generate_test_audio(duration_ms=3000, sample_rate=44100):
    """Generate test audio data with speech-like characteristics"""
    samples = int(sample_rate * duration_ms / 1000)
    t = np.linspace(0, duration_ms/1000, samples, False)
    # Mix multiple frequencies to simulate speech
    audio = (0.1 * np.sin(2 * np.pi * 200 * t) +  # Low frequency
             0.05 * np.sin(2 * np.pi * 800 * t) +  # Mid frequency
             0.02 * np.sin(2 * np.pi * 2000 * t))  # High frequency
    return audio.astype(np.float32).tobytes()

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

async def test_tts_pinpoint_logging():
    """Test TTS with pinpoint logging to identify breaks"""
    print("🔍 Testing TTS Pinpoint Logging...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(V1_WEBSOCKET_URL) as ws:
                print(f"✅ Connected to V1 WebSocket: {V1_WEBSOCKET_URL}")
                
                # Send test audio data to trigger TTS
                test_audio = generate_test_audio(3000)  # 3 seconds of audio
                await ws.send_bytes(test_audio)
                print(f"📤 Sent {len(test_audio)} bytes of test audio")
                
                # Wait for responses and track with pinpoint logging
                responses = []
                audio_chunks = []
                start_time = time.time()
                timeout = 30  # 30 seconds timeout for comprehensive logging
                last_audio_time = None
                word_timing_started = False
                word_timing_completed = False
                processing_complete = False
                
                print("\n🔍 TTS PINPOINT LOGGING STARTED - Watch for breaks:")
                print("=" * 80)
                
                while time.time() - start_time < timeout:
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                        
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                responses.append(data)
                                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                                
                                # Track TTS progress with pinpoint logging
                                if data.get('type') == 'word_timing_start':
                                    word_timing_started = True
                                    print(f"🔍 [{timestamp}] TTS STARTED: {data.get('text', '')[:50]}...")
                                elif data.get('type') == 'word_highlight':
                                    print(f"🔍 [{timestamp}] WORD: {data.get('word', '')} at {data.get('timestamp', 0):.3f}s")
                                elif data.get('type') == 'word_timing_complete':
                                    word_timing_completed = True
                                    print(f"🔍 [{timestamp}] TTS COMPLETED: {data.get('total_words', 0)} words")
                                elif data.get('type') == 'processing_complete':
                                    processing_complete = True
                                    print(f"🔍 [{timestamp}] AI RESPONSE: {data.get('response', '')[:100]}...")
                                else:
                                    print(f"🔍 [{timestamp}] MESSAGE: {data.get('type', 'unknown')}")
                                    
                            except json.JSONDecodeError:
                                print(f"🔍 [{timestamp}] NON-JSON: {msg.data[:100]}...")
                                
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            current_time = time.time()
                            audio_chunks.append({
                                'size': len(msg.data),
                                'timestamp': current_time,
                                'time_since_last': current_time - last_audio_time if last_audio_time else 0
                            })
                            last_audio_time = current_time
                            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                            print(f"🔍 [{timestamp}] AUDIO CHUNK: {len(msg.data)} bytes")
                            
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                            print(f"🔍 [{timestamp}] WEBSOCKET ERROR: {ws.exception()}")
                            break
                            
                    except asyncio.TimeoutError:
                        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        print(f"🔍 [{timestamp}] TIMEOUT: No message received")
                        continue
                
                print("=" * 80)
                print("🔍 TTS PINPOINT LOGGING COMPLETED")
                
                # Analysis
                print(f"\n📊 TTS Analysis:")
                print(f"   Total responses: {len(responses)}")
                print(f"   Total audio chunks: {len(audio_chunks)}")
                print(f"   Word timing started: {word_timing_started}")
                print(f"   Word timing completed: {word_timing_completed}")
                print(f"   Processing complete: {processing_complete}")
                
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
                        for i, gap in enumerate(large_gaps[:5]):  # Show first 5
                            print(f"      Gap {i+1}: {gap:.3f}s")
                    else:
                        print(f"   ✅ No large gaps detected in streaming")
                
                # Check if we got a complete TTS response
                has_tts_start = word_timing_started
                has_tts_complete = word_timing_completed
                has_audio = len(audio_chunks) > 0
                
                if has_tts_start and has_tts_complete and has_audio:
                    print("✅ TTS Pinpoint Logging shows complete audio streaming!")
                    return True
                elif has_audio:
                    print("⚠️  TTS Pinpoint Logging shows audio but may be incomplete")
                    return True
                else:
                    print("❌ TTS Pinpoint Logging shows no audio received")
                    return False
                    
    except Exception as e:
        print(f"❌ TTS Pinpoint Logging test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🔍 TTS Pinpoint Logging Test")
    print("=" * 60)
    
    # Test V1 Backend Health
    print("\n🏥 Testing V1 Backend Health...")
    backend_health = await test_backend_health()
    
    # Test TTS Pinpoint Logging
    print("\n🔍 Testing TTS Pinpoint Logging...")
    tts_logging = await test_tts_pinpoint_logging()
    
    # Summary
    print("\n📊 Test Results:")
    print(f"V1 Backend Health: {'✅ PASS' if backend_health else '❌ FAIL'}")
    print(f"TTS Pinpoint Logging: {'✅ PASS' if tts_logging else '❌ FAIL'}")
    
    if backend_health and tts_logging:
        print("\n🎉 TTS Pinpoint Logging is working!")
        print("\n📝 Next Steps:")
        print("1. Open the frontend at http://localhost:5173")
        print("2. Open browser console (F12)")
        print("3. Speak into the microphone")
        print("4. Watch for 🔍 TTS PINPOINT logs in console")
        print("5. Look for any breaks in the audio streaming")
    else:
        print("\n❌ Some tests failed. Please check the issues above.")
    
    print(f"\n⏰ Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    asyncio.run(main()) 