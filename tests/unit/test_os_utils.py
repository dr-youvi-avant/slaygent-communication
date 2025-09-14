"""
Unit tests for OS utilities module
Tests cross-platform OS detection and utility functions
"""

import pytest
import sys
import platform
from unittest.mock import patch, Mock, mock_open
from pathlib import Path

from src.utils.os_utils import OSUtils


class TestOSDetection:
    """Test OS detection functionality."""
    
    def test_get_os_type_windows(self):
        """Test Windows OS detection."""
        from src.utils.os_utils import OSDetector
        # Reset singleton for clean test
        OSDetector._reset_instance()
        with patch('platform.system', return_value='Windows'):
            assert OSUtils.get_os_type() == 'windows'
    
    def test_get_os_type_linux(self):
        """Test Linux OS detection."""
        from src.utils.os_utils import OSDetector
        # Reset singleton for clean test
        OSDetector._reset_instance()
        with patch('platform.system', return_value='Linux'):
            assert OSUtils.get_os_type() == 'linux'
    
    def test_get_os_type_darwin(self):
        """Test macOS OS detection."""
        from src.utils.os_utils import OSDetector
        # Reset singleton for clean test
        OSDetector._reset_instance()
        with patch('platform.system', return_value='Darwin'):
            assert OSUtils.get_os_type() == 'macos'
    
    def test_get_os_type_unknown(self):
        """Test unknown OS detection."""
        from src.utils.os_utils import OSDetector
        # Reset singleton for clean test
        OSDetector._reset_instance()
        with patch('platform.system', return_value='FreeBSD'):
            assert OSUtils.get_os_type() == 'unknown'
    
    @pytest.mark.windows
    def test_is_windows_on_windows(self, test_env):
        """Test Windows detection on Windows platform."""
        if test_env.is_windows():
            assert OSUtils.is_windows()
        else:
            pytest.skip("Not running on Windows")
    
    @pytest.mark.unix_only
    def test_is_windows_on_unix(self, test_env):
        """Test Windows detection on Unix platforms."""
        if not test_env.is_windows():
            assert not OSUtils.is_windows()
        else:
            pytest.skip("Not running on Unix")
    
    def test_detect_wsl(self):
        """Test WSL detection."""
        from src.utils.os_utils import OSDetector
        # Reset singleton for clean test
        OSDetector._reset_instance()
        
        # Mock WSL environment - file exists and contains 'microsoft'
        with patch('builtins.open', mock_open(read_data='Linux version 4.4.0-microsoft WSL')):
            assert OSUtils.detect_wsl()
        
        # Reset singleton for second test
        OSDetector._reset_instance()
        
        # Mock non-WSL environment - file doesn't exist
        with patch('builtins.open', side_effect=FileNotFoundError):
            assert not OSUtils.detect_wsl()


