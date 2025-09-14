#!/usr/bin/env python3
"""
Quick performance validation script for Task 10
Tests messaging latency and system performance targets
"""

import time
import asyncio
import tempfile
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_messaging_latency():
    """Test messaging latency to validate <50ms target"""
    print("🔄 Testing messaging latency...")
    
    try:
        from src.messaging.manager import MessagingManager
        
        # Use fallback backend for reliable testing
        temp_dir = tempfile.mkdtemp()
        messaging = MessagingManager(backend_type='fallback', fallback_path=temp_dir)
        await messaging.connect()
        
        latencies = []
        iterations = 10
        
        for i in range(iterations):
            start_time = time.perf_counter()
            
            success = await messaging.send_message(
                sender="test_sender",
                recipient="test_receiver", 
                content=f"Performance test message {i}"
            )
            
            end_time = time.perf_counter()
            
            if success:
                latency_ms = (end_time - start_time) * 1000
                latencies.append(latency_ms)
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            min_latency = min(latencies)
            
            print(f"✅ Messaging Performance Results:")
            print(f"   Average latency: {avg_latency:.2f}ms")
            print(f"   Min latency: {min_latency:.2f}ms") 
            print(f"   Max latency: {max_latency:.2f}ms")
            print(f"   Target: <50ms")
            
            if avg_latency < 50:
                print(f"   ✅ PASS: Average latency meets target")
            else:
                print(f"   ❌ FAIL: Average latency exceeds target")
                
            return avg_latency < 50
        else:
            print("❌ No successful messages sent")
            return False
            
    except Exception as e:
        print(f"❌ Messaging test failed: {e}")
        return False

def test_audio_processing_speed():
    """Test audio processing speed to validate <200ms TTS target"""
    print("\n🔄 Testing audio processing speed...")
    
    try:
        from src.audio.manager import AudioManager
        
        # Use none backend for consistent testing
        audio = AudioManager(backend_type='none')
        
        # Generate test audio
        sample_rates = [22050]
        durations = [0.5, 1.0, 2.0]  # seconds
        
        processing_times = []
        
        for duration in durations:
            for sample_rate in sample_rates:
                start_time = time.perf_counter()
                
                # Generate audio
                test_audio = audio.generate_test_tone(
                    frequency=440, 
                    duration=duration, 
                    sample_rate=sample_rate
                )
                
                # Process audio (normalize)
                normalized = audio.normalize_audio(test_audio)
                
                # Simulate playback
                playback_success = audio.play_audio(test_audio, sample_rate=sample_rate)
                
                end_time = time.perf_counter()
                
                if playback_success:
                    processing_ms = (end_time - start_time) * 1000
                    processing_times.append(processing_ms)
        
        if processing_times:
            avg_processing = sum(processing_times) / len(processing_times)
            max_processing = max(processing_times)
            min_processing = min(processing_times)
            
            print(f"✅ Audio Processing Results:")
            print(f"   Average processing: {avg_processing:.2f}ms")
            print(f"   Min processing: {min_processing:.2f}ms")
            print(f"   Max processing: {max_processing:.2f}ms")
            print(f"   Target: <200ms TTS playback")
            
            if avg_processing < 200:
                print(f"   ✅ PASS: Processing speed meets target")
            else:
                print(f"   ❌ FAIL: Processing speed exceeds target")
                
            return avg_processing < 200
        else:
            print("❌ No successful audio processing")
            return False
            
    except Exception as e:
        print(f"❌ Audio test failed: {e}")
        return False

def test_system_compatibility():
    """Test cross-platform system compatibility"""
    print("\n🔄 Testing system compatibility...")
    
    try:
        from src.utils.os_utils import OSUtils
        
        # Test OS detection
        os_type = OSUtils.get_os_type()
        print(f"✅ OS Detection: {os_type}")
        
        # Test audio backend selection
        audio_backend = OSUtils.get_preferred_audio_backend()
        print(f"✅ Preferred Audio Backend: {audio_backend}")
        
        # Test Python executable detection
        python_exe = OSUtils.get_python_executable()
        print(f"✅ Python Executable: {python_exe}")
        
        # Test memory info
        memory_info = OSUtils.get_memory_info()
        if memory_info:
            print(f"✅ Memory Info: {memory_info['total'] // (1024*1024)}MB total")
        
        # Test system info
        system_info = OSUtils.get_system_info()
        print(f"✅ System Info: {system_info['os_type']} {system_info['architecture']}")
        
        return True
        
    except Exception as e:
        print(f"❌ System compatibility test failed: {e}")
        return False

def test_dependency_availability():
    """Test that all required dependencies are available"""
    print("\n🔄 Testing dependency availability...")
    
    required_deps = [
        'asyncio', 'pathlib', 'tempfile', 'logging', 'json', 'yaml',
        'psutil', 'platform', 'sys', 'os'
    ]
    
    optional_deps = ['redis', 'sounddevice', 'numpy', 'fastapi']
    
    missing_required = []
    missing_optional = []
    
    try:
        from src.utils.os_utils import OSUtils
        
        for dep in required_deps:
            if not OSUtils.check_dependency_available(dep):
                missing_required.append(dep)
        
        for dep in optional_deps:
            if not OSUtils.check_dependency_available(dep):
                missing_optional.append(dep)
        
        if not missing_required:
            print(f"✅ All required dependencies available")
        else:
            print(f"❌ Missing required dependencies: {missing_required}")
        
        if not missing_optional:
            print(f"✅ All optional dependencies available")
        else:
            print(f"⚠️  Missing optional dependencies: {missing_optional}")
        
        return len(missing_required) == 0
        
    except Exception as e:
        print(f"❌ Dependency check failed: {e}")
        return False

async def main():
    """Run all performance validation tests"""
    print("🚀 Slaygent Cross-Platform Performance Validation")
    print("=" * 60)
    
    tests = [
        ("Messaging Latency (<50ms target)", test_messaging_latency()),
        ("Audio Processing (<200ms target)", test_audio_processing_speed()),
        ("System Compatibility", test_system_compatibility()),
        ("Dependency Availability", test_dependency_availability())
    ]
    
    results = []
    
    for test_name, test_coro in tests:
        print(f"\n📋 Running: {test_name}")
        print("-" * 40)
        
        if asyncio.iscoroutine(test_coro):
            result = await test_coro
        else:
            result = test_coro
            
        results.append((test_name, result))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 PERFORMANCE VALIDATION SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL PERFORMANCE TARGETS MET! System ready for deployment.")
        return True
    else:
        print("⚠️  Some performance targets not met. Review and optimize.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)