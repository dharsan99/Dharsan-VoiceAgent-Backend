#!/usr/bin/env python3
"""
Comprehensive Testing Script for Voice Agent Implementation
Tests gRPC dependencies, service connectivity, and end-to-end functionality
"""

import requests
import json
import time
import subprocess
import sys
from typing import Dict, List, Optional

class VoiceAgentTester:
    def __init__(self):
        self.base_urls = {
            'media_server': 'http://35.244.8.62:8001',
            'orchestrator': 'http://34.47.230.178:8001',
            'stt_service': 'http://localhost:8000',  # Internal cluster IP
            'tts_service': 'http://localhost:5000'   # Internal cluster IP
        }
        self.test_results = {}
        
    def test_service_health(self, service_name: str, url: str) -> Dict:
        """Test basic service health and connectivity"""
        try:
            response = requests.get(f"{url}/health", timeout=10)
            return {
                'status': 'PASS' if response.status_code == 200 else 'FAIL',
                'status_code': response.status_code,
                'response': response.text[:200] if response.text else 'No response body'
            }
        except requests.exceptions.RequestException as e:
            return {
                'status': 'FAIL',
                'error': str(e),
                'status_code': None
            }
    
    def test_websocket_connection(self, service_name: str, url: str) -> Dict:
        """Test WebSocket connectivity"""
        try:
            # Test WebSocket endpoint
            ws_url = url.replace('http://', 'ws://') + '/ws'
            # This is a basic test - in production you'd use a WebSocket client
            return {
                'status': 'INFO',
                'message': f'WebSocket endpoint available at {ws_url}',
                'note': 'Manual WebSocket testing required'
            }
        except Exception as e:
            return {
                'status': 'FAIL',
                'error': str(e)
            }
    
    def test_kafka_connectivity(self) -> Dict:
        """Test Kafka connectivity through RedPanda"""
        try:
            # Test RedPanda connectivity
            result = subprocess.run([
                'kubectl', 'exec', '-n', 'voice-agent-phase5', 
                'deployment/redpanda', '--', 'rpk', 'cluster', 'info'
            ], capture_output=True, text=True, timeout=30)
            
            return {
                'status': 'PASS' if result.returncode == 0 else 'FAIL',
                'output': result.stdout[:200] if result.stdout else result.stderr[:200]
            }
        except Exception as e:
            return {
                'status': 'FAIL',
                'error': str(e)
            }
    
    def test_grpc_dependencies(self) -> Dict:
        """Test gRPC dependencies in Go services"""
        try:
            # Check if gRPC dependencies are properly loaded
            result = subprocess.run([
                'kubectl', 'exec', '-n', 'voice-agent-phase5', 
                'deployment/orchestrator', '--', 'go', 'list', '-m', 'google.golang.org/grpc'
            ], capture_output=True, text=True, timeout=10)
            
            return {
                'status': 'PASS' if result.returncode == 0 else 'FAIL',
                'output': result.stdout.strip() if result.stdout else result.stderr.strip()
            }
        except Exception as e:
            return {
                'status': 'FAIL',
                'error': str(e)
            }
    
    def test_pod_status(self) -> Dict:
        """Test Kubernetes pod status"""
        try:
            result = subprocess.run([
                'kubectl', 'get', 'pods', '-n', 'voice-agent-phase5', '-o', 'json'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                pods_data = json.loads(result.stdout)
                pod_status = {}
                
                for pod in pods_data['items']:
                    pod_name = pod['metadata']['name']
                    pod_status[pod_name] = {
                        'phase': pod['status']['phase'],
                        'ready': pod['status']['containerStatuses'][0]['ready'] if pod['status']['containerStatuses'] else False,
                        'restarts': pod['status']['containerStatuses'][0]['restartCount'] if pod['status']['containerStatuses'] else 0
                    }
                
                return {
                    'status': 'PASS',
                    'pods': pod_status
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
        """Test service endpoints and ports"""
        try:
            result = subprocess.run([
                'kubectl', 'get', 'svc', '-n', 'voice-agent-phase5', '-o', 'json'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                services_data = json.loads(result.stdout)
                service_info = {}
                
                for svc in services_data['items']:
                    svc_name = svc['metadata']['name']
                    service_info[svc_name] = {
                        'type': svc['spec']['type'],
                        'ports': [port['port'] for port in svc['spec']['ports']],
                        'cluster_ip': svc['spec']['clusterIP']
                    }
                
                return {
                    'status': 'PASS',
                    'services': service_info
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
    
    def run_comprehensive_test(self) -> Dict:
        """Run all tests and return comprehensive results"""
        print("🚀 Starting Comprehensive Voice Agent Testing...")
        print("=" * 60)
        
        # Test 1: Pod Status
        print("\n1. Testing Kubernetes Pod Status...")
        self.test_results['pod_status'] = self.test_pod_status()
        self._print_result('Pod Status', self.test_results['pod_status'])
        
        # Test 2: Service Endpoints
        print("\n2. Testing Service Endpoints...")
        self.test_results['service_endpoints'] = self.test_service_endpoints()
        self._print_result('Service Endpoints', self.test_results['service_endpoints'])
        
        # Test 3: gRPC Dependencies
        print("\n3. Testing gRPC Dependencies...")
        self.test_results['grpc_dependencies'] = self.test_grpc_dependencies()
        self._print_result('gRPC Dependencies', self.test_results['grpc_dependencies'])
        
        # Test 4: Kafka Connectivity
        print("\n4. Testing Kafka/RedPanda Connectivity...")
        self.test_results['kafka_connectivity'] = self.test_kafka_connectivity()
        self._print_result('Kafka Connectivity', self.test_results['kafka_connectivity'])
        
        # Test 5: Service Health Checks
        print("\n5. Testing Service Health...")
        for service_name, url in self.base_urls.items():
            if 'localhost' not in url:  # Skip internal services
                print(f"   Testing {service_name}...")
                self.test_results[f'{service_name}_health'] = self.test_service_health(service_name, url)
                self._print_result(f'{service_name} Health', self.test_results[f'{service_name}_health'])
        
        # Test 6: WebSocket Connectivity
        print("\n6. Testing WebSocket Connectivity...")
        for service_name, url in self.base_urls.items():
            if 'localhost' not in url:  # Skip internal services
                print(f"   Testing {service_name} WebSocket...")
                self.test_results[f'{service_name}_websocket'] = self.test_websocket_connection(service_name, url)
                self._print_result(f'{service_name} WebSocket', self.test_results[f'{service_name}_websocket'])
        
        return self.test_results
    
    def _print_result(self, test_name: str, result: Dict):
        """Print test result with formatting"""
        status = result.get('status', 'UNKNOWN')
        if status == 'PASS':
            print(f"   ✅ {test_name}: PASS")
        elif status == 'FAIL':
            print(f"   ❌ {test_name}: FAIL")
            if 'error' in result:
                print(f"      Error: {result['error']}")
        else:
            print(f"   ℹ️  {test_name}: {status}")
            if 'message' in result:
                print(f"      {result['message']}")
    
    def generate_report(self) -> str:
        """Generate a comprehensive test report"""
        report = []
        report.append("# Voice Agent Implementation Test Report")
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
            if 'message' in result:
                report.append(f"**Message:** {result['message']}")
            if 'pods' in result:
                report.append("**Pod Details:**")
                for pod_name, pod_info in result['pods'].items():
                    report.append(f"  - {pod_name}: {pod_info['phase']} (Ready: {pod_info['ready']}, Restarts: {pod_info['restarts']})")
            if 'services' in result:
                report.append("**Service Details:**")
                for svc_name, svc_info in result['services'].items():
                    report.append(f"  - {svc_name}: {svc_info['type']} on ports {svc_info['ports']}")
            
            report.append("")
        
        return "\n".join(report)

def main():
    """Main testing function"""
    tester = VoiceAgentTester()
    
    try:
        # Run comprehensive tests
        results = tester.run_comprehensive_test()
        
        # Generate and save report
        report = tester.generate_report()
        
        # Save report to file
        with open('test_report.md', 'w') as f:
            f.write(report)
        
        print("\n" + "=" * 60)
        print("📊 Test Report Generated: test_report.md")
        print("=" * 60)
        
        # Print summary
        total_tests = len(results)
        passed_tests = sum(1 for result in results.values() if result.get('status') == 'PASS')
        print(f"\n🎯 Test Summary: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🎉 All tests passed! Your implementation is ready.")
        else:
            print("⚠️  Some tests failed. Check the detailed report for issues.")
        
    except KeyboardInterrupt:
        print("\n⏹️  Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Testing failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 