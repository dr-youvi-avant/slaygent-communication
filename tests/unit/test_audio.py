"""
Unit tests for audio system
Tests cross-platform audio backends and TTS functionality
"""

import pytest
import asyncio
import numpy as np
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path

from src.audio.manager import AudioManager
from src.audio.sounddevice_backend import SoundDeviceBackend
from src.audio.pulse_backend import PulseAudioBackend
from src.audio.none_backend import NoneBackend


class TestSoundDeviceBackend:
    """Test SoundDevice audio backend."""
    
    def test_sounddevice_backend_init(self):
        """Test SoundDevice backend initialization."""
        with patch('sounddevice.query_devices') as mock_query:
            mock_query.return_value = [{'name': 'Test Device', 'channels': 2}]
            
            backend = SoundDeviceBackend()
            assert backend.backend_name == 'sounddevice'
    
    def test_get_devices(self, mock_audio_device):
        """Test device enumeration."""
        with patch('sounddevice.query_devices', return_value=mock_audio_device.query_devices()):
            backend = SoundDeviceBackend()
            devices = backend.get_devices()
            
            assert len(devices) > 0
            assert 'name' in devices[0]
            assert 'index' in devices[0]
    
    def test_get_default_device(self):
        """Test default device detection."""
        with patch('sounddevice.default') as mock_default:
            mock_default.device = [0, 1]  # input, output
            
            backend = SoundDeviceBackend()
            default_device = backend.get_default_device()
            
            assert default_device is not None
    
    def test_set_device(self):
        """Test device selection."""
        with patch('sounddevice.query_devices') as mock_query:
            mock_query.return_value = [
                {'name': 'Device 0', 'index': 0, 'channels': 2},
                {'name': 'Device 1', 'index': 1, 'channels': 2}
            ]
            
            backend = SoundDeviceBackend()
            
            success = backend.set_device(1)
            assert success
            assert backend.device_id == 1
            
            # Test invalid device
            success = backend.set_device(999)
            assert not success
    
    def test_play_audio(self, sample_audio_data):
        """Test audio playback."""
        with patch('sounddevice.play') as mock_play:
            with patch('sounddevice.wait') as mock_wait:
                backend = SoundDeviceBackend()
                
                success = backend.play_audio(sample_audio_data, sample_rate=22050)
                
                assert success
                mock_play.assert_called_once()
                mock_wait.assert_called_once()
                
                # Verify audio data was passed correctly
                call_args = mock_play.call_args[0]
                audio_data = call_args[0]
                assert len(audio_data) == len(sample_audio_data)
    
    def test_play_audio_failure(self, sample_audio_data):
        """Test audio playback failure handling."""
        with patch('sounddevice.play', side_effect=Exception("Audio device error")):
            backend = SoundDeviceBackend()
            
            success = backend.play_audio(sample_audio_data, sample_rate=22050)
            assert not success
    
    def test_set_volume(self):
        """Test volume control."""
        backend = SoundDeviceBackend()
        
        # Test valid volume
        backend.set_volume(0.5)
        assert backend.volume == 0.5
        
        # Test volume clamping
        backend.set_volume(1.5)  # Above max
        assert backend.volume == 1.0
        
        backend.set_volume(-0.1)  # Below min
        assert backend.volume == 0.0
    
    def test_is_available(self):
        """Test backend availability check."""
        # Test when sounddevice is available
        with patch('importlib.import_module') as mock_import:
            mock_sd = Mock()
            mock_sd.query_devices.return_value = [{'name': 'Test'}]
            mock_import.return_value = mock_sd
            
            assert SoundDeviceBackend.is_available()
        
        # Test when sounddevice is not available
        with patch('importlib.import_module', side_effect=ImportError):
            assert not SoundDeviceBackend.is_available()


