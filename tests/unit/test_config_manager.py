"""
Unit tests for configuration manager
Tests configuration loading, validation, and cross-platform compatibility
"""

import pytest
import tempfile
import yaml
import json
import os
from pathlib import Path
from unittest.mock import patch, mock_open

from src.config.manager import ConfigManager, Config


class TestConfigManager:
    """Test ConfigManager functionality."""
    
    def test_load_config_from_yaml(self, temp_dir):
        """Test loading configuration from YAML file."""
        config_data = {
            'tts': {
                'host': 'localhost',
                'port': 9003,
                'voices': {
                    'amy': {
                        'model_path': 'voices/amy/model.onnx',
                        'config_path': 'voices/amy/config.json'
                    }
                }
            },
            'messaging': {
                'backend': 'redis',
                'redis_host': 'localhost',
                'redis_port': 6379
            }
        }
        
        config_file = temp_dir / 'config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        config = ConfigManager.load_config(str(temp_dir))
        
        assert config.tts.host == 'localhost'
        assert config.tts.port == 9003
        assert config.messaging.redis_host == 'localhost'
    
    def test_load_config_with_env_override(self, temp_dir):
        """Test configuration loading with environment variable overrides."""
        config_data = {
            'tts': {'host': 'localhost', 'port': 9003},
            'messaging': {'redis_host': 'localhost'}
        }
        
        config_file = temp_dir / 'config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Create .env file
        env_file = temp_dir / '.env'
        env_file.write_text('TTS_HOST=remote-host\nTTS_PORT=9004\n')
        
        with patch.dict(os.environ, {'TTS_HOST': 'remote-host', 'TTS_PORT': '9004'}):
            config = ConfigManager.load_config(str(temp_dir))
        
        assert config.tts.host == 'remote-host'
        assert config.tts.port == 9004
    
    def test_load_config_missing_file(self, temp_dir):
        """Test loading configuration when config file is missing."""
        # Should load default configuration
        config = ConfigManager.load_config(str(temp_dir))
        
        # Should have default values
        assert config.tts.host == 'localhost'
        assert config.tts.port == 9003
        assert config.discovery.port == 9005
    
    def test_config_validation_valid(self):
        """Test configuration validation with valid data."""
        valid_config = {
            'tts': {
                'host': 'localhost',
                'port': 9003,
                'voices': {}
            },
            'discovery': {
                'host': 'localhost',
                'port': 9005
            },
            'messaging': {
                'backend': 'redis'
            },
            'audio': {
                'backend': 'auto'
            }
        }
        
        # Should not raise exception
        ConfigManager.validate_config(valid_config)
    
    def test_config_validation_invalid_port(self):
        """Test configuration validation with invalid port."""
        invalid_config = {
            'tts': {
                'host': 'localhost',
                'port': 'invalid_port'  # Should be integer
            }
        }
        
        with pytest.raises(ValueError, match="Invalid port"):
            ConfigManager.validate_config(invalid_config)
    
    def test_config_validation_invalid_backend(self):
        """Test configuration validation with invalid backend."""
        invalid_config = {
            'messaging': {
                'backend': 'invalid_backend'
            }
        }
        
        with pytest.raises(ValueError, match="Invalid messaging backend"):
            ConfigManager.validate_config(invalid_config)
    
    def test_get_default_config(self):
        """Test default configuration generation."""
        default_config = ConfigManager.get_default_config()
        
        assert default_config['tts']['host'] == 'localhost'
        assert default_config['tts']['port'] == 9003
        assert default_config['discovery']['host'] == 'localhost'
        assert default_config['discovery']['port'] == 9005
        assert default_config['messaging']['backend'] == 'redis'
        assert default_config['audio']['backend'] == 'auto'
    
    def test_merge_configs(self):
        """Test configuration merging."""
        base_config = {
            'tts': {
                'host': 'localhost',
                'port': 9003,
                'voices': {'amy': {'model_path': 'old_path'}}
            },
            'messaging': {
                'backend': 'redis'
            }
        }
        
        override_config = {
            'tts': {
                'port': 9004,  # Override port
                'voices': {'amy': {'model_path': 'new_path'}}  # Override voice path
            },
            'audio': {  # Add new section
                'backend': 'pulse'
            }
        }
        
        merged = ConfigManager.merge_configs(base_config, override_config)
        
        assert merged['tts']['host'] == 'localhost'  # Preserved
        assert merged['tts']['port'] == 9004  # Overridden
        assert merged['tts']['voices']['amy']['model_path'] == 'new_path'  # Overridden
        assert merged['messaging']['backend'] == 'redis'  # Preserved
        assert merged['audio']['backend'] == 'pulse'  # Added


