"""
Pytest configuration and fixtures for Slaygent Communication System tests
Provides cross-platform test utilities and common fixtures
"""

import pytest
import asyncio
import tempfile
import shutil
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, Optional, Generator

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.config.manager import ConfigManager
from src.utils.os_utils import OSUtils


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_config(temp_dir):
    """Create a mock configuration for testing."""
    config_data = {
        "tts": {
            "host": "localhost",
            "port": 9003,
            "voices": {
                "amy": {
                    "model_path": str(temp_dir / "voices" / "amy" / "model.onnx"),
                    "config_path": str(temp_dir / "voices" / "amy" / "config.json"),
                    "language": "en-US",
                    "quality": "medium"
                }
            }
        },
        "discovery": {
            "host": "localhost", 
            "port": 9005,
            "scan_interval": 5
        },
        "messaging": {
            "backend": "redis",
            "redis_host": "localhost",
            "redis_port": 6379,
            "fallback_enabled": True
        },
        "audio": {
            "backend": "auto",
            "device_id": None,
            "buffer_size": 1024
        }
    }
    
    # Create voice model files
    voices_dir = temp_dir / "voices" / "amy"
    voices_dir.mkdir(parents=True)
    (voices_dir / "model.onnx").write_bytes(b"fake_model_data")
    (voices_dir / "config.json").write_text('{"sample_rate": 22050}')
    
    return config_data


@pytest.fixture
def config_manager(mock_config, temp_dir):
    """Create a ConfigManager instance with test configuration."""
    config_file = temp_dir / "config.yaml"
    
    import yaml
    with open(config_file, 'w') as f:
        yaml.dump(mock_config, f)
    
    return ConfigManager.load_config(str(temp_dir))


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    redis_mock = Mock()
    redis_mock.ping.return_value = True
    redis_mock.publish.return_value = 1
    redis_mock.subscribe.return_value = Mock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.keys.return_value = []
    
    return redis_mock


@pytest.fixture
def mock_audio_device():
    """Mock audio device for testing."""
    device_mock = Mock()
    device_mock.query_devices.return_value = [
        {
            'name': 'Test Audio Device',
            'index': 0,
            'channels': 2,
            'default_samplerate': 44100
        }
    ]
    device_mock.play.return_value = None
    device_mock.default.return_value = {'device': 0}
    
    return device_mock


@pytest.fixture
def mock_process_list():
    """Mock process list for testing agent discovery."""
    return [
        {
            'pid': 1234,
            'name': 'python',
            'cmdline': ['python', '-m', 'claude.cli'],
            'create_time': 1234567890,
            'status': 'running'
        },
        {
            'pid': 5678,
            'name': 'node', 
            'cmdline': ['node', '/path/to/agent.js'],
            'create_time': 1234567891,
            'status': 'running'
        },
        {
            'pid': 9999,
            'name': 'tmux',
            'cmdline': ['tmux', 'new-session', '-d'],
            'create_time': 1234567892,
            'status': 'running'
        }
    ]


@pytest.fixture
def mock_piper_model():
    """Mock Piper TTS model for testing."""
    model_mock = Mock()
    model_mock.synthesize.return_value = b"fake_audio_data"
    model_mock.sample_rate = 22050
    model_mock.voice_info = {
        'name': 'amy',
        'language': 'en-US',
        'quality': 'medium'
    }
    
    return model_mock