class TestPulseAudioBackend:
    """Test PulseAudio backend."""
    
    def test_pulse_backend_init(self):
        """Test PulseAudio backend initialization."""
        with patch('shutil.which', return_value='/usr/bin/pactl'):
            backend = PulseAudioBackend()
            assert backend.backend_name == 'pulse'
    
    def test_get_devices_pulse(self):
        """Test PulseAudio device enumeration."""
        mock_output = """
index: 0
	name: <alsa_output.pci-0000_00_1f.3.analog-stereo>
	driver: <module-alsa-card.c>
	flags: HARDWARE HW_MUTE_CTRL DECIBEL_VOLUME LATENCY 
	state: SUSPENDED
	description: Built-in Audio Analog Stereo

index: 1
	name: <alsa_output.usb-Generic_USB_Audio-00.analog-stereo>
	driver: <module-alsa-card.c>
	flags: HARDWARE HW_MUTE_CTRL DECIBEL_VOLUME LATENCY 
	state: RUNNING
	description: USB Audio Analog Stereo
"""
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.returncode = 0
            
            backend = PulseAudioBackend()
            devices = backend.get_devices()
            
            assert len(devices) == 2
            assert devices[0]['name'] == 'alsa_output.pci-0000_00_1f.3.analog-stereo'
            assert devices[0]['description'] == 'Built-in Audio Analog Stereo'
    
    def test_get_default_device_pulse(self):
        """Test PulseAudio default device detection."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.stdout = "alsa_output.pci-0000_00_1f.3.analog-stereo"
            mock_run.return_value.returncode = 0
            
            backend = PulseAudioBackend()
            default_device = backend.get_default_device()
            
            assert default_device == "alsa_output.pci-0000_00_1f.3.analog-stereo"
    
    def test_play_audio_pulse(self, sample_audio_data, temp_dir):
        """Test PulseAudio playback."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                mock_file = Mock()
                mock_file.name = str(temp_dir / 'test_audio.wav')
                mock_tempfile.return_value.__enter__.return_value = mock_file
                
                backend = PulseAudioBackend()
                success = backend.play_audio(sample_audio_data, sample_rate=22050)
                
                assert success
                mock_run.assert_called()
                
                # Verify paplay was called
                call_args = mock_run.call_args[0][0]
                assert 'paplay' in call_args
    
    def test_play_audio_pulse_failure(self, sample_audio_data):
        """Test PulseAudio playback failure."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "Device not found"
            
            backend = PulseAudioBackend()
            success = backend.play_audio(sample_audio_data)
            
            assert not success
    
    def test_set_volume_pulse(self):
        """Test PulseAudio volume control."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            backend = PulseAudioBackend()
            backend.set_volume(0.8)
            
            # Verify pactl set-sink-volume was called
            mock_run.assert_called()
            call_args = mock_run.call_args[0][0]
            assert 'pactl' in call_args
            assert 'set-sink-volume' in call_args
            assert '80%' in call_args
    
    def test_is_available_pulse(self):
        """Test PulseAudio availability check."""
        # Test when pactl is available
        with patch('shutil.which', return_value='/usr/bin/pactl'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                assert PulseAudioBackend.is_available()
        
        # Test when pactl is not available
        with patch('shutil.which', return_value=None):
            assert not PulseAudioBackend.is_available()


class TestNoneBackend:
    """Test null audio backend."""
    
    def test_none_backend_init(self):
        """Test None backend initialization."""
        backend = NoneBackend()
        assert backend.backend_name == 'none'
    
    def test_none_backend_methods(self, sample_audio_data):
        """Test None backend methods (should all be no-ops)."""
        backend = NoneBackend()
        
        # All methods should return empty/default values without errors
        assert backend.get_devices() == []
        assert backend.get_default_device() is None
        assert backend.set_device(0) == True  # Always succeeds
        assert backend.play_audio(sample_audio_data) == True  # Always succeeds
        backend.set_volume(0.5)  # No-op
        assert backend.is_available() == True  # Always available


class TestAudioManager:
    """Test AudioManager orchestration."""
    
    def test_audio_manager_init_auto(self):
        """Test AudioManager initialization with auto backend selection."""
        with patch('src.utils.os_utils.OSUtils.get_preferred_audio_backend', return_value='sounddevice'):
            with patch('src.audio.sounddevice_backend.SoundDeviceBackend.is_available', return_value=True):
                manager = AudioManager(backend_type='auto')
                
                assert manager.backend_type == 'auto'
                assert isinstance(manager.backend, SoundDeviceBackend)
    
    def test_audio_manager_init_specific(self):
        """Test AudioManager initialization with specific backend."""
        manager = AudioManager(backend_type='none')
        
        assert manager.backend_type == 'none'
        assert isinstance(manager.backend, NoneBackend)
    
    def test_audio_manager_backend_selection_windows(self):
        """Test backend selection on Windows."""
        with patch('src.utils.os_utils.OSUtils.get_os_type', return_value='windows'):
            with patch('src.audio.sounddevice_backend.SoundDeviceBackend.is_available', return_value=True):
                manager = AudioManager(backend_type='auto')
                
                assert isinstance(manager.backend, SoundDeviceBackend)
    
    @pytest.mark.unix_only
    def test_audio_manager_backend_selection_linux(self, test_env):
        """Test backend selection on Linux."""
        if test_env.is_windows():
            pytest.skip("Unix-only test")
        
        with patch('src.utils.os_utils.OSUtils.get_os_type', return_value='linux'):
            # Test with PulseAudio available
            with patch('src.audio.pulse_backend.PulseAudioBackend.is_available', return_value=True):
                manager = AudioManager(backend_type='auto')
                assert isinstance(manager.backend, PulseAudioBackend)
            
            # Test with PulseAudio unavailable, fallback to sounddevice
            with patch('src.audio.pulse_backend.PulseAudioBackend.is_available', return_value=False):
                with patch('src.audio.sounddevice_backend.SoundDeviceBackend.is_available', return_value=True):
                    manager = AudioManager(backend_type='auto')
                    assert isinstance(manager.backend, SoundDeviceBackend)
    
    def test_audio_manager_fallback_to_none(self):
        """Test fallback to NoneBackend when no audio system is available."""
        with patch('src.audio.sounddevice_backend.SoundDeviceBackend.is_available', return_value=False):
            with patch('src.audio.pulse_backend.PulseAudioBackend.is_available', return_value=False):
                manager = AudioManager(backend_type='auto')
                
                assert isinstance(manager.backend, NoneBackend)
    
    def test_get_available_backends(self):
        """Test getting list of available backends."""
        with patch('src.audio.sounddevice_backend.SoundDeviceBackend.is_available', return_value=True):
            with patch('src.audio.pulse_backend.PulseAudioBackend.is_available', return_value=False):
                backends = AudioManager.get_available_backends()
                
                assert 'sounddevice' in backends
                assert 'none' in backends  # Always available
                assert 'pulse' not in backends
    
    def test_play_audio_manager(self, sample_audio_data):
        """Test audio playback through AudioManager."""
        with patch.object(NoneBackend, 'play_audio', return_value=True) as mock_play:
            manager = AudioManager(backend_type='none')
            
            success = manager.play_audio(sample_audio_data, sample_rate=22050)
            
            assert success
            mock_play.assert_called_once_with(sample_audio_data, sample_rate=22050)
    
    def test_get_devices_manager(self):
        """Test device enumeration through AudioManager."""
        mock_devices = [{'name': 'Test Device', 'index': 0}]
        
        with patch.object(NoneBackend, 'get_devices', return_value=mock_devices):
            manager = AudioManager(backend_type='none')
            devices = manager.get_devices()
            
            assert devices == mock_devices
    
    def test_set_volume_manager(self):
        """Test volume control through AudioManager."""
        with patch.object(NoneBackend, 'set_volume') as mock_set_volume:
            manager = AudioManager(backend_type='none')
            
            manager.set_volume(0.7)
            
            mock_set_volume.assert_called_once_with(0.7)
    
    def test_switch_backend(self):
        """Test switching audio backends at runtime."""
        manager = AudioManager(backend_type='none')
        assert isinstance(manager.backend, NoneBackend)
        
        # Switch to sounddevice (if available)
        with patch('src.audio.sounddevice_backend.SoundDeviceBackend.is_available', return_value=True):
            success = manager.switch_backend('sounddevice')
            
            if success:
                assert isinstance(manager.backend, SoundDeviceBackend)
    
    def test_backend_health_check(self):
        """Test backend health checking."""
        manager = AudioManager(backend_type='none')
        
        # None backend should always be healthy
        assert manager.is_backend_healthy()
    
    def test_audio_format_conversion(self, sample_audio_data):
        """Test audio format conversion utilities."""
        # Test float32 to int16 conversion
        int16_data = AudioManager.convert_to_int16(sample_audio_data)
        assert int16_data.dtype == np.int16
        assert len(int16_data) == len(sample_audio_data)
        
        # Test normalization
        normalized = AudioManager.normalize_audio(sample_audio_data)
        assert np.max(np.abs(normalized)) <= 1.0


@pytest.mark.integration
class TestAudioIntegration:
    """Integration tests for audio system."""
    
    def test_audio_pipeline_end_to_end(self, sample_audio_data):
        """Test complete audio pipeline from data to playback."""
        # Use None backend for reliable testing
        manager = AudioManager(backend_type='none')
        
        # Test device enumeration
        devices = manager.get_devices()
        assert isinstance(devices, list)
        
        # Test volume setting
        manager.set_volume(0.8)
        
        # Test audio playback
        success = manager.play_audio(sample_audio_data, sample_rate=22050)
        assert success
    
    @pytest.mark.audio
    def test_real_audio_system(self, test_env, sample_audio_data):
        """Test with real audio system (if available)."""
        if not test_env.has_audio():
            pytest.skip("No audio system available")
        
        manager = AudioManager(backend_type='auto')
        
        # Should not fall back to NoneBackend if audio is available
        assert not isinstance(manager.backend, NoneBackend)
        
        # Test device enumeration
        devices = manager.get_devices()
        assert len(devices) > 0
        
        # Test playback (this will produce actual audio)
        success = manager.play_audio(sample_audio_data[:1000], sample_rate=22050)  # Short clip
        assert success
    
    @pytest.mark.performance
    def test_audio_latency(self, benchmark_config, sample_audio_data):
        """Test audio latency benchmarks."""
        import time
        
        manager = AudioManager(backend_type='none')  # Use None for consistent timing
        
        # Measure playback initiation latency
        start_time = time.time()
        
        for _ in range(5):  # Test 5 playbacks
            manager.play_audio(sample_audio_data[:100], sample_rate=22050)  # Very short clips
        
        end_time = time.time()
        avg_latency = (end_time - start_time) / 5
        
        # Audio latency should be very low with None backend
        assert avg_latency < 0.01  # 10ms
    
    def test_audio_error_recovery(self, sample_audio_data):
        """Test audio system error handling and recovery."""
        manager = AudioManager(backend_type='sounddevice')
        
        # Simulate device error
        with patch.object(manager.backend, 'play_audio', side_effect=Exception("Device error")):
            success = manager.play_audio(sample_audio_data)
            assert not success
        
        # Recovery: switch to None backend
        success = manager.switch_backend('none')
        assert success
        
        # Should work with None backend
        success = manager.play_audio(sample_audio_data)
        assert success
    
    def test_cross_platform_compatibility(self, test_env, sample_audio_data):
        """Test audio system works across platforms."""
        manager = AudioManager(backend_type='auto')
        
        # Should select appropriate backend for platform
        if test_env.is_windows():
            # On Windows, should prefer sounddevice or fall back to none
            assert manager.backend.backend_name in ['sounddevice', 'none']
        elif test_env.is_linux():
            # On Linux, should prefer pulse or sounddevice or fall back to none
            assert manager.backend.backend_name in ['pulse', 'sounddevice', 'none']
        elif test_env.is_macos():
            # On macOS, should prefer sounddevice or fall back to none
            assert manager.backend.backend_name in ['sounddevice', 'none']
        
        # Basic functionality should work regardless of backend
        devices = manager.get_devices()
        assert isinstance(devices, list)
        
        success = manager.play_audio(sample_audio_data[:100], sample_rate=22050)
        assert success


class TestAudioUtilities:
    """Test audio utility functions."""
    
    def test_generate_test_tone(self):
        """Test test tone generation."""
        tone = AudioManager.generate_test_tone(frequency=440, duration=1.0, sample_rate=22050)
        
        assert len(tone) == 22050  # 1 second at 22050 Hz
        assert tone.dtype == np.float32
        assert np.max(np.abs(tone)) <= 1.0
    
    def test_audio_format_detection(self, sample_audio_data):
        """Test audio format detection."""
        # Test float32
        assert AudioManager.detect_audio_format(sample_audio_data) == 'float32'
        
        # Test int16
        int16_data = (sample_audio_data * 32767).astype(np.int16)
        assert AudioManager.detect_audio_format(int16_data) == 'int16'
    
    def test_resample_audio(self, sample_audio_data):
        """Test audio resampling."""
        # Resample from 22050 to 44100
        resampled = AudioManager.resample_audio(sample_audio_data, 22050, 44100)
        
        # Should be approximately double the length
        assert len(resampled) >= len(sample_audio_data) * 1.8
        assert len(resampled) <= len(sample_audio_data) * 2.2
    
    def test_apply_fade(self, sample_audio_data):
        """Test fade in/out application."""
        fade_samples = int(0.1 * 22050)  # 100ms fade
        
        faded = AudioManager.apply_fade(sample_audio_data, fade_samples, fade_samples)
        
        # Should start and end with near-zero values
        assert np.abs(faded[0]) < 0.01
        assert np.abs(faded[-1]) < 0.01
        
        # Should have same length
        assert len(faded) == len(sample_audio_data)