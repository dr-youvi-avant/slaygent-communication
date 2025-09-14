#!/usr/bin/env python3
"""
Cross-platform OS utilities for Slaygent Communication System
Provides OS detection and platform-specific optimizations.
"""

import platform
import sys
from enum import Enum
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SupportedOS(Enum):
    """Supported operating systems"""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "darwin"
    UNKNOWN = "unknown"


class OSDetector:
    """Cross-platform OS detection and capability assessment"""
    
    _instance = None
    _os_info = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._os_info is None:
            self._detect_os()
    
    def _detect_os(self):
        """Detect current operating system and capabilities"""
        system = platform.system().lower()
        
        if system == "windows":
            self._os_info = {
                "os": SupportedOS.WINDOWS,
                "version": platform.version(),
                "architecture": platform.architecture()[0],
                "is_wsl": self._detect_wsl(),
                "powershell_available": self._check_powershell(),
                "audio_backend": "sounddevice",
                "process_cmd": ["tasklist", "/FO", "CSV"],
                "shell": "powershell" if self._check_powershell() else "cmd"
            }
        elif system == "linux":
            self._os_info = {
                "os": SupportedOS.LINUX,
                "version": platform.version(),
                "architecture": platform.architecture()[0],
                "is_wsl": self._detect_wsl(),
                "audio_backend": self._detect_linux_audio(),
                "process_cmd": ["ps", "aux"],
                "shell": "bash"
            }
        elif system == "darwin":
            self._os_info = {
                "os": SupportedOS.MACOS,
                "version": platform.mac_ver()[0],
                "architecture": platform.architecture()[0],
                "is_wsl": False,
                "audio_backend": "sounddevice",  # CoreAudio via sounddevice
                "process_cmd": ["ps", "aux"],
                "shell": "zsh"
            }
        else:
            self._os_info = {
                "os": SupportedOS.UNKNOWN,
                "version": "unknown",
                "architecture": "unknown",
                "is_wsl": False,
                "audio_backend": "none",
                "process_cmd": ["ps", "aux"],
                "shell": "sh"
            }
        
        logger.info(f"Detected OS: {self._os_info['os'].value} ({self._os_info['version']})")
    
    def _detect_wsl(self) -> bool:
        """Detect if running in WSL (Windows Subsystem for Linux)"""
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
        except (FileNotFoundError, PermissionError):
            return False
    
    def _check_powershell(self) -> bool:
        """Check if PowerShell is available on Windows"""
        try:
            import subprocess
            result = subprocess.run(
                ["powershell", "-Command", "echo 'test'"],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False
    
    def _detect_linux_audio(self) -> str:
        """Detect available audio backend on Linux"""
        try:
            import subprocess
            
            # Check for PulseAudio
            result = subprocess.run(["pulseaudio", "--check"], 
                                  capture_output=True, timeout=2)
            if result.returncode == 0:
                return "pulse"
            
            # Check for ALSA
            result = subprocess.run(["aplay", "--version"], 
                                  capture_output=True, timeout=2)
            if result.returncode == 0:
                return "alsa"
            
            # Fallback to sounddevice
            return "sounddevice"
            
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return "sounddevice"
    
    @property
    def os_type(self) -> SupportedOS:
        """Get detected OS type"""
        return self._os_info["os"]
    
    @property
    def is_windows(self) -> bool:
        """Check if running on Windows"""
        return self._os_info["os"] == SupportedOS.WINDOWS
    
    @property
    def is_linux(self) -> bool:
        """Check if running on Linux"""
        return self._os_info["os"] == SupportedOS.LINUX
    
    @property
    def is_macos(self) -> bool:
        """Check if running on macOS"""
        return self._os_info["os"] == SupportedOS.MACOS
    
    @property
    def is_wsl(self) -> bool:
        """Check if running in WSL"""
        return self._os_info.get("is_wsl", False)
    
    @property
    def audio_backend(self) -> str:
        """Get recommended audio backend"""
        return self._os_info["audio_backend"]
    
    @property
    def process_command(self) -> list:
        """Get OS-appropriate process listing command"""
        return self._os_info["process_cmd"]
    
    @property
    def shell(self) -> str:
        """Get default shell for OS"""
        return self._os_info["shell"]
    
    def get_info(self) -> Dict[str, Any]:
        """Get complete OS information"""
        return self._os_info.copy()
    
    def is_supported(self) -> bool:
        """Check if current OS is supported"""
        return self._os_info["os"] != SupportedOS.UNKNOWN


def get_os_detector() -> OSDetector:
    """Get singleton OS detector instance"""
    return OSDetector()


def get_path_separator() -> str:
    """Get OS-appropriate path separator"""
    detector = get_os_detector()
    return "\\" if detector.is_windows else "/"


def get_executable_extension() -> str:
    """Get OS-appropriate executable extension"""
    detector = get_os_detector()
    return ".exe" if detector.is_windows else ""


def normalize_path(path: str) -> str:
    """Normalize path for current OS"""
    import os
    return os.path.normpath(path)


def get_home_directory() -> str:
    """Get user home directory cross-platform"""
    import os
    return os.path.expanduser("~")


def get_config_directory() -> str:
    """Get appropriate config directory for OS"""
    detector = get_os_detector()
    home = get_home_directory()
    
    if detector.is_windows:
        # Use AppData/Local on Windows
        appdata = os.environ.get('LOCALAPPDATA')
        if appdata:
            return os.path.join(appdata, 'SlaygentComm')
        return os.path.join(home, 'AppData', 'Local', 'SlaygentComm')
    elif detector.is_macos:
        # Use ~/Library/Application Support on macOS
        return os.path.join(home, 'Library', 'Application Support', 'SlaygentComm')
    else:
        # Use ~/.config on Linux/Unix
        config_home = os.environ.get('XDG_CONFIG_HOME')
        if config_home:
            return os.path.join(config_home, 'slaygent-comm')
        return os.path.join(home, '.config', 'slaygent-comm')


# Convenience functions for common OS checks
os_detector = get_os_detector()
IS_WINDOWS = os_detector.is_windows
IS_LINUX = os_detector.is_linux
IS_MACOS = os_detector.is_macos
IS_WSL = os_detector.is_wsl