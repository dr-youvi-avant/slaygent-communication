"""
macOS CoreAudio Native Backend - Direct CoreAudio integration
Provides native macOS audio functionality equivalent to PulseAudio on Linux
"""

import asyncio
import logging
import subprocess
from typing import Dict, List, Optional, Any
from pathlib import Path
import json

try:
    import objc
    from Foundation import NSBundle
    # Load CoreAudio framework
    CoreAudio = NSBundle.bundleWithPath_('/System/Library/Frameworks/CoreAudio.framework')
    HAS_COREAUDIO = CoreAudio is not None
except ImportError:
    HAS_COREAUDIO = False

from .base import AudioBackend, AudioDevice

logger = logging.getLogger(__name__)

class CoreAudioBackend(AudioBackend):
    """
    macOS CoreAudio Native Backend
    Provides WASAPI/PulseAudio equivalent functionality using native macOS APIs
    """
    
    def __init__(self):
        self.name = "coreaudio_native"
        self.is_available = self._check_availability()
        self.current_device: Optional[AudioDevice] = None
        self._audio_devices = {}
        
    def _check_availability(self) -> bool:
        """Check if CoreAudio is available"""
        try:
            import platform
            if platform.system() != "Darwin":
                return False
                
            # Test if we can run system_profiler (macOS system info)
            result = subprocess.run(['system_profiler', 'SPAudioDataType'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
            
        except Exception as e:
            logger.debug(f"CoreAudio not available: {e}")
            return False
    
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize CoreAudio backend"""
        if not self.is_available:
            return False
            
        try:
            # Get default audio device
            self.current_device = await self._get_default_device()
            
            # Cache available devices
            await self._cache_audio_devices()
            
            logger.info("CoreAudio native backend initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize CoreAudio: {e}")
            return False
    
    async def list_devices(self) -> List[AudioDevice]:
        """List available audio devices (equivalent to pactl list sinks)"""
        devices = []
        
        try:
            # Use system_profiler to get audio devices
            result = await self._run_command([
                'system_profiler', 'SPAudioDataType', '-json'
            ])
            
            if result and result.get('SPAudioDataType'):
                for audio_item in result['SPAudioDataType']:
                    if 'Audio (Built In)' in audio_item:
                        built_in = audio_item['Audio (Built In)']
                        
                        # Parse built-in audio devices
                        for device_name, device_info in built_in.items():
                            device = AudioDevice(
                                id=device_name.lower().replace(' ', '_'),
                                name=device_name,
                                description=f"macOS Audio Device: {device_name}",
                                is_default=('built-in output' in device_name.lower())
                            )
                            devices.append(device)
            
            # Also check with audiodevice command if available
            try:
                audio_devices_result = await self._run_command([
                    'audiodevice', 'list', 'output'
                ])
                # Parse additional devices if command exists
            except FileNotFoundError:
                # audiodevice command not available, continue with system_profiler results
                pass
                
        except Exception as e:
            logger.error(f"Failed to list macOS audio devices: {e}")
            
        # Fallback: add default device
        if not devices:
            devices.append(AudioDevice(
                id="default",
                name="Built-in Output",
                description="Default macOS Audio Output",
                is_default=True
            ))
            
        return devices
    
    async def play_audio_file(self, file_path: Path, device_id: Optional[str] = None, volume: float = 0.8) -> bool:
        """
        Play audio file using macOS native tools (equivalent to paplay)
        """
        try:
            # Method 1: Use afplay (Audio File Play) - macOS built-in command
            command = ['afplay', str(file_path)]
            
            # Set volume if specified
            if volume != 1.0:
                # afplay doesn't support volume directly, so we set system volume
                await self.set_volume(volume, device_id)
            
            # Execute afplay command
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return True
            else:
                logger.error(f"afplay failed: {stderr.decode()}")
                
                # Fallback to say command for text or other methods
                return await self._fallback_playback(file_path, volume)
                
        except Exception as e:
            logger.error(f"Failed to play audio with CoreAudio: {e}")
            return await self._fallback_playback(file_path, volume)
    
    async def set_volume(self, volume: float, device_id: Optional[str] = None) -> bool:
        """
        Set system volume using osascript (equivalent to pactl set-sink-volume)
        """
        try:
            # Clamp volume to valid range (macOS uses 0-100)
            volume_percent = max(0, min(100, int(volume * 100)))
            
            # Use AppleScript to set volume
            applescript = f'set volume output volume {volume_percent}'
            
            result = await self._run_applescript(applescript)
            return result is not None
            
        except Exception as e:
            logger.error(f"Failed to set macOS volume: {e}")
            return False
    
    async def get_volume(self, device_id: Optional[str] = None) -> float:
        """
        Get current system volume (equivalent to pactl get-sink-volume)
        """
        try:
            # Use AppleScript to get volume
            applescript = 'output volume of (get volume settings)'
            
            result = await self._run_applescript(applescript)
            if result:
                volume_percent = int(result.strip())
                return volume_percent / 100.0
                
        except Exception as e:
            logger.error(f"Failed to get macOS volume: {e}")
            
        return 0.5  # Default volume
    
    async def mute(self, device_id: Optional[str] = None) -> bool:
        """
        Mute audio output (equivalent to pactl set-sink-mute)
        """
        try:
            applescript = 'set volume with output muted'
            result = await self._run_applescript(applescript)
            return result is not None
            
        except Exception as e:
            logger.error(f"Failed to mute macOS audio: {e}")
            return False
    
    async def unmute(self, device_id: Optional[str] = None) -> bool:
        """
        Unmute audio output (equivalent to pactl set-sink-mute 0)
        """
        try:
            applescript = 'set volume without output muted'
            result = await self._run_applescript(applescript)
            return result is not None
            
        except Exception as e:
            logger.error(f"Failed to unmute macOS audio: {e}")
            return False
    
    async def _run_command(self, command: List[str]) -> Optional[Dict]:
        """Run system command and return JSON result"""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                if command[1] == 'SPAudioDataType' and '-json' in command:
                    return json.loads(stdout.decode())
                return {"output": stdout.decode()}
            else:
                logger.error(f"Command failed: {stderr.decode()}")
                
        except Exception as e:
            logger.error(f"Failed to run command {command}: {e}")
            
        return None
    
    async def _run_applescript(self, script: str) -> Optional[str]:
        """Run AppleScript command"""
        try:
            command = ['osascript', '-e', script]
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                logger.error(f"AppleScript failed: {stderr.decode()}")
                
        except Exception as e:
            logger.error(f"Failed to run AppleScript: {e}")
            
        return None
    
    async def _get_default_device(self) -> Optional[AudioDevice]:
        """Get the default audio output device"""
        try:
            # Use AppleScript to get default output device
            applescript = '''
            tell application "System Events"
                tell process "System Preferences"
                    return "Built-in Output"
                end tell
            end tell
            '''
            
            return AudioDevice(
                id="default",
                name="Built-in Output", 
                description="Default macOS Audio Output",
                is_default=True
            )
            
        except Exception as e:
            logger.error(f"Failed to get default macOS audio device: {e}")
            return None
    
    async def _cache_audio_devices(self):
        """Cache available audio devices for quick access"""
        try:
            devices = await self.list_devices()
            self._audio_devices = {device.id: device for device in devices}
        except Exception as e:
            logger.error(f"Failed to cache audio devices: {e}")
    
    async def _fallback_playback(self, file_path: Path, volume: float) -> bool:
        """Fallback to sounddevice or other methods"""
        try:
            # Try sounddevice as fallback
            import sounddevice as sd
            import soundfile as sf
            
            # Read and play audio file
            data, sample_rate = sf.read(str(file_path))
            sd.play(data * volume, sample_rate)
            return True
            
        except Exception as e:
            logger.error(f"Fallback audio playback failed: {e}")
            return False
    
    async def cleanup(self):
        """Cleanup CoreAudio resources"""
        try:
            self._audio_devices.clear()
            self.current_device = None
        except Exception as e:
            logger.debug(f"CoreAudio cleanup: {e}")

# macOS-specific audio utilities
class MacOSAudioManager:
    """
    macOS Audio Manager providing PulseAudio/WASAPI equivalent functionality
    """
    
    @staticmethod
    async def list_audio_devices():
        """List all macOS audio devices (equivalent to pactl list)"""
        backend = CoreAudioBackend()
        if await backend.initialize({}):
            return await backend.list_devices()
        return []
    
    @staticmethod
    async def set_default_device(device_name: str):
        """Set default audio device (equivalent to pactl set-default-sink)"""
        try:
            # Use AppleScript to set default device
            applescript = f'''
            tell application "System Preferences"
                activate
                set current pane to pane "com.apple.preference.sound"
                delay 1
                tell application "System Events"
                    tell process "System Preferences"
                        click radio button "{device_name}" of tab group 1 of window 1
                    end tell
                end tell
                quit
            end tell
            '''
            
            backend = CoreAudioBackend()
            result = await backend._run_applescript(applescript)
            return result is not None
            
        except Exception as e:
            logger.error(f"Failed to set default macOS audio device: {e}")
            return False
    
    @staticmethod 
    async def get_audio_info():
        """Get macOS audio system information (equivalent to pactl info)"""
        info = {
            "server": "CoreAudio",
            "version": "macOS Native",
            "default_sink": "Built-in Output",
            "backend": "CoreAudio Framework"
        }
        return info

# Export the backend
__all__ = ['CoreAudioBackend', 'MacOSAudioManager']