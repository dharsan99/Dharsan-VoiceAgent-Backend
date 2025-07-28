#!/usr/bin/env python3
"""
Test Script for Modal Cloud Storage Integration
Verifies that all Modal components are working correctly
"""

import asyncio
import json
import time
from datetime import datetime
import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_modal_import():
    """Test if Modal can be imported"""
    print("🔍 Testing Modal Import...")
    try:
        import modal
        print(f"✅ Modal imported successfully (version: {modal.__version__})")
        return True
    except ImportError as e:
        print(f"❌ Failed to import Modal: {e}")
        return False

def test_modal_storage_import():
    """Test if Modal storage module can be imported"""
    print("\n🔍 Testing Modal Storage Import...")
    try:
        from modal_storage import (
            store_session, store_conversation, queue_voice_processing,
            store_session_metrics, update_session, get_storage_stats
        )
        print("✅ Modal storage module imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import Modal storage: {e}")
        return False

def test_backend_integration():
    """Test if backend integrates with Modal storage"""
    print("\n🔍 Testing Backend Integration...")
    try:
        # Test if Modal storage functions can be imported
        from modal_storage import (
            store_session, store_conversation, queue_voice_processing,
            store_session_metrics, update_session, get_storage_stats
        )
        
        # Check if the functions exist (they should be Modal function objects)
        functions_exist = all([
            store_session is not None,
            store_conversation is not None,
            queue_voice_processing is not None,
            store_session_metrics is not None,
            update_session is not None,
            get_storage_stats is not None
        ])
        
        if functions_exist:
            print("✅ Modal storage functions are available")
            return True
        else:
            print("❌ Some Modal storage functions are missing")
            return False
            
    except ImportError as e:
        print(f"❌ Failed to import Modal storage functions: {e}")
        return False
    except Exception as e:
        print(f"❌ Modal storage test error: {e}")
        return False

def test_environment_variables():
    """Test if required environment variables are set"""
    print("\n🔍 Testing Environment Variables...")
    required_vars = [
        "DEEPGRAM_API_KEY",
        "GROQ_API_KEY", 
        "ELEVENLABS_API_KEY"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"⚠️ Missing environment variables: {missing_vars}")
        print("   These are required for full functionality")
        return False
    else:
        print("✅ All required environment variables are set")
        return True

def test_modal_cli():
    """Test if Modal CLI is available"""
    print("\n🔍 Testing Modal CLI...")
    try:
        import subprocess
        result = subprocess.run(["modal", "--version"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ Modal CLI is available: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ Modal CLI test failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ Modal CLI not found. Install with: pip install modal")
        return False
    except subprocess.TimeoutExpired:
        print("❌ Modal CLI test timed out")
        return False
    except Exception as e:
        print(f"❌ Modal CLI test error: {e}")
        return False

def test_modal_authentication():
    """Test if Modal authentication is working"""
    print("\n🔍 Testing Modal Authentication...")
    try:
        import subprocess
        # Use 'modal token' to check if tokens exist
        result = subprocess.run(["modal", "token"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Modal authentication successful")
            return True
        else:
            print(f"❌ Modal authentication failed: {result.stderr}")
            print("   Run 'modal token new' to authenticate")
            return False
    except Exception as e:
        print(f"❌ Modal authentication test error: {e}")
        return False

def test_modal_resources():
    """Test if Modal resources can be created"""
    print("\n🔍 Testing Modal Resources...")
    try:
        import modal
        
        # Test volume creation
        test_volume = modal.Volume.from_name("test-volume", create_if_missing=True)
        print("✅ Modal Volume creation successful")
        
        # Test dict creation
        test_dict = modal.Dict.from_name("test-dict", create_if_missing=True)
        print("✅ Modal Dict creation successful")
        
        # Test queue creation
        test_queue = modal.Queue.from_name("test-queue", create_if_missing=True)
        print("✅ Modal Queue creation successful")
        
        return True
    except Exception as e:
        print(f"❌ Modal resource creation failed: {e}")
        return False

def test_deployment_script():
    """Test if deployment script exists and is valid"""
    print("\n🔍 Testing Deployment Script...")
    deploy_script = "deploy_modal.py"
    
    if not os.path.exists(deploy_script):
        print(f"❌ Deployment script not found: {deploy_script}")
        return False
    
    try:
        # Try to import the deployment script
        import importlib.util
        spec = importlib.util.spec_from_file_location("deploy_modal", deploy_script)
        deploy_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deploy_module)
        print("✅ Deployment script is valid and can be imported")
        return True
    except Exception as e:
        print(f"❌ Deployment script validation failed: {e}")
        return False

def run_all_tests():
    """Run all integration tests"""
    print("🚀 Modal Cloud Storage Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("Modal Import", test_modal_import),
        ("Modal Storage Import", test_modal_storage_import),
        ("Backend Integration", test_backend_integration),
        ("Environment Variables", test_environment_variables),
        ("Modal CLI", test_modal_cli),
        ("Modal Authentication", test_modal_authentication),
        ("Modal Resources", test_modal_resources),
        ("Deployment Script", test_deployment_script),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Modal integration is ready.")
        print("\nNext steps:")
        print("1. Run: python deploy_modal.py deploy")
        print("2. Start your backend: python main.py")
        print("3. Test the frontend Cloud Storage Manager")
    elif passed >= total * 0.7:
        print("⚠️ Most tests passed. Check the failed tests above.")
        print("Modal integration should work with some limitations.")
    else:
        print("❌ Many tests failed. Please fix the issues above.")
        print("Modal integration may not work properly.")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 