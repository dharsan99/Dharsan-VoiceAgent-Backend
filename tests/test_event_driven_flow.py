#!/usr/bin/env python3
"""
Test Event-Driven Flow
Tests the complete event-driven flow including trigger_llm with mock transcript
"""

import asyncio
import json
import websockets
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_event_driven_flow():
    """Test the complete event-driven flow"""
    uri = "ws://34.47.230.178:8001/ws"
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Connected to WebSocket")
            
            # Test 1: Send greeting request
            logger.info("📤 Sending greeting_request")
            await websocket.send(json.dumps({
                "event": "greeting_request"
            }))
            
            # Wait for greeting response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                logger.info(f"📥 Received: {data}")
                
                if data.get("event") == "greeting":
                    logger.info("✅ Greeting received successfully!")
                else:
                    logger.error(f"❌ Unexpected greeting response: {data}")
                    return False
                    
            except asyncio.TimeoutError:
                logger.error("❌ Timeout waiting for greeting response")
                return False
            
            # Test 2: Send start_listening
            session_id = f"test_session_{int(time.time())}"
            logger.info(f"📤 Sending start_listening with session_id: {session_id}")
            await websocket.send(json.dumps({
                "event": "start_listening",
                "session_id": session_id
            }))
            
            # Wait for listening confirmation
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                logger.info(f"📥 Received: {data}")
                
                if data.get("event") == "listening_started" or data.get("type") == "pipeline_state_update":
                    logger.info("✅ Listening started successfully!")
                else:
                    logger.error(f"❌ Unexpected listening response: {data}")
                    return False
                    
            except asyncio.TimeoutError:
                logger.error("❌ Timeout waiting for listening confirmation")
                return False
            
            # Test 3: Send trigger_llm with mock transcript
            mock_transcript = "Hello, this is a test message from the event-driven voice agent."
            logger.info(f"📤 Sending trigger_llm with transcript: {mock_transcript}")
            await websocket.send(json.dumps({
                "event": "trigger_llm",
                "final_transcript": mock_transcript,
                "session_id": session_id
            }))
            
            # Wait for processing responses
            processing_responses = []
            start_time = time.time()
            
            while time.time() - start_time < 30:  # Wait up to 30 seconds
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(response)
                    logger.info(f"📥 Received: {data}")
                    processing_responses.append(data)
                    
                    # Check if we got a complete response
                    if data.get("type") == "pipeline_state_update" and data.get("state") == "complete":
                        logger.info("✅ Processing completed successfully!")
                        break
                        
                except asyncio.TimeoutError:
                    logger.info("⏳ Still waiting for processing to complete...")
                    continue
            
            # Check if we got any processing responses
            if processing_responses:
                logger.info(f"✅ Received {len(processing_responses)} processing responses")
                return True
            else:
                logger.error("❌ No processing responses received")
                return False
                
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}")
        return False

async def main():
    """Main test function"""
    logger.info("🚀 Starting Event-Driven Flow Test")
    
    success = await test_event_driven_flow()
    
    if success:
        logger.info("🎉 Event-Driven Flow Test PASSED!")
    else:
        logger.error("❌ Event-Driven Flow Test FAILED!")
    
    return success

if __name__ == "__main__":
    asyncio.run(main()) 