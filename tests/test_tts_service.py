#!/usr/bin/env python3
"""
Test TTS Service Directly
Tests the TTS service to see what it's actually returning
"""

import requests
import base64
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_tts_service():
    """Test the TTS service directly"""
    tts_url = "http://localhost:5000"  # TTS service via port-forward
    
    # Test 1: Health check
    logger.info("Testing TTS service health...")
    try:
        health_response = requests.get(f"{tts_url}/health", timeout=10)
        logger.info(f"Health check status: {health_response.status_code}")
        if health_response.status_code == 200:
            health_data = health_response.json()
            logger.info(f"Health data: {health_data}")
        else:
            logger.error(f"Health check failed: {health_response.text}")
            return False
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return False
    
    # Test 2: Simple synthesis
    logger.info("Testing TTS synthesis...")
    test_text = "Hello, this is a test message."
    
    try:
        # Use GET endpoint
        synthesis_url = f"{tts_url}/synthesize?text={test_text}&voice=en_US-lessac-high&speed=1.0&format=wav"
        logger.info(f"Sending request to: {synthesis_url}")
        
        synthesis_response = requests.get(synthesis_url, timeout=30)
        logger.info(f"Synthesis status: {synthesis_response.status_code}")
        logger.info(f"Response headers: {dict(synthesis_response.headers)}")
        
        if synthesis_response.status_code == 200:
            audio_data = synthesis_response.content
            logger.info(f"Audio data size: {len(audio_data)} bytes")
            
            if len(audio_data) > 0:
                # Convert to base64 for logging
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                logger.info(f"Audio data (first 100 chars): {audio_base64[:100]}...")
                
                # Save audio file for testing
                with open("test_audio.wav", "wb") as f:
                    f.write(audio_data)
                logger.info("Audio saved to test_audio.wav")
                return True
            else:
                logger.error("No audio data received")
                return False
        else:
            logger.error(f"Synthesis failed: {synthesis_response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Synthesis error: {e}")
        return False

def test_tts_post_endpoint():
    """Test the POST endpoint for comparison"""
    tts_url = "http://localhost:5000"
    test_text = "Hello, this is a test message."
    
    logger.info("Testing TTS POST endpoint...")
    
    try:
        # Use POST endpoint
        synthesis_data = {
            "text": test_text,
            "voice": "en_US-lessac-high",
            "speed": 1.0,
            "format": "wav"
        }
        
        synthesis_response = requests.post(f"{tts_url}/synthesize", json=synthesis_data, timeout=30)
        logger.info(f"POST synthesis status: {synthesis_response.status_code}")
        
        if synthesis_response.status_code == 200:
            response_data = synthesis_response.json()
            logger.info(f"POST response: {response_data}")
            return True
        else:
            logger.error(f"POST synthesis failed: {synthesis_response.text}")
            return False
            
    except Exception as e:
        logger.error(f"POST synthesis error: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 Starting TTS Service Test")
    
    # Test health
    if not test_tts_service():
        logger.error("❌ TTS service test failed")
        exit(1)
    
    # Test POST endpoint for comparison
    test_tts_post_endpoint()
    
    logger.info("✅ TTS service test completed") 