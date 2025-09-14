#!/usr/bin/env python3
"""
Cross-platform OS utilities for Slaygent Communication System
Provides OS detection and platform-specific optimizations.
"""

import platform
import sys
from enum import Enum
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SupportedOS(Enum):
    """Supported operating systems"""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
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
    
    @classmethod
    def _reset_instance(cls):
        """Reset singleton instance for testing purposes."""
        cls._instance = None
        cls._os_info = None
    
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


class OSUtils:
    """Static utility class for OS-related operations.
    
    Provides a static interface to OS detection and utility functions
    for compatibility with existing tests and code.
    """
    
    @staticmethod
    def get_os_type() -> str:
        """Get the operating system type as a string."""
        detector = get_os_detector()
        return detector.os_type.value
    
    @staticmethod
    def is_windows() -> bool:
        """Check if running on Windows."""
        detector = get_os_detector()
        return detector.is_windows
    
    @staticmethod
    def is_linux() -> bool:
        """Check if running on Linux."""
        detector = get_os_detector()
        return detector.is_linux
    
    @staticmethod
    def is_macos() -> bool:
        """Check if running on macOS."""
        detector = get_os_detector()
        return detector.is_macos
    
    @staticmethod
    def detect_wsl() -> bool:
        """Detect if running in WSL."""
        detector = get_os_detector()
        return detector.is_wsl
    
    @staticmethod
    def get_preferred_audio_backend() -> str:
        """Get the preferred audio backend for the current OS."""
        detector = get_os_detector()
        return detector.audio_backend
    
    @staticmethod
    def check_audio_system_availability(backend: str) -> bool:
        """Check if a specific audio system is available."""
        if backend == 'pulse':
            import shutil
            import subprocess
            try:
                if shutil.which('pulseaudio'):
                    result = subprocess.run(['pulseaudio', '--check'], 
                                          capture_output=True, timeout=2)
                    return result.returncode == 0
                return False
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                return False
        
        elif backend == 'sounddevice':
            try:
                import importlib
                sd = importlib.import_module('sounddevice')
                devices = sd.query_devices()
                return len(devices) > 0
            except (ImportError, OSError):
                return False
        
        return False
    
    @staticmethod
    def get_config_dir() -> str:
        """Get the configuration directory for the current OS."""
        return get_config_dir()
    
    @staticmethod
    def get_cache_dir() -> str:
        """Get the cache directory for the current OS."""
        import os
        home = os.path.expanduser('~')
        detector = get_os_detector()
        
        if detector.is_windows:
            # Use LOCALAPPDATA on Windows
            local_app_data = os.environ.get('LOCALAPPDATA')
            if local_app_data:
                return os.path.join(local_app_data, 'Slaygent', 'Cache')
            return os.path.join(home, 'AppData', 'Local', 'Slaygent', 'Cache')
        elif detector.is_macos:
            # Use ~/Library/Caches on macOS
            return os.path.join(home, 'Library', 'Caches', 'SlaygentComm')
        else:
            # Use ~/.cache on Linux/Unix
            cache_home = os.environ.get('XDG_CACHE_HOME')
            if cache_home:
                return os.path.join(cache_home, 'slaygent-comm')
            return os.path.join(home, '.cache', 'slaygent-comm')
    
    @staticmethod
    def resolve_path(path: str, base_dir: Optional[Path] = None) -> Path:
        """Resolve a path with support for relative paths and home directory."""
        import os
        from pathlib import Path
        
        # Expand user home directory
        if path.startswith('~'):
            path = os.path.expanduser(path)
        
        path_obj = Path(path)
        
        # If absolute path, return as is
        if path_obj.is_absolute():
            return path_obj
        
        # If relative path and base_dir provided, resolve relative to base_dir
        if base_dir:
            return base_dir / path_obj
        
        # Otherwise, resolve relative to current working directory
        return Path.cwd() / path_obj
    
    @staticmethod
    def get_python_executable() -> str:
        """Get the current Python executable path."""
        import sys
        return sys.executable
    
    @staticmethod
    def find_executable(name: str) -> Optional[str]:
        """Find an executable in the system PATH."""
        import shutil
        return shutil.which(name)
    
    @staticmethod
    def get_process_list() -> list:
        """Get a list of running processes."""
        try:
            import psutil
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'status']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return processes
        except ImportError:
            logger.warning("psutil not available, cannot get process list")
            return []
    
    @staticmethod
    def check_port_availability(host: str, port: int) -> bool:
        """Check if a port is available for binding."""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                return result != 0  # Port is available if connection fails
        except socket.error:
            return False
    
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """Get comprehensive system information."""
        import sys
        import platform
        detector = get_os_detector()
        return {
            'os_type': detector.os_type.value,
            'version': detector._os_info.get('version', 'unknown'),
            'architecture': detector._os_info.get('architecture', 'unknown'),
            'is_wsl': detector.is_wsl,
            'audio_backend': detector.preferred_audio_backend,
            'shell': detector._os_info.get('shell', 'unknown'),
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'platform': platform.platform()
        }
    
    @staticmethod
    def check_dependency_available(module_name: str) -> bool:
        """Check if a Python module dependency is available."""
        try:
            import importlib
            importlib.import_module(module_name)
            return True
        except ImportError:
            return False
    
    @staticmethod
    def get_memory_info() -> Dict[str, int]:
        """Get system memory information."""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return {
                'total': memory.total,
                'available': memory.available,
                'percent': memory.percent,
                'used': memory.used,
                'free': memory.free
            }
        except ImportError:
            logger.warning("psutil not available, cannot get memory info")
            return {}
    
    @staticmethod
    def is_virtual_environment() -> bool:
        """Check if running in a virtual environment."""
        import os
        import sys
        return (
            hasattr(sys, 'real_prefix') or
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or
            os.environ.get('VIRTUAL_ENV') is not None or
            os.environ.get('CONDA_DEFAULT_ENV') is not None
        )
    
    @staticmethod
    def get_shell_type() -> str:
        """Get the current shell type."""
        detector = get_os_detector()
        return detector._os_info.get('shell', 'unknown')
    
    @staticmethod
    def is_admin_user() -> bool:
        """Check if running as administrator/root user."""
        import os
        detector = get_os_detector()
        
        if detector.is_windows:
            try:
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            except (ImportError, AttributeError):
                return False
        else:
            return os.getuid() == 0
    
    @staticmethod
    def get_terminal_type() -> str:
        """Get the current terminal type."""
        import os
        
        # Check for various terminal environment variables
        terminal_env = os.environ.get('TERM_PROGRAM')
        if terminal_env:
            return terminal_env.lower()
        
        term = os.environ.get('TERM', '')
        if 'xterm' in term:
            return 'xterm'
        elif 'tmux' in term:
            return 'tmux'
        elif 'screen' in term:
            return 'screen'
        
        # Windows Terminal detection
        if os.environ.get('WT_SESSION'):
            return 'windows_terminal'
        
        return 'unknown'