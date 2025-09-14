#!/usr/bin/env python3
"""
Cross-platform configuration management system for Slaygent Communication System
Supports .env files, YAML config files, and environment-based overrides.
"""

import os
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field
from dotenv import load_dotenv

from ..utils.os_utils import get_os_detector, get_config_directory

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """Server configuration settings"""
    host: str = "127.0.0.1"
    port: int = 9003
    workers: int = 1
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ServerConfig':
        return cls(
            host=data.get("host", "127.0.0.1"),
            port=data.get("port", 9003),
            workers=data.get("workers", 1)
        )


@dataclass 
class RedisConfig:
    """Redis configuration for messaging"""
    host: str = "127.0.0.1"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0
    enabled: bool = True
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RedisConfig':
        return cls(
            host=data.get("host", "127.0.0.1"),
            port=data.get("port", 6379),
            password=data.get("password"),
            db=data.get("db", 0),
            enabled=data.get("enabled", True)
        )


@dataclass
class AudioConfig:
    """Audio backend configuration"""
    backend: str = "auto"  # auto, sounddevice, pulse, alsa, none
    device_id: Optional[int] = None
    sample_rate: int = 22050
    channels: int = 1
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AudioConfig':
        return cls(
            backend=data.get("backend", "auto"),
            device_id=data.get("device_id"),
            sample_rate=data.get("sample_rate", 22050),
            channels=data.get("channels", 1)
        )


@dataclass
class VoiceConfig:
    """Voice model configuration"""
    default_voice: str = "amy"
    voice_dir: str = "voices"
    auto_download: bool = True
    models: Dict[str, str] = field(default_factory=lambda: {
        "amy": "en_US-amy-medium.onnx",
        "danny": "en_US-danny-low.onnx",
        "kathleen": "en_US-kathleen-low.onnx",
        "libritts": "en_US-libritts-high.onnx",
        "lessac": "en_US-lessac-medium.onnx",
        "ryan": "en_US-ryan-medium.onnx"
    })
    
    @classmethod
    def from_dict(cls, data: dict) -> 'VoiceConfig':
        return cls(
            default_voice=data.get("default_voice", "amy"),
            voice_dir=data.get("voice_dir", "voices"),
            auto_download=data.get("auto_download", True),
            models=data.get("models", cls().models)
        )


@dataclass
class AgentConfig:
    """Agent discovery configuration"""
    discovery_port: int = 9005
    refresh_interval: int = 5
    timeout: int = 30
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AgentConfig':
        return cls(
            discovery_port=data.get("discovery_port", 9005),
            refresh_interval=data.get("refresh_interval", 5),
            timeout=data.get("timeout", 30)
        )


