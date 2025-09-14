#!/usr/bin/env python3
"""
SoundDevice-based audio backend for cross-platform audio support
Primary backend for Windows, macOS, and Linux with sounddevice
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
import threading

import numpy as np
import sounddevice as sd
import soundfile as sf

from .base import AudioBackend, AudioDevice, AudioConfig
from .base import AudioError, AudioInitializationError, AudioPlaybackError, AudioDeviceError

logger = logging.getLogger(__name__)


class SoundDeviceBackend(AudioBackend):
    """SoundDevice cross-platform audio backend"""
    
    def __init__(self, config: AudioConfig):
        super().__init__(config)
        self.backend_name = "sounddevice"
        self._playback_lock = threading.Lock()
        self._current_volume = 1.0
    
    async def initialize(self) -> bool:
        """Initialize SoundDevice backend"""
        try:
            # Check if sounddevice is available
            devices = sd.query_devices()
            if not devices:
                raise AudioInitializationError("No audio devices found")
            
            # Set default device if specified
            if self.config.device_id is not None:
                try:
                    sd.default.device = self.config.device_id
                    logger.info(f"Set default audio device to ID {self.config.device_id}")
                except Exception as e:
                    logger.warning(f"Failed to set device {self.config.device_id}: {e}")
            
            # Test audio output
            try:
                test_tone = self._generate_test_tone(duration=0.1)
                sd.play(test_tone, samplerate=self.config.sample_rate, blocking=True)
                logger.info("Audio test successful")
            except Exception as e:
                logger.warning(f"Audio test failed: {e}")
            
            self.is_initialized = True
            logger.info("SoundDevice backend initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize SoundDevice backend: {e}")
            self.is_initialized = False
            return False
    
    async def shutdown(self):
        """Shutdown SoundDevice backend"""
        try:
            # Stop any ongoing playback
            sd.stop()
            self.is_initialized = False
            logger.info("SoundDevice backend shutdown")
        except Exception as e:
            logger.error(f"Error during SoundDevice shutdown: {e}")
    
    def _generate_test_tone(self, frequency: float = 440.0, duration: float = 0.1) -> np.ndarray:
        """Generate a test tone for audio verification"""
        t = np.linspace(0, duration, int(self.config.sample_rate * duration), False)
        tone = np.sin(2 * np.pi * frequency * t) * 0.1  # Low volume
        return tone.astype(np.float32)
    
    async def play_audio(self, audio_data: np.ndarray, sample_rate: Optional[int] = None) -> bool:
        """Play audio data using SoundDevice"""
        if not self.is_initialized:
            raise AudioPlaybackError("Audio backend not initialized")
        
        try:
            # Use provided sample rate or default
            sr = sample_rate or self.config.sample_rate
            
            # Apply volume
            volume_adjusted_data = audio_data * self._current_volume
            
            # Ensure audio data is in correct format
            if volume_adjusted_data.dtype != np.float32:
                volume_adjusted_data = volume_adjusted_data.astype(np.float32)
            
            # Play audio in separate thread to avoid blocking
            def play_sync():
                with self._playback_lock:
                    sd.play(volume_adjusted_data, samplerate=sr, blocking=True)
            
            # Run in thread pool to make it async
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, play_sync)
            
            return True
            
        except Exception as e:
            logger.error(f"Audio playback failed: {e}")
            raise AudioPlaybackError(f"SoundDevice playback error: {e}")
    
    async def get_devices(self) -> List[AudioDevice]:
        """Get list of available audio output devices"""
        try:
            devices = sd.query_devices()
            audio_devices = []
            
            for i, device in enumerate(devices):
                # Only include output devices
                if device['max_output_channels'] > 0:
                    audio_device = AudioDevice(
                        device_id=i,
                        name=device['name'],
                        channels=device['max_output_channels'],
                        sample_rate=int(device['default_samplerate']),
                        is_default=(i == sd.default.device[1]),  # Output device
                        backend=self.backend_name
                    )
                    audio_devices.append(audio_device)
            
            return audio_devices
            
        except Exception as e:
            logger.error(f"Failed to get audio devices: {e}")
            raise AudioDeviceError(f"Device enumeration failed: {e}")
    
    async def get_default_device(self) -> Optional[AudioDevice]:
        """Get default audio output device"""
        try:
            devices = await self.get_devices()
            for device in devices:
                if device.is_default:
                    return device
            
            # Fallback to first available device
            return devices[0] if devices else None
            
        except Exception as e:
            logger.error(f"Failed to get default device: {e}")
            return None
    
    async def set_volume(self, volume: float) -> bool:
        """Set playback volume (0.0 to 1.0)"""
        if not 0.0 <= volume <= 1.0:
            raise AudioError("Volume must be between 0.0 and 1.0")
        
        self._current_volume = volume
        logger.debug(f"Volume set to {volume}")
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        """Check SoundDevice backend health"""
        health = {
            "backend": self.backend_name,
            "initialized": self.is_initialized,
            "status": "unknown"
        }
        
        try:
            if not self.is_initialized:
                health["status"] = "not_initialized"
                return health
            
            # Check device availability
            devices = sd.query_devices()
            output_devices = [d for d in devices if d['max_output_channels'] > 0]
            
            health.update({
                "status": "healthy",
                "total_devices": len(devices),
                "output_devices": len(output_devices),
                "default_device": sd.default.device,
                "sample_rate": self.config.sample_rate,
                "channels": self.config.channels,
                "volume": self._current_volume
            })
            
            # Test audio capability
            try:
                test_tone = self._generate_test_tone(duration=0.01)  # Very short test
                # Don't actually play during health check, just verify we can create audio
                health["audio_generation"] = "working"
            except Exception as e:
                health["audio_generation"] = f"failed: {e}"
            
        except Exception as e:
            health.update({
                "status": "unhealthy",
                "error": str(e)
            })
        
        return health


# Convenience functions for sounddevice backend

async def create_sounddevice_backend(config: AudioConfig) -> SoundDeviceBackend:
    """Create and initialize SoundDevice backend"""
    backend = SoundDeviceBackend(config)
    await backend.initialize()
    return backend


def is_sounddevice_available() -> bool:
    """Check if SoundDevice is available on this system"""
    try:
        import sounddevice
        import soundfile
        
        # Try to query devices
        devices = sounddevice.query_devices()
        return len(devices) > 0
        
    except ImportError:
        return False
    except Exception:
        return False