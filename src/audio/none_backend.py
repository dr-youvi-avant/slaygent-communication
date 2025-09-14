#!/usr/bin/env python3
"""
Null audio backend for systems without audio support
Provides a working interface that silently discards audio
"""

import logging
from typing import Dict, List, Optional, Any

import numpy as np

from .base import AudioBackend, AudioDevice, AudioConfig

logger = logging.getLogger(__name__)


class NoneAudioBackend(AudioBackend):
    """Null audio backend that silently discards audio"""
    
    def __init__(self, config: AudioConfig):
        super().__init__(config)
        self.backend_name = "none"
        self._current_volume = 1.0
    
    async def initialize(self) -> bool:
        """Initialize null backend (always succeeds)"""
        self.is_initialized = True
        logger.info("Null audio backend initialized (no sound output)")
        return True
    
    async def shutdown(self):
        """Shutdown null backend"""
        self.is_initialized = False
        logger.info("Null audio backend shutdown")
    
    async def play_audio(self, audio_data: np.ndarray, sample_rate: Optional[int] = None) -> bool:
        """Silently 'play' audio (no actual output)"""
        if not self.is_initialized:
            return False
        
        # Log audio playback simulation
        duration = len(audio_data) / (sample_rate or self.config.sample_rate)
        logger.debug(f"Simulated audio playback: {duration:.2f}s at {sample_rate or self.config.sample_rate}Hz")
        
        return True
    
    async def get_devices(self) -> List[AudioDevice]:
        """Return empty device list"""
        return []
    
    async def get_default_device(self) -> Optional[AudioDevice]:
        """No default device available"""
        return None
    
    async def set_volume(self, volume: float) -> bool:
        """Set volume (simulated)"""
        if not 0.0 <= volume <= 1.0:
            return False
        
        self._current_volume = volume
        logger.debug(f"Simulated volume set to {volume}")
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        """Always reports healthy (null backend)"""
        return {
            "backend": self.backend_name,
            "initialized": self.is_initialized,
            "status": "healthy",
            "note": "No audio output - null backend",
            "volume": self._current_volume
        }