@dataclass
class SlaygentConfig:
    """Main configuration class"""
    environment: str = "development"
    debug: bool = False
    
    # Server configurations
    tts_server: ServerConfig = field(default_factory=ServerConfig)
    discovery_server: ServerConfig = field(default_factory=lambda: ServerConfig(port=9005))
    
    # Service configurations  
    redis: RedisConfig = field(default_factory=RedisConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SlaygentConfig':
        """Create config from dictionary"""
        config = cls(
            environment=data.get("environment", "development"),
            debug=data.get("debug", False)
        )
        
        if "tts_server" in data:
            config.tts_server = ServerConfig.from_dict(data["tts_server"])
            
        if "discovery_server" in data:
            config.discovery_server = ServerConfig.from_dict(data["discovery_server"])
            
        if "redis" in data:
            config.redis = RedisConfig.from_dict(data["redis"])
            
        if "audio" in data:
            config.audio = AudioConfig.from_dict(data["audio"])
            
        if "voice" in data:
            config.voice = VoiceConfig.from_dict(data["voice"])
            
        if "agent" in data:
            config.agent = AgentConfig.from_dict(data["agent"])
            
        return config


class ConfigManager:
    """Cross-platform configuration manager"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.os_detector = get_os_detector()
        self.config_dir = Path(get_config_directory())
        self.config_file = config_file or self._find_config_file()
        self._config: Optional[SlaygentConfig] = None
        
    def _find_config_file(self) -> Optional[str]:
        """Find configuration file in standard locations"""
        # Search order: current dir, config dir, project root
        search_paths = [
            Path.cwd() / "config.yaml",
            Path.cwd() / "config.yml", 
            Path.cwd() / "config.json",
            self.config_dir / "config.yaml",
            self.config_dir / "config.yml",
            self.config_dir / "config.json",
        ]
        
        for path in search_paths:
            if path.exists():
                logger.info(f"Found config file: {path}")
                return str(path)
        
        logger.info("No config file found, using defaults")
        return None
    
    def _load_env_file(self):
        """Load environment variables from .env files"""
        env_paths = [
            Path.cwd() / ".env",
            Path.cwd() / ".env.local",
            self.config_dir / ".env"
        ]
        
        for env_path in env_paths:
            if env_path.exists():
                logger.info(f"Loading environment from: {env_path}")
                load_dotenv(env_path)
    
    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides"""
        # TTS Server settings
        if "SLAYGENT_TTS_HOST" in os.environ:
            config_data.setdefault("tts_server", {})["host"] = os.environ["SLAYGENT_TTS_HOST"]
        if "SLAYGENT_TTS_PORT" in os.environ:
            config_data.setdefault("tts_server", {})["port"] = int(os.environ["SLAYGENT_TTS_PORT"])
        
        # Discovery Server settings
        if "SLAYGENT_DISCOVERY_HOST" in os.environ:
            config_data.setdefault("discovery_server", {})["host"] = os.environ["SLAYGENT_DISCOVERY_HOST"]
        if "SLAYGENT_DISCOVERY_PORT" in os.environ:
            config_data.setdefault("discovery_server", {})["port"] = int(os.environ["SLAYGENT_DISCOVERY_PORT"])
        
        # Redis settings (using Clacky Redis if available)
        if "REDIS_INNER_HOST" in os.environ:
            config_data.setdefault("redis", {})["host"] = os.environ["REDIS_INNER_HOST"]
        if "REDIS_INNER_PORT" in os.environ:
            config_data.setdefault("redis", {})["port"] = int(os.environ["REDIS_INNER_PORT"])
        if "REDISCLI_AUTH" in os.environ:
            config_data.setdefault("redis", {})["password"] = os.environ["REDISCLI_AUTH"]
        
        # Manual Redis fallback
        if "SLAYGENT_REDIS_HOST" in os.environ:
            config_data.setdefault("redis", {})["host"] = os.environ["SLAYGENT_REDIS_HOST"]
        if "SLAYGENT_REDIS_PORT" in os.environ:
            config_data.setdefault("redis", {})["port"] = int(os.environ["SLAYGENT_REDIS_PORT"])
        if "SLAYGENT_REDIS_PASSWORD" in os.environ:
            config_data.setdefault("redis", {})["password"] = os.environ["SLAYGENT_REDIS_PASSWORD"]
        
        # Audio settings
        if "SLAYGENT_AUDIO_BACKEND" in os.environ:
            config_data.setdefault("audio", {})["backend"] = os.environ["SLAYGENT_AUDIO_BACKEND"]
        
        # Voice settings
        if "SLAYGENT_DEFAULT_VOICE" in os.environ:
            config_data.setdefault("voice", {})["default_voice"] = os.environ["SLAYGENT_DEFAULT_VOICE"]
        if "SLAYGENT_VOICE_DIR" in os.environ:
            config_data.setdefault("voice", {})["voice_dir"] = os.environ["SLAYGENT_VOICE_DIR"]
        
        # Debug mode
        if "SLAYGENT_DEBUG" in os.environ:
            config_data["debug"] = os.environ["SLAYGENT_DEBUG"].lower() in ("true", "1", "yes")
        
        return config_data
    
    def _apply_os_defaults(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply OS-specific defaults"""
        # Set audio backend based on OS if auto
        audio_config = config_data.setdefault("audio", {})
        if audio_config.get("backend") == "auto":
            audio_config["backend"] = self.os_detector.audio_backend
        
        return config_data
    
    def load_config(self) -> SlaygentConfig:
        """Load and validate configuration"""
        if self._config is not None:
            return self._config
        
        # Load .env files first
        self._load_env_file()
        
        # Start with empty config
        config_data = {}
        
        # Load from file if it exists
        if self.config_file and Path(self.config_file).exists():
            try:
                with open(self.config_file, 'r') as f:
                    if self.config_file.endswith(('.yaml', '.yml')):
                        config_data = yaml.safe_load(f) or {}
                    else:
                        config_data = json.load(f)
                logger.info(f"Loaded configuration from {self.config_file}")
            except Exception as e:
                logger.error(f"Failed to load config file {self.config_file}: {e}")
                config_data = {}
        
        # Apply environment overrides
        config_data = self._apply_env_overrides(config_data)
        
        # Apply OS-specific defaults
        config_data = self._apply_os_defaults(config_data)
        
        # Create and cache config object
        self._config = SlaygentConfig.from_dict(config_data)
        
        logger.info(f"Configuration loaded for {self.os_detector.os_type.value} environment")
        return self._config
    
    def save_config(self, config: SlaygentConfig, file_path: Optional[str] = None):
        """Save configuration to file"""
        save_path = file_path or self.config_file or (self.config_dir / "config.yaml")
        save_path = Path(save_path)
        
        # Ensure directory exists
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dictionary (simplified for serialization)
        config_dict = {
            "environment": config.environment,
            "debug": config.debug,
            "tts_server": {
                "host": config.tts_server.host,
                "port": config.tts_server.port,
                "workers": config.tts_server.workers
            },
            "discovery_server": {
                "host": config.discovery_server.host,
                "port": config.discovery_server.port,
                "workers": config.discovery_server.workers
            },
            "redis": {
                "host": config.redis.host,
                "port": config.redis.port,
                "password": config.redis.password,
                "db": config.redis.db,
                "enabled": config.redis.enabled
            },
            "audio": {
                "backend": config.audio.backend,
                "device_id": config.audio.device_id,
                "sample_rate": config.audio.sample_rate,
                "channels": config.audio.channels
            },
            "voice": {
                "default_voice": config.voice.default_voice,
                "voice_dir": config.voice.voice_dir,
                "auto_download": config.voice.auto_download,
                "models": config.voice.models
            },
            "agent": {
                "discovery_port": config.agent.discovery_port,
                "refresh_interval": config.agent.refresh_interval,
                "timeout": config.agent.timeout
            }
        }
        
        try:
            if save_path.suffix in ('.yaml', '.yml'):
                with open(save_path, 'w') as f:
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            else:
                with open(save_path, 'w') as f:
                    json.dump(config_dict, f, indent=2)
            
            logger.info(f"Configuration saved to {save_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise
    
    def get_config(self) -> SlaygentConfig:
        """Get current configuration"""
        return self.load_config()
    
    def validate_config(self, config: SlaygentConfig) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        # Check port ranges
        if not (1024 <= config.tts_server.port <= 65535):
            errors.append(f"TTS server port {config.tts_server.port} out of range")
        
        if not (1024 <= config.discovery_server.port <= 65535):
            errors.append(f"Discovery server port {config.discovery_server.port} out of range")
        
        # Check Redis connection if enabled
        if config.redis.enabled:
            if not (1 <= config.redis.port <= 65535):
                errors.append(f"Redis port {config.redis.port} out of range")
        
        # Validate audio backend
        valid_backends = ["auto", "sounddevice", "pulse", "alsa", "none"]
        if config.audio.backend not in valid_backends:
            errors.append(f"Invalid audio backend: {config.audio.backend}")
        
        # Check voice directory exists
        voice_path = Path(config.voice.voice_dir)
        if not voice_path.exists() and not config.voice.auto_download:
            errors.append(f"Voice directory does not exist: {voice_path}")
        
        return errors


# Global config manager instance
_config_manager = None


def get_config_manager() -> ConfigManager:
    """Get singleton config manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> SlaygentConfig:
    """Get current configuration"""
    return get_config_manager().get_config()