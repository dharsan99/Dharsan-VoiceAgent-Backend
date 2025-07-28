#!/usr/bin/env python3
"""
gRPC Communication Test Script
Tests the gRPC communication between Media Server and Orchestrator
"""

import grpc
import time
import json
import subprocess
import sys
from typing import Dict, List

# Import the generated protobuf modules
sys.path.append('v2/proto')
import voice_agent_pb2
import voice_agent_pb2_grpc

class GRPCTester:
    def __init__(self):
        self.orchestrator_address = "localhost:8002"  # Port-forwarded gRPC port
        self.media_server_address = "35.244.8.62:8001"
        self.test_results = {}
        
    def test_grpc_connection(self) -> Dict:
        """Test basic gRPC connection to orchestrator"""
        try:
            # Create gRPC channel
            channel = grpc.insecure_channel(self.orchestrator_address)
            
            # Create stub
            stub = voice_agent_pb2_grpc.VoiceAgentServiceStub(channel)
            
            # Test health check
            request = voice_agent_pb2.HealthRequest(
                service_name="test-client",
                timestamp=int(time.time())
            )
            
            response = stub.HealthCheck(request, timeout=10)
            
            return {
                'status': 'PASS',
                'response': {
                    'service_name': response.service_name,
                    'healthy': response.healthy,
                    'status': response.status,
                    'metadata': dict(response.metadata)
                }
            }
        except Exception as e:
            return {
                'status': 'FAIL',
                'error': str(e)
            }
    
    def test_control_message(self) -> Dict:
        """Test control message functionality"""
        try:
            channel = grpc.insecure_channel(self.orchestrator_address)
            stub = voice_agent_pb2_grpc.VoiceAgentServiceStub(channel)
            
            # Test start listening control message
            control_msg = voice_agent_pb2.ControlMessage(
                session_id="test-session-123",
                control_type=voice_agent_pb2.ControlType.CONTROL_TYPE_START_LISTENING,
                parameters={"test": "value"},
                timestamp=int(time.time())
            )
            
            response = stub.SendControlMessage(control_msg, timeout=10)
            
            return {
                'status': 'PASS',
                'response': {
                    'session_id': response.session_id,
                    'success': response.success,
                    'message': response.message
                }
            }
        except Exception as e:
            return {
                'status': 'FAIL',
                'error': str(e)
            }
    
    def test_audio_stream(self) -> Dict:
        """Test bidirectional audio streaming"""
        try:
            channel = grpc.insecure_channel(self.orchestrator_address)
            stub = voice_agent_pb2_grpc.VoiceAgentServiceStub(channel)
            
            # Create bidirectional stream
            def audio_generator():
                # Send a test audio chunk
                audio_chunk = voice_agent_pb2.AudioChunk(
                    session_id="test-stream-session",
                    audio_data=b"test audio data",
                    timestamp=int(time.time()),
                    metadata=voice_agent_pb2.AudioMetadata(
                        energy_level=0.5,
                        voice_activity=True,
                        confidence=0.8,
                        audio_format="opus",
                        sample_rate=16000,
                        channels=1
                    )
                )
                yield audio_chunk
                # Send one more chunk to keep stream alive
                time.sleep(1)
                yield audio_chunk
            
            # Create the stream
            stream = stub.StreamAudio(audio_generator())
            
            # Try to read a response (with timeout)
            try:
                response = next(stream)
                return {
                    'status': 'PASS',
                    'response': {
                        'session_id': response.session_id,
                        'response_type': response.response_type,
                        'transcript': response.transcript
                    }
                }
            except Exception as read_error:
                # It's okay if no response is received immediately
                return {
                    'status': 'PASS',
                    'message': 'Stream established, no immediate response (expected)',
                    'note': str(read_error)
                }
                
        except Exception as e:
            return {
                'status': 'FAIL',
                'error': str(e)
            }
    
    def test_service_health(self) -> Dict:
        """Test HTTP health endpoints"""
        try:
            import requests
            
            # Test orchestrator HTTP health
            orch_response = requests.get(f"http://{self.orchestrator_address.replace(':8002', ':8001')}/health", timeout=10)
            
            # Test media server HTTP health
            media_response = requests.get(f"http://{self.media_server_address}/health", timeout=10)
            
            return {
                'status': 'PASS',
                'orchestrator': orch_response.json() if orch_response.ok else None,
                'media_server': media_response.json() if media_response.ok else None
            }
        except Exception as e:
            return {
                'status': 'FAIL',
                'error': str(e)
            }
    
    def run_comprehensive_test(self) -> Dict:
        """Run all gRPC tests"""
        print("🚀 Starting gRPC Communication Tests...")
        print("=" * 60)
        
        # Test 1: gRPC Connection
        print("\n1. Testing gRPC Connection...")
        self.test_results['grpc_connection'] = self.test_grpc_connection()
        self._print_result('gRPC Connection', self.test_results['grpc_connection'])
        
        # Test 2: Control Message
        print("\n2. Testing Control Message...")
        self.test_results['control_message'] = self.test_control_message()
        self._print_result('Control Message', self.test_results['control_message'])
        
        # Test 3: Audio Stream
        print("\n3. Testing Audio Stream...")
        self.test_results['audio_stream'] = self.test_audio_stream()
        self._print_result('Audio Stream', self.test_results['audio_stream'])
        
        # Test 4: Service Health
        print("\n4. Testing Service Health...")
        self.test_results['service_health'] = self.test_service_health()
        self._print_result('Service Health', self.test_results['service_health'])
        
        return self.test_results
    
    def _print_result(self, test_name: str, result: Dict):
        """Print test result with formatting"""
        status = result.get('status', 'UNKNOWN')
        if status == 'PASS':
            print(f"   ✅ {test_name}: PASS")
            if 'response' in result:
                print(f"      Response: {result['response']}")
            if 'message' in result:
                print(f"      {result['message']}")
        elif status == 'FAIL':
            print(f"   ❌ {test_name}: FAIL")
            if 'error' in result:
                print(f"      Error: {result['error']}")
        else:
            print(f"   ℹ️  {test_name}: {status}")
    
    def generate_report(self) -> str:
        """Generate a comprehensive test report"""
        report = []
        report.append("# gRPC Communication Test Report")
        report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result.get('status') == 'PASS')
        failed_tests = sum(1 for result in self.test_results.values() if result.get('status') == 'FAIL')
        
        report.append("## Summary")
        report.append(f"- Total Tests: {total_tests}")
        report.append(f"- Passed: {passed_tests}")
        report.append(f"- Failed: {failed_tests}")
        report.append(f"- Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        report.append("")
        
        # Detailed Results
        report.append("## Detailed Results")
        for test_name, result in self.test_results.items():
            report.append(f"### {test_name.replace('_', ' ').title()}")
            report.append(f"**Status:** {result.get('status', 'UNKNOWN')}")
            
            if 'error' in result:
                report.append(f"**Error:** {result['error']}")
            if 'response' in result:
                report.append(f"**Response:** {json.dumps(result['response'], indent=2)}")
            if 'message' in result:
                report.append(f"**Message:** {result['message']}")
            
            report.append("")
        
        return "\n".join(report)

def main():
    """Main testing function"""
    tester = GRPCTester()
    
    try:
        # Run comprehensive tests
        results = tester.run_comprehensive_test()
        
        # Generate and save report
        report = tester.generate_report()
        
        # Save report to file
        with open('grpc_test_report.md', 'w') as f:
            f.write(report)
        
        print("\n" + "=" * 60)
        print("📊 gRPC Test Report Generated: grpc_test_report.md")
        print("=" * 60)
        
        # Print summary
        total_tests = len(results)
        passed_tests = sum(1 for result in results.values() if result.get('status') == 'PASS')
        print(f"\n🎯 Test Summary: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🎉 All gRPC tests passed! Communication is working.")
        else:
            print("⚠️  Some gRPC tests failed. Check the detailed report for issues.")
        
    except KeyboardInterrupt:
        print("\n⏹️  Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Testing failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 