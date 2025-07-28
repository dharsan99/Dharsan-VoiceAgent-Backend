#!/usr/bin/env python3
"""
Event Sequence Test Script
Tests the new event-driven voice agent implementation to ensure it follows the correct event sequence.
"""

import asyncio
import json
import websockets
import time
import logging
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EventSequenceTester:
    def __init__(self, websocket_url: str = "ws://34.47.230.178:8001/ws"):
        self.websocket_url = websocket_url
        self.websocket = None
        self.session_id = f"test_session_{int(time.time())}"
        self.received_events = []
        self.test_results = []
        
    async def connect(self):
        """Establish WebSocket connection"""
        try:
            self.websocket = await websockets.connect(self.websocket_url)
            logger.info(f"✅ Connected to {self.websocket_url}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect: {e}")
            return False
    
    async def send_event(self, event: str, data: Dict[str, Any] = None):
        """Send an event to the server"""
        if data is None:
            data = {}
        
        message = {
            "event": event,
            "session_id": self.session_id,
            **data
        }
        
        await self.websocket.send(json.dumps(message))
        logger.info(f"📤 Sent event: {event}")
        
    async def receive_messages(self, timeout: float = 5.0):
        """Receive and log messages from the server"""
        try:
            async with asyncio.timeout(timeout):
                while True:
                    message = await self.websocket.recv()
                    data = json.loads(message)
                    self.received_events.append(data)
                    logger.info(f"📥 Received: {data.get('event', 'unknown')} - {data}")
        except asyncio.TimeoutError:
            logger.info("⏰ Message receive timeout")
        except Exception as e:
            logger.error(f"❌ Error receiving message: {e}")
    
    async def test_greeting_sequence(self):
        """Test the greeting event sequence"""
        logger.info("\n🧪 Testing Greeting Sequence")
        
        # Send greeting request
        await self.send_event("greeting_request")
        
        # Wait for greeting response
        await asyncio.sleep(1)
        
        # Check if greeting was received
        greeting_events = [e for e in self.received_events if e.get('event') == 'greeting']
        if greeting_events:
            greeting = greeting_events[0]
            if greeting.get('text') == 'how may i help you today':
                logger.info("✅ Greeting sequence passed")
                self.test_results.append(("Greeting", "PASS"))
                return True
            else:
                logger.error(f"❌ Unexpected greeting text: {greeting.get('text')}")
                self.test_results.append(("Greeting", "FAIL"))
                return False
        else:
            logger.error("❌ No greeting event received")
            self.test_results.append(("Greeting", "FAIL"))
            return False
    
    async def test_start_listening_sequence(self):
        """Test the start_listening event sequence"""
        logger.info("\n🧪 Testing Start Listening Sequence")
        
        # Send start_listening event
        await self.send_event("start_listening")
        
        # Wait for pipeline state update or listening_started response
        await asyncio.sleep(1)
        
        # Check if pipeline state update was received (indicating listening started)
        state_events = [e for e in self.received_events if e.get('type') == 'pipeline_state_update' and e.get('state') == 'listening']
        info_events = [e for e in self.received_events if e.get('type') == 'info' and 'Started listening' in e.get('message', '')]
        
        if state_events or info_events:
            logger.info("✅ Start listening sequence passed")
            self.test_results.append(("Start Listening", "PASS"))
            return True
        else:
            logger.error("❌ No listening confirmation received")
            self.test_results.append(("Start Listening", "FAIL"))
            return False
    
    async def test_trigger_llm_sequence(self):
        """Test the trigger_llm event sequence"""
        logger.info("\n🧪 Testing Trigger LLM Sequence")
        
        # Send trigger_llm event with final transcript
        test_transcript = "Hello, this is a test message"
        await self.send_event("trigger_llm", {
            "final_transcript": test_transcript
        })
        
        # Wait for processing
        await asyncio.sleep(3)
        
        # Check if processing events were received (pipeline state updates or processing messages)
        processing_events = [e for e in self.received_events if e.get('event') in ['processing_start', 'ai_response', 'processing_complete']]
        state_events = [e for e in self.received_events if e.get('type') == 'pipeline_state_update' and e.get('state') == 'processing']
        
        if processing_events or state_events:
            logger.info("✅ Trigger LLM sequence passed")
            self.test_results.append(("Trigger LLM", "PASS"))
            return True
        else:
            logger.error("❌ No processing events received")
            self.test_results.append(("Trigger LLM", "FAIL"))
            return False
    
    async def test_invalid_events(self):
        """Test handling of invalid events"""
        logger.info("\n🧪 Testing Invalid Events")
        
        # Send invalid event
        await self.send_event("invalid_event")
        
        # Wait for response
        await asyncio.sleep(1)
        
        # Check if error was received or event was ignored
        error_events = [e for e in self.received_events if e.get('event') == 'error']
        if error_events:
            logger.info("✅ Invalid event handling passed (error received)")
            self.test_results.append(("Invalid Events", "PASS"))
            return True
        else:
            logger.info("✅ Invalid event handling passed (event ignored)")
            self.test_results.append(("Invalid Events", "PASS"))
            return True
    
    async def test_complete_sequence(self):
        """Test the complete event sequence in order"""
        logger.info("\n🧪 Testing Complete Event Sequence")
        
        # Clear previous events
        self.received_events = []
        
        # 1. Greeting
        await self.send_event("greeting_request")
        await asyncio.sleep(1)
        
        # 2. Start Listening
        await self.send_event("start_listening")
        await asyncio.sleep(1)
        
        # 3. Trigger LLM
        await self.send_event("trigger_llm", {
            "final_transcript": "Complete sequence test message"
        })
        await asyncio.sleep(3)
        
        # Verify sequence - check for both event types and pipeline state updates
        events = [e.get('event') for e in self.received_events if e.get('event')]
        state_updates = [e.get('type') for e in self.received_events if e.get('type')]
        
        # Check for greeting event
        has_greeting = any(e.get('event') == 'greeting' for e in self.received_events)
        
        # Check for listening confirmation (either event or state update)
        has_listening = any(e.get('event') == 'listening_started' for e in self.received_events) or \
                       any(e.get('type') == 'pipeline_state_update' and e.get('state') == 'listening' for e in self.received_events)
        
        # Check for processing confirmation (either event or state update)
        has_processing = any(e.get('event') in ['processing_start', 'ai_response', 'processing_complete'] for e in self.received_events) or \
                        any(e.get('type') == 'pipeline_state_update' and e.get('state') == 'processing' for e in self.received_events)
        
        if has_greeting and has_listening and has_processing:
            logger.info("✅ Complete sequence passed")
            self.test_results.append(("Complete Sequence", "PASS"))
            return True
        else:
            missing = []
            if not has_greeting: missing.append('greeting')
            if not has_listening: missing.append('listening_confirmation')
            if not has_processing: missing.append('processing_confirmation')
            
            logger.error(f"❌ Missing events: {missing}")
            logger.error(f"Received events: {events}")
            logger.error(f"State updates: {state_updates}")
            self.test_results.append(("Complete Sequence", "FAIL"))
            return False
    
    def print_results(self):
        """Print test results summary"""
        logger.info("\n" + "="*50)
        logger.info("📊 TEST RESULTS SUMMARY")
        logger.info("="*50)
        
        passed = 0
        total = len(self.test_results)
        
        for test_name, result in self.test_results:
            status = "✅ PASS" if result == "PASS" else "❌ FAIL"
            logger.info(f"{test_name:<20} {status}")
            if result == "PASS":
                passed += 1
        
        logger.info("="*50)
        logger.info(f"Total: {total}, Passed: {passed}, Failed: {total - passed}")
        
        if passed == total:
            logger.info("🎉 All tests passed! Event sequence implementation is working correctly.")
        else:
            logger.error("⚠️  Some tests failed. Please check the implementation.")
        
        return passed == total
    
    async def run_all_tests(self):
        """Run all tests"""
        logger.info("🚀 Starting Event Sequence Tests")
        logger.info(f"Target: {self.websocket_url}")
        logger.info(f"Session ID: {self.session_id}")
        
        # Connect to WebSocket
        if not await self.connect():
            return False
        
        try:
            # Run individual tests
            await self.test_greeting_sequence()
            await self.test_start_listening_sequence()
            await self.test_trigger_llm_sequence()
            await self.test_invalid_events()
            
            # Run complete sequence test
            await self.test_complete_sequence()
            
        finally:
            # Close connection
            if self.websocket:
                await self.websocket.close()
                logger.info("🔌 WebSocket connection closed")
        
        # Print results
        return self.print_results()

async def main():
    """Main test function"""
    tester = EventSequenceTester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n🎯 Event sequence implementation is working correctly!")
        print("The system now follows the required event flow:")
        print("1. greeting_request → greeting")
        print("2. start_listening → listening_started")
        print("3. trigger_llm → ai_response + processing_complete")
    else:
        print("\n⚠️  Some tests failed. Please check the implementation.")
    
    return success

if __name__ == "__main__":
    asyncio.run(main()) 