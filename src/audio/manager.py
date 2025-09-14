#!/usr/bin/env python3
"""
Cross-platform audio manager for Slaygent Communication System
Automatically selects best available audio backend for each OS
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Type
import numpy as np

from .base import AudioBackend, AudioDevice, AudioConfig, AudioError
from ..config.manager import SlaygentConfig, get_config
from ..utils.os_utils import get_os_detector, SupportedOS

logger = logging.getLogger(__name__)


class AudioManager:
    """Cross-platform audio manager with automatic backend selection"""
    
    def __init__(self, config: Optional[SlaygentConfig] = None):
        self.config = config or get_config()
        self.os_detector = get_os_detector()
        self.active_backend: Optional[AudioBackend] = None
        self.backend_name = "none"
        self.is_initialized = False
        
        # Audio configuration from config
        self.audio_config = AudioConfig(
            sample_rate=self.config.audio.sample_rate,
            channels=self.config.audio.channels,
            device_id=self.config.audio.device_id
        )
    
    async def initialize(self) -> bool:
        """Initialize audio system with best available backend"""
        
        # Determine backend based on configuration and OS
        backend_preference = self.config.audio.backend.lower()
        
        if backend_preference == "auto":
            backend_preference = self._get_auto_backend()
        
        # Try to initialize preferred backend
        success = await self._try_backend(backend_preference)
        
        if not success:
            # Fall back to other backends in order of preference
            fallback_order = self._get_fallback_order(backend_preference)
            
            for backend_name in fallback_order:
                if await self._try_backend(backend_name):
                    success = True
                    break
        
        if success:
            logger.info(f"Audio system initialized with {self.backend_name} backend")
        else:
            logger.error("Failed to initialize any audio backend")
        
        return success
    
    def _get_auto_backend(self) -> str:
        """Determine best backend automatically based on OS"""
        if self.os_detector.is_windows:
            # Windows: Try native WASAPI first, fallback to sounddevice
            return "windows_native"
        elif self.os_detector.is_linux:
            # Linux: PulseAudio > JACK > ALSA Low-Latency > sounddevice
            return "pulse"
        elif self.os_detector.is_macos:
            # macOS: CoreAudio native > JACK > sounddevice
            return "coreaudio_native"
        else:
            return "sounddevice"  # Universal fallback
    
    def _get_fallback_order(self, preferred: str) -> List[str]:
        """Get fallback order for backend selection"""
        # Define all possible backends
        all_backends = ["windows_native", "coreaudio_native", "pulse", "jack_audio", "alsa_low_latency", "sounddevice", "none"]
        
        # Remove preferred from list
        if preferred in all_backends:
            all_backends.remove(preferred)
        
        # Filter by OS availability and set priority order
        available_backends = []
        
        if self.os_detector.is_linux:
            # Linux: PulseAudio > JACK > ALSA LL > sounddevice > none
            available_backends = ["pulse", "jack_audio", "alsa_low_latency", "sounddevice", "none"]
        elif self.os_detector.is_windows:
            # Windows: Native WASAPI > sounddevice > none
            available_backends = ["windows_native", "sounddevice", "none"]
        elif self.os_detector.is_macos:
            # macOS: CoreAudio > JACK > sounddevice > none
            available_backends = ["coreaudio_native", "jack_audio", "sounddevice", "none"]
        else:
            available_backends = ["sounddevice", "none"]
        
        # Remove already tried backend
        return [b for b in available_backends if b != preferred]
    
    async def _try_backend(self, backend_name: str) -> bool:
        """Try to initialize a specific backend"""
        try:
            if backend_name == "sounddevice":
                return await self._init_sounddevice()
            elif backend_name == "pulse":
                return await self._init_pulseaudio()
            elif backend_name == "windows_native":
                return await self._init_windows_native()
            elif backend_name == "coreaudio_native":
                return await self._init_coreaudio_native()
            elif backend_name == "jack_audio":
                return await self._init_jack_audio()
            elif backend_name == "alsa_low_latency":
                return await self._init_alsa_low_latency()
            elif backend_name == "none":
                return await self._init_none_backend()
            else:
                logger.warning(f"Unknown backend: {backend_name}")
                return False
                
        except Exception as e:
            logger.debug(f"Backend {backend_name} failed to initialize: {e}")
            return False
    
    async def _init_sounddevice(self) -> bool:
        """Initialize SoundDevice backend"""
        try:
            from .sounddevice_backend import SoundDeviceBackend, is_sounddevice_available
            
            if not is_sounddevice_available():
                logger.debug("SoundDevice not available")
                return False
            
            backend = SoundDeviceBackend(self.audio_config)
            if await backend.initialize():
                self.active_backend = backend
                self.backend_name = "sounddevice"
                self.is_initialized = True
                return True
            
        except ImportError:
            logger.debug("SoundDevice backend not available (import error)")
        except Exception as e:
            logger.debug(f"SoundDevice initialization failed: {e}")
        
        return False
    
    async def _init_pulseaudio(self) -> bool:
        """Initialize PulseAudio backend (Linux only)"""
        if not self.os_detector.is_linux:
            return False
        
        try:
            from .pulse_backend import PulseAudioBackend, is_pulseaudio_available
            
            if not is_pulseaudio_available():
                logger.debug("PulseAudio not available")
                return False
            
            backend = PulseAudioBackend(self.audio_config)
            if await backend.initialize():
                self.active_backend = backend
                self.backend_name = "pulse"
                self.is_initialized = True
                return True
            
        except ImportError:
            logger.debug("PulseAudio backend not available (import error)")
        except Exception as e:
            logger.debug(f"PulseAudio initialization failed: {e}")
        
        return False
    
    async def _init_windows_native(self) -> bool:
        """Initialize Windows Native WASAPI backend (Windows only)"""
        if not self.os_detector.is_windows:
            return False
        
        try:
            from .windows_native_backend import WindowsNativeBackend
            
            backend = WindowsNativeBackend()
            if await backend.initialize({}):
                self.active_backend = backend
                self.backend_name = "windows_native"
                self.is_initialized = True
                return True
            
        except ImportError:
            logger.debug("Windows native backend not available (import error)")
        except Exception as e:
            logger.debug(f"Windows native initialization failed: {e}")
        
        return False
    
    async def _init_coreaudio_native(self) -> bool:
        """Initialize CoreAudio native backend (macOS only)"""
        if not self.os_detector.is_macos:
            return False
        
        try:
            from .coreaudio_backend import CoreAudioBackend
            
            backend = CoreAudioBackend()
            if await backend.initialize({}):
                self.active_backend = backend
                self.backend_name = "coreaudio_native"
                self.is_initialized = True
                return True
            
        except ImportError:
            logger.debug("CoreAudio native backend not available (import error)")
        except Exception as e:
            logger.debug(f"CoreAudio native initialization failed: {e}")
        
        return False
    
    async def _init_jack_audio(self) -> bool:
        """Initialize JACK Audio backend (Linux/macOS professional audio)"""
        if self.os_detector.is_windows:
            return False  # JACK typically not used on Windows
        
        try:
            from .low_latency_backends import JackAudioBackend
            
            backend = JackAudioBackend()
            if await backend.initialize({}):
                self.active_backend = backend
                self.backend_name = "jack_audio"
                self.is_initialized = True
                return True
            
        except ImportError:
            logger.debug("JACK Audio backend not available (import error)")
        except Exception as e:
            logger.debug(f"JACK Audio initialization failed: {e}")
        
        return False
    
    async def _init_alsa_low_latency(self) -> bool:
        """Initialize ALSA Low-Latency backend (Linux only)"""
        if not self.os_detector.is_linux:
            return False
        
        try:
            from .low_latency_backends import ALSALowLatencyBackend
            
            backend = ALSALowLatencyBackend()
            if await backend.initialize({}):
                self.active_backend = backend
                self.backend_name = "alsa_low_latency"
                self.is_initialized = True
                return True
            
        except ImportError:
            logger.debug("ALSA Low-Latency backend not available (import error)")
        except Exception as e:
            logger.debug(f"ALSA Low-Latency initialization failed: {e}")
        
        return False
    
    async def _init_none_backend(self) -> bool:
        """Initialize null audio backend (no sound output)"""
        try:
            from .none_backend import NoneAudioBackend
            
            backend = NoneAudioBackend(self.audio_config)
            if await backend.initialize():
                self.active_backend = backend
                self.backend_name = "none"
                self.is_initialized = True
                logger.warning("Using null audio backend (no sound output)")
                return True
                
        except ImportError:
            logger.debug("None backend not available")
        except Exception as e:
            logger.debug(f"None backend initialization failed: {e}")
        
        return False
    
    async def shutdown(self):
        """Shutdown audio system"""
        if self.active_backend:
            await self.active_backend.shutdown()
            self.active_backend = None
        
        self.is_initialized = False
        self.backend_name = "none"
        logger.info("Audio system shutdown")
    
    # Public API methods
    
    async def play_audio(self, audio_data: np.ndarray, sample_rate: Optional[int] = None) -> bool:
        """Play audio data"""
        if not self.active_backend:
            raise AudioError("Audio system not initialized")
        
        return await self.active_backend.play_audio(audio_data, sample_rate)
    
    async def play_audio_file(self, file_path: str) -> bool:
        """Play audio file"""
        try:
            import soundfile as sf
            audio_data, sample_rate = sf.read(file_path)
            return await self.play_audio(audio_data, sample_rate)
        except ImportError:
            logger.error("soundfile not available, cannot play audio files")
            return False
        except Exception as e:
            logger.error(f"Failed to play audio file {file_path}: {e}")
            return False
    
    async def get_devices(self) -> List[AudioDevice]:
        """Get list of available audio devices"""
        if not self.active_backend:
            return []
        
        return await self.active_backend.get_devices()
    
    async def get_default_device(self) -> Optional[AudioDevice]:
        """Get default audio device"""
        if not self.active_backend:
            return None
        
        return await self.active_backend.get_default_device()
    
    async def set_volume(self, volume: float) -> bool:
        """Set playback volume (0.0 to 1.0)"""
        if not self.active_backend:
            return False
        
        return await self.active_backend.set_volume(volume)
    
    async def set_device(self, device_id: int) -> bool:
        """Set audio output device"""
        if not self.active_backend:
            return False
        
        # Update config
        self.audio_config.device_id = device_id
        
        # Reinitialize backend with new device
        backend_name = self.backend_name
        await self.active_backend.shutdown()
        self.active_backend = None
        self.is_initialized = False
        
        return await self._try_backend(backend_name)
    
    def get_backend_name(self) -> str:
        """Get current audio backend name"""
        return self.backend_name
    
    def is_audio_available(self) -> bool:
        """Check if audio output is available"""
        return self.is_initialized and self.backend_name != "none"
    
    async def health_check(self) -> Dict[str, Any]:
        """Get audio system health status"""
        health = {
            "initialized": self.is_initialized,
            "backend": self.backend_name,
            "audio_available": self.is_audio_available(),
            "os": self.os_detector.os_type.value
        }
        
        if self.active_backend:
            try:
                backend_health = await self.active_backend.health_check()
                health["backend_health"] = backend_health
            except Exception as e:
                health["backend_health"] = {"error": str(e)}
        
        return health


# Global audio manager instance
_audio_manager: Optional[AudioManager] = None


async def get_audio_manager() -> AudioManager:
    """Get singleton audio manager instance"""
    global _audio_manager
    
    if _audio_manager is None:
        _audio_manager = AudioManager()
        await _audio_manager.initialize()
    
    return _audio_manager


async def shutdown_audio():
    """Shutdown global audio manager"""
    global _audio_manager
    
    if _audio_manager:
        await _audio_manager.shutdown()
        _audio_manager = None


# Convenience functions

async def play_audio(audio_data: np.ndarray, sample_rate: Optional[int] = None) -> bool:
    """Play audio data using global audio manager"""
    manager = await get_audio_manager()
    return await manager.play_audio(audio_data, sample_rate)


async def play_audio_file(file_path: str) -> bool:
    """Play audio file using global audio manager"""
    manager = await get_audio_manager()
    return await manager.play_audio_file(file_path)