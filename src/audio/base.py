#!/usr/bin/env python3
"""
Abstract base class for cross-platform audio backends
Supports Windows (sounddevice), Linux (pulse/alsa), and macOS (CoreAudio)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AudioDevice:
    """Audio device information"""
    device_id: int
    name: str
    channels: int
    sample_rate: int
    is_default: bool = False
    backend: str = "unknown"


@dataclass
class AudioConfig:
    """Audio configuration for playback"""
    sample_rate: int = 22050
    channels: int = 1
    device_id: Optional[int] = None
    buffer_size: int = 1024
    volume: float = 1.0  # 0.0 to 1.0


class AudioBackend(ABC):
    """Abstract base class for audio backends"""
    
    def __init__(self, config: AudioConfig):
        self.config = config
        self.is_initialized = False
        self.backend_name = "unknown"
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize audio backend"""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """Shutdown audio backend"""
        pass
    
    @abstractmethod
    async def play_audio(self, audio_data: np.ndarray, sample_rate: Optional[int] = None) -> bool:
        """Play audio data"""
        pass
    
    @abstractmethod
    async def get_devices(self) -> List[AudioDevice]:
        """Get list of available audio devices"""
        pass
    
    @abstractmethod
    async def get_default_device(self) -> Optional[AudioDevice]:
        """Get default audio output device"""
        pass
    
    @abstractmethod
    async def set_volume(self, volume: float) -> bool:
        """Set playback volume (0.0 to 1.0)"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check audio backend health"""
        pass
    
    def get_backend_name(self) -> str:
        """Get backend name"""
        return self.backend_name


class AudioError(Exception):
    """Base audio error"""
    pass


class AudioInitializationError(AudioError):
    """Audio initialization error"""
    pass


class AudioPlaybackError(AudioError):
    """Audio playback error"""  
    pass


class AudioDeviceError(AudioError):
    """Audio device error"""
    pass