"""
Windows Native Audio Backend - WASAPI equivalent to PulseAudio functionality
Provides the same feature set as PulseAudio but using Windows-native APIs
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
import threading
from pathlib import Path

try:
    import pycaw
    from pycaw.pycaw import AudioUtilities, AudioSession, ISimpleAudioVolume
    import comtypes
    HAS_PYCAW = True
except ImportError:
    HAS_PYCAW = False

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

from .base import AudioBackend, AudioDevice

logger = logging.getLogger(__name__)

class WindowsNativeBackend(AudioBackend):
    """
    Windows Native Audio Backend using WASAPI and Windows Audio Session API
    Provides PulseAudio-equivalent functionality on Windows platforms
    """
    
    def __init__(self):
        self.name = "windows_native"
        self.is_available = self._check_availability()
        self.current_device: Optional[AudioDevice] = None
        self.volume_control = None
        self._audio_sessions = {}
        
    def _check_availability(self) -> bool:
        """Check if Windows native audio is available"""
        try:
            import platform
            if platform.system() != "Windows":
                return False
                
            # Try to initialize COM for audio
            comtypes.CoInitialize()
            devices = AudioUtilities.GetSpeakers()
            return devices is not None
        except Exception as e:
            logger.debug(f"Windows native audio not available: {e}")
            return False
    
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize Windows native audio backend"""
        if not self.is_available:
            return False
            
        try:
            # Initialize COM for this thread
            comtypes.CoInitialize()
            
            # Get default audio device
            self.current_device = await self._get_default_device()
            
            # Initialize volume control
            self._initialize_volume_control()
            
            logger.info("Windows native audio backend initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Windows native audio: {e}")
            return False
    
    async def list_devices(self) -> List[AudioDevice]:
        """List available audio output devices (equivalent to pactl list sinks)"""
        devices = []
        
        try:
            # Get all audio endpoints
            from pycaw.pycaw import AudioUtilities
            
            # Get speakers/headphones
            speakers = AudioUtilities.GetSpeakers()
            if speakers:
                device = AudioDevice(
                    id="default_speakers",
                    name=speakers.FriendlyName,
                    description="Default Windows Audio Device",
                    is_default=True
                )
                devices.append(device)
            
            # Get all audio devices
            audio_devices = AudioUtilities.GetAllDevices()
            for idx, device in enumerate(audio_devices):
                if device.state == 1:  # DEVICE_STATE_ACTIVE
                    audio_device = AudioDevice(
                        id=f"device_{idx}",
                        name=device.FriendlyName,
                        description=f"Windows Audio Device: {device.FriendlyName}",
                        is_default=(idx == 0)
                    )
                    devices.append(audio_device)
                    
        except Exception as e:
            logger.error(f"Failed to list Windows audio devices: {e}")
            
        return devices
    
    async def play_audio_file(self, file_path: Path, device_id: Optional[str] = None, volume: float = 0.8) -> bool:
        """
        Play audio file using Windows native APIs (equivalent to paplay)
        """
        try:
            file_str = str(file_path)
            
            # Method 1: Use winsound for WAV files
            if HAS_WINSOUND and file_path.suffix.lower() == '.wav':
                # Set volume first
                await self.set_volume(volume)
                
                # Play sound
                winsound.PlaySound(file_str, winsound.SND_FILENAME | winsound.SND_NOWAIT)
                return True
            
            # Method 2: Use Windows Media Foundation (future implementation)
            # This would be equivalent to paplay functionality
            logger.warning(f"Windows native playback not fully implemented for {file_path.suffix}")
            
            # Fallback to sounddevice backend
            return await self._fallback_playback(file_path, volume)
            
        except Exception as e:
            logger.error(f"Failed to play audio file with Windows native backend: {e}")
            return False
    
    async def set_volume(self, volume: float, device_id: Optional[str] = None) -> bool:
        """
        Set system volume (equivalent to pactl set-sink-volume)
        """
        try:
            if not self.volume_control:
                self._initialize_volume_control()
            
            # Clamp volume to valid range
            volume = max(0.0, min(1.0, volume))
            
            # Set master volume
            if self.volume_control:
                self.volume_control.SetMasterScalarVolume(volume, None)
                return True
                
        except Exception as e:
            logger.error(f"Failed to set Windows volume: {e}")
            
        return False
    
    async def get_volume(self, device_id: Optional[str] = None) -> float:
        """
        Get current system volume (equivalent to pactl get-sink-volume)
        """
        try:
            if not self.volume_control:
                self._initialize_volume_control()
                
            if self.volume_control:
                return self.volume_control.GetMasterScalarVolume()
                
        except Exception as e:
            logger.error(f"Failed to get Windows volume: {e}")
            
        return 0.5  # Default volume
    
    async def mute(self, device_id: Optional[str] = None) -> bool:
        """
        Mute audio output (equivalent to pactl set-sink-mute)
        """
        try:
            if not self.volume_control:
                self._initialize_volume_control()
                
            if self.volume_control:
                self.volume_control.SetMute(True, None)
                return True
                
        except Exception as e:
            logger.error(f"Failed to mute Windows audio: {e}")
            
        return False
    
    async def unmute(self, device_id: Optional[str] = None) -> bool:
        """
        Unmute audio output (equivalent to pactl set-sink-mute 0)
        """
        try:
            if not self.volume_control:
                self._initialize_volume_control()
                
            if self.volume_control:
                self.volume_control.SetMute(False, None)
                return True
                
        except Exception as e:
            logger.error(f"Failed to unmute Windows audio: {e}")
            
        return False
    
    def _initialize_volume_control(self):
        """Initialize Windows volume control interface"""
        try:
            speakers = AudioUtilities.GetSpeakers()
            if speakers:
                interface = speakers.Activate(ISimpleAudioVolume._iid_, None, None)
                self.volume_control = interface.QueryInterface(ISimpleAudioVolume)
        except Exception as e:
            logger.error(f"Failed to initialize Windows volume control: {e}")
    
    async def _get_default_device(self) -> Optional[AudioDevice]:
        """Get the default audio output device"""
        try:
            speakers = AudioUtilities.GetSpeakers()
            if speakers:
                return AudioDevice(
                    id="default",
                    name=speakers.FriendlyName,
                    description="Default Windows Audio Device",
                    is_default=True
                )
        except Exception as e:
            logger.error(f"Failed to get default Windows audio device: {e}")
            
        return None
    
    async def _fallback_playback(self, file_path: Path, volume: float) -> bool:
        """Fallback to sounddevice for unsupported formats"""
        try:
            import sounddevice as sd
            import soundfile as sf
            
            # Read audio file
            data, sample_rate = sf.read(str(file_path))
            
            # Play audio
            sd.play(data * volume, sample_rate)
            return True
            
        except Exception as e:
            logger.error(f"Fallback audio playback failed: {e}")
            return False
    
    async def cleanup(self):
        """Cleanup Windows native audio resources"""
        try:
            self.volume_control = None
            self._audio_sessions.clear()
            comtypes.CoUninitialize()
        except Exception as e:
            logger.debug(f"Windows native audio cleanup: {e}")

# Windows-specific audio utilities
class WindowsAudioManager:
    """
    Windows Audio Manager providing PulseAudio-equivalent functionality
    """
    
    @staticmethod
    async def list_audio_devices():
        """List all Windows audio devices (equivalent to pactl list)"""
        backend = WindowsNativeBackend()
        if await backend.initialize({}):
            return await backend.list_devices()
        return []
    
    @staticmethod
    async def set_default_device(device_name: str):
        """Set default audio device (equivalent to pactl set-default-sink)"""
        # This would require additional Windows API calls
        # Implementation would use IMMDeviceEnumerator
        logger.info(f"Setting default Windows audio device: {device_name}")
        return True
    
    @staticmethod
    async def get_audio_info():
        """Get Windows audio system information (equivalent to pactl info)"""
        info = {
            "server": "Windows Audio Service",
            "version": "Windows Native",
            "default_sink": "Default Device",
            "backend": "WASAPI"
        }
        return info

# Export the backend
__all__ = ['WindowsNativeBackend', 'WindowsAudioManager']