@pytest.fixture
def sample_audio_data():
    """Generate sample audio data for testing."""
    import numpy as np
    
    # Generate a 1-second sine wave at 440 Hz
    sample_rate = 22050
    duration = 1.0
    frequency = 440
    
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio_data = np.sin(2 * np.pi * frequency * t) * 0.5
    
    return audio_data.astype(np.float32)


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for API testing."""
    client_mock = AsyncMock()
    client_mock.get.return_value.status = 200
    client_mock.get.return_value.json.return_value = {"status": "ok"}
    client_mock.post.return_value.status = 200
    client_mock.post.return_value.json.return_value = {"success": True}
    
    return client_mock


@pytest.fixture
def platform_patches():
    """Platform-specific patches for cross-platform testing."""
    patches = {}
    
    # Windows patches
    if sys.platform.startswith('win'):
        patches['subprocess'] = patch('subprocess.run')
        patches['wmic'] = patch('src.messaging.process_discovery.subprocess.run')
    
    # Linux patches  
    elif sys.platform.startswith('linux'):
        patches['pulseaudio'] = patch('src.audio.pulse_backend.subprocess.run')
        patches['ps'] = patch('src.messaging.process_discovery.subprocess.run')
    
    # macOS patches
    elif sys.platform == 'darwin':
        patches['coreaudio'] = patch('src.audio.sounddevice_backend.sd')
        patches['ps'] = patch('src.messaging.process_discovery.subprocess.run')
    
    return patches


@pytest.fixture(autouse=True)
def cleanup_processes():
    """Automatically clean up any test processes after each test."""
    yield
    
    # Kill any test processes that might be running
    import psutil
    current_process = psutil.Process()
    
    for child in current_process.children(recursive=True):
        try:
            if 'test' in child.name().lower() or 'pytest' in ' '.join(child.cmdline()).lower():
                child.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


@pytest.fixture
def benchmark_config():
    """Configuration for performance benchmarking."""
    return {
        'messaging_latency_target': 0.05,  # 50ms
        'tts_latency_target': 0.2,  # 200ms
        'discovery_latency_target': 0.1,  # 100ms
        'startup_time_target': 10.0,  # 10 seconds
        'memory_usage_target': 500 * 1024 * 1024  # 500MB
    }


class TestEnvironment:
    """Test environment utilities for cross-platform testing."""
    
    @staticmethod
    def is_windows():
        return sys.platform.startswith('win')
    
    @staticmethod
    def is_linux():
        return sys.platform.startswith('linux')
    
    @staticmethod
    def is_macos():
        return sys.platform == 'darwin'
    
    @staticmethod
    def has_redis():
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            r.ping()
            return True
        except:
            return False
    
    @staticmethod
    def has_audio():
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            return len(devices) > 0
        except:
            return False
    
    @staticmethod
    def has_tmux():
        return shutil.which('tmux') is not None
    
    @staticmethod
    def skip_if_no_redis():
        return pytest.mark.skipif(
            not TestEnvironment.has_redis(),
            reason="Redis not available"
        )
    
    @staticmethod
    def skip_if_no_audio():
        return pytest.mark.skipif(
            not TestEnvironment.has_audio(),
            reason="Audio system not available"
        )
    
    @staticmethod
    def skip_if_no_tmux():
        return pytest.mark.skipif(
            not TestEnvironment.has_tmux(),
            reason="tmux not available"
        )
    
    @staticmethod
    def windows_only():
        return pytest.mark.skipif(
            not TestEnvironment.is_windows(),
            reason="Windows-only test"
        )
    
    @staticmethod
    def unix_only():
        return pytest.mark.skipif(
            TestEnvironment.is_windows(),
            reason="Unix-only test"
        )


@pytest.fixture
def test_env():
    """Test environment utilities fixture."""
    return TestEnvironment


# Pytest markers for organizing tests
pytest_plugins = ["pytest_asyncio"]

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual components"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests for component interactions"
    )
    config.addinivalue_line(
        "markers", "performance: Performance and benchmark tests"
    )
    config.addinivalue_line(
        "markers", "windows: Windows-specific tests"
    )
    config.addinivalue_line(
        "markers", "linux: Linux-specific tests"
    )
    config.addinivalue_line(
        "markers", "macos: macOS-specific tests"
    )
    config.addinivalue_line(
        "markers", "redis: Tests requiring Redis"
    )
    config.addinivalue_line(
        "markers", "audio: Tests requiring audio system"
    )
    config.addinivalue_line(
        "markers", "tmux: Tests requiring tmux"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests (>5 seconds)"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add platform markers automatically."""
    for item in items:
        # Add platform markers based on test location/name
        if "windows" in item.nodeid.lower():
            item.add_marker(pytest.mark.windows)
        elif "linux" in item.nodeid.lower():
            item.add_marker(pytest.mark.linux)
        elif "macos" in item.nodeid.lower():
            item.add_marker(pytest.mark.macos)
        
        # Add component markers based on test path
        if "messaging" in item.nodeid:
            item.add_marker(pytest.mark.messaging)
        elif "audio" in item.nodeid:
            item.add_marker(pytest.mark.audio)
        elif "config" in item.nodeid:
            item.add_marker(pytest.mark.config)
        elif "servers" in item.nodeid:
            item.add_marker(pytest.mark.servers)


@pytest.fixture(scope="session")
def test_data_dir():
    """Directory containing test data files."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def create_test_voice_model(temp_dir):
    """Create a minimal test voice model."""
    def _create_voice_model(voice_name="test_voice"):
        voice_dir = temp_dir / "voices" / voice_name
        voice_dir.mkdir(parents=True, exist_ok=True)
        
        # Create minimal model file
        model_file = voice_dir / "model.onnx"
        model_file.write_bytes(b"fake_onnx_model_data")
        
        # Create config file
        config_file = voice_dir / "config.json"
        config_data = {
            "audio": {
                "sample_rate": 22050
            },
            "inference": {
                "noise_scale": 0.667,
                "length_scale": 1.0,
                "noise_w": 0.8
            },
            "phoneme_type": "espeak",
            "espeak": {
                "voice": "en-us"
            }
        }
        
        import json
        config_file.write_text(json.dumps(config_data, indent=2))
        
        return voice_dir
    
    return _create_voice_model