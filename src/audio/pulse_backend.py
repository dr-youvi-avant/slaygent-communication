#!/usr/bin/env python3
"""
PulseAudio backend for Linux systems
Provides native PulseAudio integration when available
"""

import asyncio
import logging
import subprocess
import tempfile
import os
from typing import Dict, List, Optional, Any
from pathlib import Path

import numpy as np

from .base import AudioBackend, AudioDevice, AudioConfig
from .base import AudioError, AudioInitializationError, AudioPlaybackError, AudioDeviceError

logger = logging.getLogger(__name__)


class PulseAudioBackend(AudioBackend):
    """PulseAudio backend for Linux systems"""
    
    def __init__(self, config: AudioConfig):
        super().__init__(config)
        self.backend_name = "pulseaudio"
        self._pulse_available = False
        self._paplay_path = None
        self._current_volume = 1.0
    
    async def initialize(self) -> bool:
        """Initialize PulseAudio backend"""
        try:
            # Check if PulseAudio is running
            result = await asyncio.create_subprocess_exec(
                'pulseaudio', '--check',
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await result.wait()
            
            if result.returncode != 0:
                raise AudioInitializationError("PulseAudio not running")
            
            # Find paplay command
            for cmd in ['paplay', 'pulseaudio-utils']:
                if await self._command_exists(cmd):
                    self._paplay_path = cmd if cmd == 'paplay' else 'paplay'
                    break
            
            if not self._paplay_path:
                raise AudioInitializationError("paplay command not found")
            
            # Test PulseAudio functionality
            try:
                await self._test_audio_output()
                logger.info("PulseAudio test successful")
            except Exception as e:
                logger.warning(f"PulseAudio test failed: {e}")
            
            self._pulse_available = True
            self.is_initialized = True
            logger.info("PulseAudio backend initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize PulseAudio backend: {e}")
            self.is_initialized = False
            return False
    
    async def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        try:
            result = await asyncio.create_subprocess_exec(
                'which', command,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await result.wait()
            return result.returncode == 0
        except Exception:
            return False
    
    async def _test_audio_output(self):
        """Test PulseAudio output with a short silence"""
        try:
            # Create a very short silent audio file for testing
            test_duration = 0.1  # 100ms
            silence = np.zeros(int(self.config.sample_rate * test_duration), dtype=np.float32)
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            try:
                # Write silence to temporary WAV file
                await self._write_wav_file(tmp_path, silence, self.config.sample_rate)
                
                # Try to play it with paplay
                result = await asyncio.create_subprocess_exec(
                    self._paplay_path, tmp_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode != 0:
                    raise AudioError(f"paplay test failed: {stderr.decode()}")
                    
            finally:
                # Clean up temp file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                    
        except Exception as e:
            raise AudioError(f"PulseAudio test failed: {e}")
    
    async def shutdown(self):
        """Shutdown PulseAudio backend"""
        self.is_initialized = False
        self._pulse_available = False
        logger.info("PulseAudio backend shutdown")
    
    async def _write_wav_file(self, filename: str, audio_data: np.ndarray, sample_rate: int):
        """Write audio data to WAV file"""
        try:
            import soundfile as sf
            sf.write(filename, audio_data, sample_rate)
        except ImportError:
            # Fallback: create simple WAV file manually
            await self._write_simple_wav(filename, audio_data, sample_rate)
    
    async def _write_simple_wav(self, filename: str, audio_data: np.ndarray, sample_rate: int):
        """Write simple WAV file without soundfile dependency"""
        import struct
        
        # Convert to 16-bit PCM
        if audio_data.dtype != np.int16:
            # Convert float to int16
            if audio_data.dtype in [np.float32, np.float64]:
                audio_data = (audio_data * 32767).astype(np.int16)
            else:
                audio_data = audio_data.astype(np.int16)
        
        # WAV file parameters
        channels = 1
        sample_width = 2  # 16-bit = 2 bytes
        frame_rate = sample_rate
        n_frames = len(audio_data)
        
        # Calculate sizes
        data_size = n_frames * channels * sample_width
        file_size = 36 + data_size
        
        # Create WAV file
        with open(filename, 'wb') as wav_file:
            # RIFF header
            wav_file.write(b'RIFF')
            wav_file.write(struct.pack('<L', file_size))
            wav_file.write(b'WAVE')
            
            # fmt chunk
            wav_file.write(b'fmt ')
            wav_file.write(struct.pack('<L', 16))  # fmt chunk size
            wav_file.write(struct.pack('<H', 1))   # PCM format
            wav_file.write(struct.pack('<H', channels))
            wav_file.write(struct.pack('<L', frame_rate))
            wav_file.write(struct.pack('<L', frame_rate * channels * sample_width))  # byte rate
            wav_file.write(struct.pack('<H', channels * sample_width))  # block align
            wav_file.write(struct.pack('<H', sample_width * 8))  # bits per sample
            
            # data chunk
            wav_file.write(b'data')
            wav_file.write(struct.pack('<L', data_size))
            wav_file.write(audio_data.tobytes())
    
    async def play_audio(self, audio_data: np.ndarray, sample_rate: Optional[int] = None) -> bool:
        """Play audio data using PulseAudio"""
        if not self.is_initialized:
            raise AudioPlaybackError("PulseAudio backend not initialized")
        
        try:
            # Use provided sample rate or default
            sr = sample_rate or self.config.sample_rate
            
            # Apply volume
            volume_adjusted_data = audio_data * self._current_volume
            
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            try:
                # Write audio to temporary file
                await self._write_wav_file(tmp_path, volume_adjusted_data, sr)
                
                # Play using paplay
                result = await asyncio.create_subprocess_exec(
                    self._paplay_path, tmp_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode != 0:
                    raise AudioPlaybackError(f"paplay failed: {stderr.decode()}")
                
                return True
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"PulseAudio playback failed: {e}")
            raise AudioPlaybackError(f"PulseAudio playback error: {e}")
    
    async def get_devices(self) -> List[AudioDevice]:
        """Get list of available PulseAudio devices"""
        devices = []
        
        try:
            # Use pactl to list sinks (output devices)
            result = await asyncio.create_subprocess_exec(
                'pactl', 'list', 'short', 'sinks',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                logger.warning(f"pactl failed: {stderr.decode()}")
                return devices
            
            # Parse pactl output
            lines = stdout.decode().strip().split('\n')
            for line in lines:
                if not line.strip():
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 2:
                    device_id = int(parts[0])
                    device_name = parts[1]
                    
                    # Try to get more device info
                    device_info = await self._get_device_info(device_name)
                    
                    audio_device = AudioDevice(
                        device_id=device_id,
                        name=device_info.get('description', device_name),
                        channels=device_info.get('channels', 2),
                        sample_rate=device_info.get('sample_rate', 44100),
                        is_default=device_info.get('is_default', False),
                        backend=self.backend_name
                    )
                    devices.append(audio_device)
            
        except Exception as e:
            logger.error(f"Failed to get PulseAudio devices: {e}")
        
        return devices
    
    async def _get_device_info(self, device_name: str) -> Dict[str, Any]:
        """Get detailed information about a PulseAudio device"""
        info = {}
        
        try:
            result = await asyncio.create_subprocess_exec(
                'pactl', 'list', 'sinks',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                output = stdout.decode()
                # Parse detailed sink information
                # This is a simplified parser - could be enhanced
                if device_name in output:
                    info['description'] = device_name
                    info['channels'] = 2  # Default assumption
                    info['sample_rate'] = 44100  # Default assumption
            
        except Exception as e:
            logger.debug(f"Failed to get device info for {device_name}: {e}")
        
        return info
    
    async def get_default_device(self) -> Optional[AudioDevice]:
        """Get default PulseAudio output device"""
        try:
            result = await asyncio.create_subprocess_exec(
                'pactl', 'get-default-sink',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                default_sink = stdout.decode().strip()
                
                # Find this sink in our device list
                devices = await self.get_devices()
                for device in devices:
                    if default_sink in device.name:
                        device.is_default = True
                        return device
            
        except Exception as e:
            logger.error(f"Failed to get default PulseAudio device: {e}")
        
        return None
    
    async def set_volume(self, volume: float) -> bool:
        """Set playback volume (0.0 to 1.0)"""
        if not 0.0 <= volume <= 1.0:
            raise AudioError("Volume must be between 0.0 and 1.0")
        
        self._current_volume = volume
        
        # Optionally set system volume via pactl
        try:
            volume_percent = int(volume * 100)
            result = await asyncio.create_subprocess_exec(
                'pactl', 'set-sink-volume', '@DEFAULT_SINK@', f'{volume_percent}%',
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await result.wait()
            
            if result.returncode == 0:
                logger.debug(f"System volume set to {volume_percent}%")
            else:
                logger.debug("Failed to set system volume, using software volume")
                
        except Exception as e:
            logger.debug(f"Could not set system volume: {e}")
        
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        """Check PulseAudio backend health"""
        health = {
            "backend": self.backend_name,
            "initialized": self.is_initialized,
            "pulse_available": self._pulse_available,
            "status": "unknown"
        }
        
        try:
            if not self.is_initialized:
                health["status"] = "not_initialized"
                return health
            
            # Check PulseAudio server status
            result = await asyncio.create_subprocess_exec(
                'pulseaudio', '--check',
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await result.wait()
            
            pulse_running = result.returncode == 0
            
            health.update({
                "status": "healthy" if pulse_running else "pulse_not_running",
                "pulse_server_running": pulse_running,
                "paplay_available": self._paplay_path is not None,
                "sample_rate": self.config.sample_rate,
                "channels": self.config.channels,
                "volume": self._current_volume
            })
            
        except Exception as e:
            health.update({
                "status": "unhealthy",
                "error": str(e)
            })
        
        return health


def is_pulseaudio_available() -> bool:
    """Check if PulseAudio is available on this system"""
    try:
        # Check if pulseaudio command exists
        import subprocess
        result = subprocess.run(['which', 'pulseaudio'], 
                              capture_output=True, timeout=5)
        if result.returncode != 0:
            return False
        
        # Check if PulseAudio server is running
        result = subprocess.run(['pulseaudio', '--check'], 
                              capture_output=True, timeout=5)
        return result.returncode == 0
        
    except Exception:
        return False