class TestAudioBackendSelection:
    """Test audio backend selection logic."""
    
    def test_get_preferred_audio_backend_windows(self):
        """Test preferred audio backend on Windows."""
        from src.utils.os_utils import OSDetector
        # Reset singleton for clean test
        OSDetector._reset_instance()
        
        with patch('platform.system', return_value='Windows'):
            backend = OSUtils.get_preferred_audio_backend()
            assert backend == 'sounddevice'
    
    def test_get_preferred_audio_backend_linux(self):
        """Test preferred audio backend on Linux."""
        from src.utils.os_utils import OSDetector
        
        # Test with PulseAudio available
        OSDetector._reset_instance()
        with patch('platform.system', return_value='Linux'), \
             patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0  # PulseAudio check succeeds
            backend = OSUtils.get_preferred_audio_backend()
            assert backend == 'pulse'
        
        # Test without PulseAudio
        OSDetector._reset_instance()
        with patch('platform.system', return_value='Linux'), \
             patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 1  # PulseAudio check fails
            backend = OSUtils.get_preferred_audio_backend()
            assert backend == 'sounddevice'
    
    def test_get_preferred_audio_backend_macos(self):
        """Test preferred audio backend on macOS."""
        from src.utils.os_utils import OSDetector
        # Reset singleton for clean test
        OSDetector._reset_instance()
        
        with patch('platform.system', return_value='Darwin'):
            backend = OSUtils.get_preferred_audio_backend()
            assert backend == 'sounddevice'
    
    def test_check_audio_system_availability_pulse(self):
        """Test PulseAudio system availability check."""
        with patch('shutil.which', return_value='/usr/bin/pulseaudio'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                assert OSUtils.check_audio_system_availability('pulse')
        
        # Test unavailable PulseAudio
        with patch('shutil.which', return_value=None):
            assert not OSUtils.check_audio_system_availability('pulse')
    
    def test_check_audio_system_availability_sounddevice(self):
        """Test sounddevice availability check."""
        # Mock successful sounddevice import and device query
        with patch('importlib.import_module') as mock_import:
            mock_sd = Mock()
            mock_sd.query_devices.return_value = [{'name': 'Test Device'}]
            mock_import.return_value = mock_sd
            
            assert OSUtils.check_audio_system_availability('sounddevice')
        
        # Test unavailable sounddevice
        with patch('importlib.import_module', side_effect=ImportError):
            assert not OSUtils.check_audio_system_availability('sounddevice')


class TestPathUtilities:
    """Test path utility functions."""
    
    def test_get_config_dir_windows(self):
        """Test config directory on Windows."""
        with patch.object(OSUtils, 'get_os_type', return_value='windows'):
            with patch.dict('os.environ', {'APPDATA': r'C:\Users\Test\AppData\Roaming'}):
                config_dir = OSUtils.get_config_dir()
                assert 'Slaygent' in str(config_dir)
                assert str(config_dir).startswith('C:')
    
    def test_get_config_dir_unix(self):
        """Test config directory on Unix systems."""
        with patch.object(OSUtils, 'get_os_type', return_value='linux'):
            with patch.dict('os.environ', {'HOME': '/home/test'}):
                config_dir = OSUtils.get_config_dir()
                assert '.config/slaygent' in str(config_dir)
    
    def test_get_cache_dir_windows(self):
        """Test cache directory on Windows."""
        with patch.object(OSUtils, 'get_os_type', return_value='windows'):
            with patch.dict('os.environ', {'LOCALAPPDATA': r'C:\Users\Test\AppData\Local'}):
                cache_dir = OSUtils.get_cache_dir()
                assert 'Slaygent' in str(cache_dir)
                assert str(cache_dir).startswith('C:')
    
    def test_get_cache_dir_unix(self):
        """Test cache directory on Unix systems."""
        with patch.object(OSUtils, 'get_os_type', return_value='linux'):
            with patch.dict('os.environ', {'HOME': '/home/test'}):
                cache_dir = OSUtils.get_cache_dir()
                assert '.cache/slaygent' in str(cache_dir)
    
    def test_resolve_path_absolute(self):
        """Test path resolution with absolute path."""
        abs_path = Path('/absolute/path/to/file')
        resolved = OSUtils.resolve_path(str(abs_path), Path('/base/dir'))
        assert resolved == abs_path
    
    def test_resolve_path_relative(self):
        """Test path resolution with relative path."""
        rel_path = 'relative/path/to/file'
        base_dir = Path('/base/dir')
        resolved = OSUtils.resolve_path(rel_path, base_dir)
        assert resolved == base_dir / rel_path
    
    def test_resolve_path_home_expansion(self):
        """Test path resolution with home directory expansion."""
        with patch('pathlib.Path.expanduser') as mock_expand:
            mock_expand.return_value = Path('/home/test/file')
            resolved = OSUtils.resolve_path('~/file', Path('/base'))
            assert resolved == Path('/home/test/file')


class TestProcessUtilities:
    """Test process-related utility functions."""
    
    def test_get_python_executable(self):
        """Test Python executable detection."""
        python_exe = OSUtils.get_python_executable()
        assert python_exe is not None
        assert 'python' in python_exe.lower()
    
    def test_find_executable_in_path(self):
        """Test executable finding in PATH."""
        # Test finding Python (should exist)
        python_path = OSUtils.find_executable('python')
        if python_path:  # May not exist on all systems
            assert Path(python_path).exists()
        
        # Test non-existent executable
        fake_exe = OSUtils.find_executable('nonexistent_executable_12345')
        assert fake_exe is None
    
    @pytest.mark.windows
    def test_get_process_list_windows(self, test_env):
        """Test process listing on Windows."""
        if not test_env.is_windows():
            pytest.skip("Windows-only test")
        
        with patch('subprocess.run') as mock_run:
            # Mock tasklist output
            mock_run.return_value.stdout = 'python.exe,1234,Console,1,50,000 K'
            mock_run.return_value.returncode = 0
            
            processes = OSUtils.get_process_list()
            assert isinstance(processes, list)
    
    @pytest.mark.unix_only
    def test_get_process_list_unix(self, test_env):
        """Test process listing on Unix systems."""
        if test_env.is_windows():
            pytest.skip("Unix-only test")
        
        with patch('subprocess.run') as mock_run:
            # Mock ps output
            mock_run.return_value.stdout = '1234 python /path/to/script.py'
            mock_run.return_value.returncode = 0
            
            processes = OSUtils.get_process_list()
            assert isinstance(processes, list)


class TestSystemCapabilities:
    """Test system capability detection."""
    
    def test_check_port_availability(self):
        """Test port availability checking."""
        # Test well-known unavailable port (if possible)
        import socket
        
        # Find an available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', 0))
            available_port = s.getsockname()[1]
        
        assert OSUtils.check_port_availability('localhost', available_port)
        
        # Test obviously unavailable port (port 1 requires root)
        assert not OSUtils.check_port_availability('localhost', 1)
    
    def test_get_system_info(self):
        """Test system information gathering."""
        info = OSUtils.get_system_info()
        
        assert 'os_type' in info
        assert 'platform' in info
        assert 'python_version' in info
        assert 'architecture' in info
        
        assert info['os_type'] in ['windows', 'linux', 'macos', 'unknown']
        assert isinstance(info['python_version'], str)
    
    def test_check_dependencies_available(self):
        """Test dependency availability checking."""
        # Test with known available module
        assert OSUtils.check_dependency_available('sys')
        assert OSUtils.check_dependency_available('os')
        
        # Test with non-existent module
        assert not OSUtils.check_dependency_available('nonexistent_module_12345')
    
    def test_get_memory_info(self):
        """Test memory information gathering."""
        try:
            import psutil
            memory_info = OSUtils.get_memory_info()
            
            assert 'total' in memory_info
            assert 'available' in memory_info
            assert 'percent' in memory_info
            
            assert memory_info['total'] > 0
            assert memory_info['available'] >= 0
            assert 0 <= memory_info['percent'] <= 100
        except ImportError:
            pytest.skip("psutil not available")


class TestEnvironmentDetection:
    """Test environment detection utilities."""
    
    def test_is_virtual_environment(self):
        """Test virtual environment detection."""
        # This test depends on whether we're actually in a venv
        is_venv = OSUtils.is_virtual_environment()
        assert isinstance(is_venv, bool)
    
    def test_get_shell_type(self):
        """Test shell type detection."""
        shell_type = OSUtils.get_shell_type()
        
        if sys.platform.startswith('win'):
            assert shell_type in ['powershell', 'cmd', 'unknown']
        else:
            assert shell_type in ['bash', 'zsh', 'fish', 'sh', 'unknown']
    
    def test_is_admin_user(self):
        """Test admin/root user detection."""
        is_admin = OSUtils.is_admin_user()
        assert isinstance(is_admin, bool)
        # We can't assume we're running as admin/root in tests
    
    def test_get_terminal_type(self):
        """Test terminal type detection."""
        terminal_type = OSUtils.get_terminal_type()
        
        # Should return a string, even if 'unknown'
        assert isinstance(terminal_type, str)
        
        expected_terminals = [
            'windows_terminal', 'powershell', 'cmd',
            'gnome-terminal', 'konsole', 'xterm',
            'iterm2', 'terminal', 'tmux', 'screen',
            'vscode', 'unknown'
        ]
        assert terminal_type in expected_terminals


@pytest.mark.integration
class TestOSUtilsIntegration:
    """Integration tests for OS utilities."""
    
    def test_full_system_detection(self):
        """Test complete system detection workflow."""
        # Get all system information
        os_type = OSUtils.get_os_type()
        system_info = OSUtils.get_system_info()
        audio_backend = OSUtils.get_preferred_audio_backend()
        
        # Verify consistency
        assert system_info['os_type'] == os_type
        assert audio_backend in ['sounddevice', 'pulse', 'none']
        
        # Verify audio backend is appropriate for OS
        if os_type == 'windows':
            assert audio_backend == 'sounddevice'
        elif os_type == 'linux':
            assert audio_backend in ['pulse', 'sounddevice']
        elif os_type == 'macos':
            assert audio_backend == 'sounddevice'
    
    def test_config_and_cache_directories(self):
        """Test config and cache directory creation and access."""
        config_dir = OSUtils.get_config_dir()
        cache_dir = OSUtils.get_cache_dir()
        
        # Directories should be different
        assert config_dir != cache_dir
        
        # Should be able to create directories
        config_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        assert config_dir.exists()
        assert cache_dir.exists()
        
        # Clean up test directories
        import shutil
        try:
            shutil.rmtree(config_dir)
            shutil.rmtree(cache_dir)
        except:
            pass  # Best effort cleanup