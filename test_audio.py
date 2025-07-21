#!/usr/bin/env python3
"""
Test script to verify audio generation and sending
"""

import asyncio
import websockets
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_audio_generation():
    """Test audio generation and sending"""
    
    # Test WebSocket URL (replace with your actual URL)
    websocket_url = "wss://your-modal-app.modal.run/ws"
    
    try:
        async with websockets.connect(websocket_url) as websocket:
            logger.info("Connected to WebSocket")
            
            # Send a test message to trigger audio generation
            test_message = {
                "type": "test",
                "text": "Hello, this is a test message for audio generation."
            }
            
            await websocket.send(json.dumps(test_message))
            logger.info("Sent test message")
            
            # Listen for responses
            message_count = 0
            audio_chunks_received = 0
            
            while message_count < 10:  # Limit to prevent infinite loop
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    message_count += 1
                    
                    if isinstance(message, str):
                        # Text message
                        try:
                            data = json.loads(message)
                            logger.info(f"Received text message: {data.get('type', 'unknown')}")
                        except json.JSONDecodeError:
                            logger.info(f"Received plain text: {message}")
                    else:
                        # Binary message (audio)
                        audio_chunks_received += 1
                        logger.info(f"Received audio chunk #{audio_chunks_received}, size: {len(message)} bytes")
                        
                except asyncio.TimeoutError:
                    logger.info("Timeout waiting for message")
                    break
                    
            logger.info(f"Test completed. Received {audio_chunks_received} audio chunks")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_audio_generation()) 