class TestConfig:
    """Test Config dataclass functionality."""
    
    def test_config_from_dict(self):
        """Test Config creation from dictionary."""
        config_data = {
            'tts': {
                'host': 'localhost',
                'port': 9003,
                'voices': {
                    'amy': {
                        'model_path': 'voices/amy/model.onnx',
                        'config_path': 'voices/amy/config.json'
                    }
                }
            },
            'discovery': {
                'host': 'localhost',
                'port': 9005,
                'scan_interval': 5
            },
            'messaging': {
                'backend': 'redis',
                'redis_host': 'localhost',
                'redis_port': 6379
            },
            'audio': {
                'backend': 'auto',
                'device_id': None
            }
        }
        
        config = Config.from_dict(config_data)
        
        assert config.tts.host == 'localhost'
        assert config.tts.port == 9003
        assert 'amy' in config.tts.voices
        assert config.discovery.scan_interval == 5
        assert config.messaging.backend == 'redis'
        assert config.audio.backend == 'auto'
    
    def test_config_to_dict(self, mock_config):
        """Test Config conversion to dictionary."""
        config = Config.from_dict(mock_config)
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert config_dict['tts']['host'] == mock_config['tts']['host']
        assert config_dict['tts']['port'] == mock_config['tts']['port']
    
    def test_config_partial_data(self):
        """Test Config creation with partial data (should use defaults)."""
        partial_data = {
            'tts': {
                'port': 9004  # Only override port
            }
        }
        
        config = Config.from_dict(partial_data)
        
        # Should have default host but overridden port
        assert config.tts.host == 'localhost'  # Default
        assert config.tts.port == 9004  # Overridden
        assert config.discovery.port == 9005  # Default


class TestEnvironmentVariables:
    """Test environment variable handling."""
    
    def test_load_env_file(self, temp_dir):
        """Test loading environment variables from .env file."""
        env_content = """
# Test environment file
TTS_HOST=test-host
TTS_PORT=9999
DISCOVERY_HOST=discovery-host

# Comments should be ignored
MESSAGING_BACKEND=redis
AUDIO_BACKEND=pulse
"""
        
        env_file = temp_dir / '.env'
        env_file.write_text(env_content)
        
        env_vars = ConfigManager.load_env_file(str(env_file))
        
        assert env_vars['TTS_HOST'] == 'test-host'
        assert env_vars['TTS_PORT'] == '9999'
        assert env_vars['DISCOVERY_HOST'] == 'discovery-host'
        assert env_vars['MESSAGING_BACKEND'] == 'redis'
        assert env_vars['AUDIO_BACKEND'] == 'pulse'
    
    def test_load_env_file_missing(self, temp_dir):
        """Test loading environment variables when .env file doesn't exist."""
        env_vars = ConfigManager.load_env_file(str(temp_dir / 'nonexistent.env'))
        assert env_vars == {}
    
    def test_apply_env_overrides(self):
        """Test applying environment variable overrides to configuration."""
        config_data = {
            'tts': {'host': 'localhost', 'port': 9003},
            'discovery': {'host': 'localhost', 'port': 9005}
        }
        
        env_overrides = {
            'TTS_HOST': 'remote-host',
            'TTS_PORT': '8888',
            'DISCOVERY_PORT': '8889'
        }
        
        updated_config = ConfigManager.apply_env_overrides(config_data, env_overrides)
        
        assert updated_config['tts']['host'] == 'remote-host'
        assert updated_config['tts']['port'] == 8888  # Should be converted to int
        assert updated_config['discovery']['host'] == 'localhost'  # Unchanged
        assert updated_config['discovery']['port'] == 8889  # Should be converted to int
    
    def test_env_var_type_conversion(self):
        """Test automatic type conversion of environment variables."""
        config_data = {
            'tts': {'port': 9003},
            'discovery': {'scan_interval': 5},
            'messaging': {'redis_port': 6379}
        }
        
        env_overrides = {
            'TTS_PORT': '8888',  # String should become int
            'DISCOVERY_SCAN_INTERVAL': '10',  # String should become int
            'MESSAGING_REDIS_PORT': '6380'  # String should become int
        }
        
        updated_config = ConfigManager.apply_env_overrides(config_data, env_overrides)
        
        assert isinstance(updated_config['tts']['port'], int)
        assert isinstance(updated_config['discovery']['scan_interval'], int)
        assert isinstance(updated_config['messaging']['redis_port'], int)


class TestConfigurationPlatformSpecific:
    """Test platform-specific configuration handling."""
    
    @pytest.mark.windows
    def test_windows_specific_config(self, test_env):
        """Test Windows-specific configuration defaults."""
        if not test_env.is_windows():
            pytest.skip("Windows-only test")
        
        with patch('src.utils.os_utils.OSUtils.get_os_type', return_value='windows'):
            config = ConfigManager.get_default_config()
            
            # Should prefer sounddevice on Windows
            assert config['audio']['backend'] == 'auto'  # Will resolve to sounddevice
    
    @pytest.mark.unix_only
    def test_linux_specific_config(self, test_env):
        """Test Linux-specific configuration defaults."""
        if test_env.is_windows():
            pytest.skip("Unix-only test")
        
        with patch('src.utils.os_utils.OSUtils.get_os_type', return_value='linux'):
            config = ConfigManager.get_default_config()
            
            # Configuration should be appropriate for Linux
            assert config['audio']['backend'] == 'auto'  # Will resolve based on system
    
    def test_voice_model_path_resolution(self, temp_dir):
        """Test voice model path resolution across platforms."""
        config_data = {
            'tts': {
                'voices': {
                    'amy': {
                        'model_path': 'voices/amy/model.onnx',
                        'config_path': 'voices/amy/config.json'
                    }
                }
            }
        }
        
        config = ConfigManager.load_config_from_dict(config_data, str(temp_dir))
        
        # Paths should be resolved relative to base directory
        assert Path(config.tts.voices['amy']['model_path']).is_absolute()


