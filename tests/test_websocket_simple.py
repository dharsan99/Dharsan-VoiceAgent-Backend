#!/usr/bin/env python3
"""
Simple WebSocket test for the event-driven orchestrator
"""

import asyncio
import json
import websockets
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_websocket():
    """Test basic WebSocket communication"""
    uri = "ws://34.47.230.178:8001/ws"
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Connected to WebSocket")
            
            # Test 1: Send greeting request
            logger.info("📤 Sending greeting_request")
            await websocket.send(json.dumps({
                "event": "greeting_request"
            }))
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"📥 Received: {response}")
                
                # Parse response
                data = json.loads(response)
                if data.get("event") == "greeting":
                    logger.info("✅ Greeting response received successfully!")
                else:
                    logger.error(f"❌ Unexpected response: {data}")
                    
            except asyncio.TimeoutError:
                logger.error("❌ Timeout waiting for greeting response")
            
            # Test 2: Send start_listening
            logger.info("📤 Sending start_listening")
            await websocket.send(json.dumps({
                "event": "start_listening",
                "session_id": "test_session_simple"
            }))
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"📥 Received: {response}")
                
                # Parse response
                data = json.loads(response)
                if data.get("event") == "listening_started":
                    logger.info("✅ Listening started response received successfully!")
                else:
                    logger.error(f"❌ Unexpected response: {data}")
                    
            except asyncio.TimeoutError:
                logger.error("❌ Timeout waiting for listening_started response")
            
            # Test 3: Send trigger_llm
            logger.info("📤 Sending trigger_llm")
            await websocket.send(json.dumps({
                "event": "trigger_llm",
                "final_transcript": "Hello, this is a simple test",
                "session_id": "test_session_simple"
            }))
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"📥 Received: {response}")
                
                # Parse response
                data = json.loads(response)
                logger.info(f"✅ Trigger LLM response received: {data.get('event', 'unknown')}")
                    
            except asyncio.TimeoutError:
                logger.error("❌ Timeout waiting for trigger_llm response")
            
            logger.info("🔌 Closing connection")
            
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket()) 