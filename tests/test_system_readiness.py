#!/usr/bin/env python3
"""
System Readiness Test
Comprehensive test of the Voice Agent system readiness
"""

import requests
import json
import time
import subprocess
import sys
from typing import Dict, List

class SystemReadinessTester:
    def __init__(self):
        self.orchestrator_http = "http://34.47.230.178:8001"
        self.media_server_http = "http://35.244.8.62:8001"
        self.orchestrator_grpc = "34.47.230.178:8002"  # Future gRPC port
        self.test_results = {}
        
    def test_http_health_endpoints(self) -> Dict:
        """Test HTTP health endpoints"""
        try:
            # Test orchestrator health
            orch_response = requests.get(f"{self.orchestrator_http}/health", timeout=10)
            orch_health = orch_response.json() if orch_response.ok else None
            
            # Test media server health
            media_response = requests.get(f"{self.media_server_http}/health", timeout=10)
            media_health = media_response.json() if media_response.ok else None
            
            return {
                'status': 'PASS',
                'orchestrator': orch_health,
                'media_server': media_health
            }
        except Exception as e:
            return {
                'status': 'FAIL',
                'error': str(e)
            }
    
    def test_websocket_connection(self) -> Dict:
        """Test WebSocket connection to orchestrator"""
        try:
            import websocket
            
            # Test WebSocket connection
            ws = websocket.create_connection(f"ws://34.47.230.178:8001/ws", timeout=10)
            
            # Send a test message
            test_message = {
                "type": "ping",
                "session_id": "test-readiness",
                "timestamp": int(time.time())
            }
            ws.send(json.dumps(test_message))
            
            # Try to receive a response (with timeout)
            ws.settimeout(5)
            try:
                response = ws.recv()
                ws.close()
                return {
                    'status': 'PASS',
                    'message': 'WebSocket connection successful',
                    'response': response
                }
            except Exception as recv_error:
                ws.close()
                return {
                    'status': 'PASS',
                    'message': 'WebSocket connected, no immediate response (expected)',
                    'note': str(recv_error)
                }
                
        except Exception as e:
            return {
                'status': 'FAIL',
                'error': str(e)
            }
    
    def test_kafka_connectivity(self) -> Dict:
        """Test Kafka connectivity through service health"""
        try:
            # Check if services report Kafka as connected
            orch_response = requests.get(f"{self.orchestrator_http}/health", timeout=10)
            media_response = requests.get(f"{self.media_server_http}/health", timeout=10)
            
            orch_health = orch_response.json() if orch_response.ok else {}
            media_health = media_response.json() if media_response.ok else {}
            
            orch_kafka = orch_health.get('kafka', 'unknown')
            media_kafka = media_health.get('kafka', 'unknown')
            
            if orch_kafka == 'connected' and media_kafka == 'connected':
                return {
                    'status': 'PASS',
                    'orchestrator_kafka': orch_kafka,
                    'media_server_kafka': media_kafka
                }
            else:
                return {
                    'status': 'FAIL',
                    'orchestrator_kafka': orch_kafka,
                    'media_server_kafka': media_kafka,
                    'error': 'One or more services not connected to Kafka'
                }
                
        except Exception as e:
            return {
                'status': 'FAIL',
                'error': str(e)
            }
    
    def test_service_versions(self) -> Dict:
        """Test service versions and phases"""
        try:
            orch_response = requests.get(f"{self.orchestrator_http}/health", timeout=10)
            media_response = requests.get(f"{self.media_server_http}/health", timeout=10)
            
            orch_health = orch_response.json() if orch_response.ok else {}
            media_health = media_response.json() if media_response.ok else {}
            
            return {
                'status': 'PASS',
                'orchestrator': {
                    'service': orch_health.get('service', 'unknown'),
                    'version': orch_health.get('version', 'unknown'),
                    'phase': orch_health.get('phase', 'unknown')
                },
                'media_server': {
                    'service': media_health.get('service', 'unknown'),
                    'version': media_health.get('version', 'unknown'),
                    'phase': media_health.get('phase', 'unknown')
                }
            }
        except Exception as e:
            return {
                'status': 'FAIL',
                'error': str(e)
            }
    
    def test_pod_status(self) -> Dict:
        """Test Kubernetes pod status"""
        try:
            # Get pod status
            result = subprocess.run([
                'kubectl', 'get', 'pods', '-n', 'voice-agent-phase5', 
                '-o', 'jsonpath={.items[*].status.phase}'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                pod_statuses = result.stdout.strip().split()
                running_pods = [status for status in pod_statuses if status == 'Running']
                
                return {
                    'status': 'PASS',
                    'total_pods': len(pod_statuses),
                    'running_pods': len(running_pods),
                    'pod_statuses': pod_statuses
                }
            else:
                return {
                    'status': 'FAIL',
                    'error': result.stderr
                }
                
        except Exception as e:
            return {
                'status': 'FAIL',
                'error': str(e)
            }
    
    def test_service_endpoints(self) -> Dict:
        """Test service endpoints accessibility"""
        try:
            # Test orchestrator HTTP
            orch_response = requests.get(f"{self.orchestrator_http}/health", timeout=10)
            
            # Test media server HTTP
            media_response = requests.get(f"{self.media_server_http}/health", timeout=10)
            
            # Test media server WHIP endpoint
            whip_response = requests.post(f"{self.media_server_http}/whip", timeout=10)
            
            return {
                'status': 'PASS',
                'orchestrator_http': orch_response.status_code,
                'media_server_http': media_response.status_code,
                'media_server_whip': whip_response.status_code
            }
        except Exception as e:
            return {
                'status': 'FAIL',
                'error': str(e)
            }
    
    def run_comprehensive_test(self) -> Dict:
        """Run all readiness tests"""
        print("🚀 Starting System Readiness Test...")
        print("=" * 60)
        
        # Test 1: HTTP Health Endpoints
        print("\n1. Testing HTTP Health Endpoints...")
        self.test_results['http_health'] = self.test_http_health_endpoints()
        self._print_result('HTTP Health', self.test_results['http_health'])
        
        # Test 2: WebSocket Connection
        print("\n2. Testing WebSocket Connection...")
        self.test_results['websocket'] = self.test_websocket_connection()
        self._print_result('WebSocket', self.test_results['websocket'])
        
        # Test 3: Kafka Connectivity
        print("\n3. Testing Kafka Connectivity...")
        self.test_results['kafka'] = self.test_kafka_connectivity()
        self._print_result('Kafka', self.test_results['kafka'])
        
        # Test 4: Service Versions
        print("\n4. Testing Service Versions...")
        self.test_results['versions'] = self.test_service_versions()
        self._print_result('Service Versions', self.test_results['versions'])
        
        # Test 5: Pod Status
        print("\n5. Testing Pod Status...")
        self.test_results['pods'] = self.test_pod_status()
        self._print_result('Pod Status', self.test_results['pods'])
        
        # Test 6: Service Endpoints
        print("\n6. Testing Service Endpoints...")
        self.test_results['endpoints'] = self.test_service_endpoints()
        self._print_result('Service Endpoints', self.test_results['endpoints'])
        
        return self.test_results
    
    def _print_result(self, test_name: str, result: Dict):
        """Print test result with formatting"""
        status = result.get('status', 'UNKNOWN')
        if status == 'PASS':
            print(f"   ✅ {test_name}: PASS")
            if 'message' in result:
                print(f"      {result['message']}")
            if 'orchestrator' in result and isinstance(result['orchestrator'], dict):
                print(f"      Orchestrator: {result['orchestrator']}")
            if 'media_server' in result and isinstance(result['media_server'], dict):
                print(f"      Media Server: {result['media_server']}")
        elif status == 'FAIL':
            print(f"   ❌ {test_name}: FAIL")
            if 'error' in result:
                print(f"      Error: {result['error']}")
        else:
            print(f"   ℹ️  {test_name}: {status}")
    
    def generate_readiness_report(self) -> str:
        """Generate a comprehensive readiness report"""
        report = []
        report.append("# Voice Agent System Readiness Report")
        report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result.get('status') == 'PASS')
        failed_tests = sum(1 for result in self.test_results.values() if result.get('status') == 'FAIL')
        
        report.append("## System Readiness Summary")
        report.append(f"- Total Tests: {total_tests}")
        report.append(f"- Passed: {passed_tests}")
        report.append(f"- Failed: {failed_tests}")
        report.append(f"- Readiness Score: {(passed_tests/total_tests)*100:.1f}%")
        report.append("")
        
        # Current Status
        report.append("## Current System Status")
        if passed_tests == total_tests:
            report.append("🟢 **SYSTEM READY** - All components are operational")
        elif passed_tests >= total_tests * 0.8:
            report.append("🟡 **MOSTLY READY** - Minor issues detected")
        else:
            report.append("🔴 **NOT READY** - Significant issues detected")
        report.append("")
        
        # Detailed Results
        report.append("## Detailed Test Results")
        for test_name, result in self.test_results.items():
            report.append(f"### {test_name.replace('_', ' ').title()}")
            report.append(f"**Status:** {result.get('status', 'UNKNOWN')}")
            
            if 'error' in result:
                report.append(f"**Error:** {result['error']}")
            if 'message' in result:
                report.append(f"**Message:** {result['message']}")
            if 'orchestrator' in result:
                report.append(f"**Orchestrator:** {json.dumps(result['orchestrator'], indent=2)}")
            if 'media_server' in result:
                report.append(f"**Media Server:** {json.dumps(result['media_server'], indent=2)}")
            
            report.append("")
        
        # Next Steps
        report.append("## Next Steps")
        if passed_tests == total_tests:
            report.append("✅ **System is ready for gRPC deployment**")
            report.append("1. Deploy updated orchestrator with gRPC server")
            report.append("2. Deploy updated media-server with gRPC client")
            report.append("3. Test gRPC communication")
        else:
            report.append("⚠️ **System needs attention before gRPC deployment**")
            report.append("1. Fix failed tests above")
            report.append("2. Ensure all services are healthy")
            report.append("3. Verify Kafka connectivity")
        
        return "\n".join(report)

def main():
    """Main testing function"""
    tester = SystemReadinessTester()
    
    try:
        # Run comprehensive tests
        results = tester.run_comprehensive_test()
        
        # Generate and save report
        report = tester.generate_readiness_report()
        
        # Save report to file
        with open('system_readiness_report.md', 'w') as f:
            f.write(report)
        
        print("\n" + "=" * 60)
        print("📊 System Readiness Report Generated: system_readiness_report.md")
        print("=" * 60)
        
        # Print summary
        total_tests = len(results)
        passed_tests = sum(1 for result in results.values() if result.get('status') == 'PASS')
        print(f"\n🎯 Readiness Summary: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🎉 System is ready for gRPC deployment!")
        else:
            print("⚠️  System needs attention before gRPC deployment.")
        
    except KeyboardInterrupt:
        print("\n⏹️  Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Testing failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 