class TestConfigValidation:
    """Test comprehensive configuration validation."""
    
    def test_validate_tts_config(self):
        """Test TTS configuration validation."""
        # Valid TTS config
        valid_config = {
            'tts': {
                'host': 'localhost',
                'port': 9003,
                'voices': {}
            }
        }
        ConfigManager.validate_config(valid_config)  # Should not raise
        
        # Invalid port type
        invalid_config = {
            'tts': {'host': 'localhost', 'port': 'not_a_number'}
        }
        with pytest.raises(ValueError):
            ConfigManager.validate_config(invalid_config)
        
        # Port out of range
        invalid_config = {
            'tts': {'host': 'localhost', 'port': 70000}
        }
        with pytest.raises(ValueError):
            ConfigManager.validate_config(invalid_config)
    
    def test_validate_discovery_config(self):
        """Test discovery service configuration validation."""
        # Valid config
        valid_config = {
            'discovery': {
                'host': 'localhost',
                'port': 9005,
                'scan_interval': 5
            }
        }
        ConfigManager.validate_config(valid_config)  # Should not raise
        
        # Invalid scan interval
        invalid_config = {
            'discovery': {'scan_interval': -1}
        }
        with pytest.raises(ValueError):
            ConfigManager.validate_config(invalid_config)
    
    def test_validate_messaging_config(self):
        """Test messaging configuration validation."""
        # Valid Redis config
        valid_config = {
            'messaging': {
                'backend': 'redis',
                'redis_host': 'localhost',
                'redis_port': 6379
            }
        }
        ConfigManager.validate_config(valid_config)  # Should not raise
        
        # Valid fallback config
        valid_config = {
            'messaging': {
                'backend': 'fallback',
                'fallback_dir': '/tmp/slaygent'
            }
        }
        ConfigManager.validate_config(valid_config)  # Should not raise
        
        # Invalid backend
        invalid_config = {
            'messaging': {'backend': 'invalid_backend'}
        }
        with pytest.raises(ValueError):
            ConfigManager.validate_config(invalid_config)
    
    def test_validate_audio_config(self):
        """Test audio configuration validation."""
        # Valid configs
        valid_backends = ['auto', 'sounddevice', 'pulse', 'none']
        for backend in valid_backends:
            config = {'audio': {'backend': backend}}
            ConfigManager.validate_config(config)  # Should not raise
        
        # Invalid backend
        invalid_config = {
            'audio': {'backend': 'invalid_audio_backend'}
        }
        with pytest.raises(ValueError):
            ConfigManager.validate_config(invalid_config)


@pytest.mark.integration
class TestConfigIntegration:
    """Integration tests for configuration management."""
    
    def test_full_config_loading_workflow(self, temp_dir):
        """Test complete configuration loading workflow."""
        # Create config.yaml
        config_data = {
            'tts': {'host': 'localhost', 'port': 9003},
            'discovery': {'port': 9005}
        }
        config_file = temp_dir / 'config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Create .env file
        env_file = temp_dir / '.env'
        env_file.write_text('TTS_PORT=9999\nDISCOVERY_SCAN_INTERVAL=10\n')
        
        # Load configuration
        config = ConfigManager.load_config(str(temp_dir))
        
        # Verify YAML values
        assert config.tts.host == 'localhost'
        assert config.discovery.port == 9005
        
        # Verify environment overrides
        assert config.tts.port == 9999  # Overridden by .env
    
    def test_config_with_voice_models(self, temp_dir, create_test_voice_model):
        """Test configuration with actual voice model files."""
        # Create test voice model
        voice_dir = create_test_voice_model('amy')
        
        config_data = {
            'tts': {
                'voices': {
                    'amy': {
                        'model_path': str(voice_dir / 'model.onnx'),
                        'config_path': str(voice_dir / 'config.json')
                    }
                }
            }
        }
        
        config = ConfigManager.load_config_from_dict(config_data, str(temp_dir))
        
        # Verify voice model paths exist
        assert Path(config.tts.voices['amy']['model_path']).exists()
        assert Path(config.tts.voices['amy']['config_path']).exists()
    
    def test_config_error_handling(self, temp_dir):
        """Test configuration error handling and recovery."""
        # Create invalid YAML file
        config_file = temp_dir / 'config.yaml'
        config_file.write_text('invalid: yaml: content: [')
        
        # Should fall back to defaults without crashing
        config = ConfigManager.load_config(str(temp_dir))
        
        # Should have default values
        assert config.tts.host == 'localhost'
        assert config.tts.port == 9003