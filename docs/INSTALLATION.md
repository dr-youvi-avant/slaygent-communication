# Slaygent Communication System - Installation Guide

This guide covers installation of the Slaygent Communication System across Windows, Linux, and macOS platforms.

## Quick Install (Recommended)

### Windows 11 (PowerShell)
```powershell
# Run in PowerShell (as Administrator recommended)
.\install.ps1
```

### Linux/macOS (Bash)
```bash
# Run in terminal
chmod +x install.sh
./install.sh
```

## System Requirements

### All Platforms
- **Python**: 3.8+ (3.12 recommended)
- **Memory**: 1GB RAM minimum, 2GB recommended
- **Storage**: 2GB free space (includes voice models)
- **Network**: Internet connection for downloads

### Windows-Specific
- **OS**: Windows 11 (Windows 10 1903+ supported)
- **Windows Terminal**: Recommended for optimal experience
- **PowerShell**: 5.1+ (PowerShell 7+ recommended)

### Linux-Specific  
- **Audio**: PulseAudio or ALSA
- **Build Tools**: GCC, make, pkg-config
- **Package Manager**: apt, yum, dnf, pacman, or zypper

### macOS-Specific
- **OS**: macOS Ventura+ (12.0+)
- **Xcode**: Command Line Tools
- **Homebrew**: Recommended package manager

## Installation Options

### Standard Installation

**Windows:**
```powershell
# Full installation with all features
.\install.ps1
```

**Linux/macOS:**
```bash
# Full installation with all features
./install.sh
```

### Custom Installation

**Windows:**
```powershell
# Custom installation path
.\install.ps1 -InstallPath "C:\Tools\Slaygent"

# Skip Redis (use fallback messaging)
.\install.ps1 -SkipRedis

# Skip voice model downloads
.\install.ps1 -SkipVoices

# Development mode (no auto-start)
.\install.ps1 -DevMode

# Quiet installation (no prompts)
.\install.ps1 -Quiet

# Use Memurai instead of Redis
.\install.ps1 -UseMemurai
```

**Linux/macOS:**
```bash
# Custom installation path
./install.sh --install-path /opt/slaygent

# Skip Redis (use fallback messaging)  
./install.sh --skip-redis

# Skip voice model downloads
./install.sh --skip-voices

# Development mode (no auto-start)
./install.sh --dev-mode

# Quiet installation (no prompts)
./install.sh --quiet

# Specific Python version
./install.sh --python-version 3.11
```

## What Gets Installed

### Core Components
1. **Python Dependencies**: FastAPI, Piper TTS, Redis client, audio libraries
2. **Voice Models**: Amy (default), Danny (optional) - ~200MB total
3. **Configuration**: .env file, config.yaml with OS-specific defaults
4. **CLI Tools**: Cross-platform msg, say, search-agents scripts

### Windows-Specific
- **PowerShell Module**: `Slaygent` module with cmdlets and aliases
- **Windows Terminal Profile**: "Slaygent Hub" for easy access
- **Redis**: Redis for Windows or Memurai (optional)

### Linux/macOS-Specific  
- **Shell Integration**: PATH updates and aliases in .bashrc/.zshrc
- **Systemd Services**: Optional service definitions for auto-start
- **Audio Dependencies**: PulseAudio/ALSA setup and configuration

## Post-Installation

### Windows
1. Open Windows Terminal
2. Import the Slaygent module:
   ```powershell
   Import-Module Slaygent
   ```
3. Start services:
   ```powershell
   Start-SlayServices
   ```
4. Test TTS:
   ```powershell
   Invoke-SlayTTS "Hello from Slaygent!"
   ```

### Linux/macOS
1. Source your shell configuration:
   ```bash
   source ~/.bashrc  # or ~/.zshrc for zsh
   ```
2. Start services:
   ```bash
   slay-start
   ```
3. Test TTS:
   ```bash
   slay-say "Hello from Slaygent!"
   ```

## Verification

After installation, verify everything works:

### Check Services
```bash
# Check TTS server
curl http://localhost:9003/health

# Check Discovery server  
curl http://localhost:9005/health
```

### Test CLI Tools
```bash
# List available agents
slay-agents

# Send a test message
slay-msg test "Hello World"

# Test text-to-speech
slay-say "System operational" amy
```

### PowerShell (Windows)
```powershell
# Check service health
Test-SlayHealth

# List agents
Get-SlayAgents

# Send message
Send-SlayMessage -Agent "test" -Message "Hello World"

# Test TTS
Invoke-SlayTTS "System operational"
```

## Troubleshooting

### Common Issues

#### Installation Fails
1. **Python not found**: Install Python 3.8+ from python.org
2. **Permission errors**: Run installer as administrator (Windows) or with sudo (Linux)
3. **Network issues**: Check firewall and proxy settings

#### Services Won't Start
1. **Port conflicts**: Check if ports 9003/9005 are available
2. **Python dependencies**: Reinstall with `pip install -r requirements.txt`
3. **Audio issues**: Verify audio system is working

#### Redis Connection Issues
1. **Redis not running**: Start Redis service or use `--skip-redis`
2. **Connection refused**: Check Redis is bound to localhost:6379
3. **Authentication**: Configure Redis password in .env file

### Platform-Specific Issues

#### Windows
- **PowerShell execution policy**: Run `Set-ExecutionPolicy RemoteSigned`
- **Windows Defender**: Add installation directory to exclusions
- **Audio permissions**: Grant microphone/speaker access to terminal

#### Linux  
- **Audio not working**: Install `pulseaudio-utils` or `alsa-utils`
- **Permission denied**: Add user to `audio` group: `sudo usermod -a -G audio $USER`
- **Service failures**: Check systemd logs: `journalctl -u slaygent-tts`

#### macOS
- **Homebrew issues**: Install/update Homebrew first
- **Gatekeeper warnings**: Allow apps in Security & Privacy settings
- **Audio permissions**: Grant terminal access to microphone in System Preferences

## Uninstallation

### Windows
```powershell
# Stop services
Stop-SlayServices

# Remove PowerShell module
Remove-Module Slaygent
Remove-Item "$env:USERPROFILE\Documents\PowerShell\Modules\Slaygent" -Recurse -Force

# Remove installation directory
Remove-Item "C:\Path\To\Slaygent" -Recurse -Force
```

### Linux/macOS
```bash
# Stop services
slay-stop

# Remove systemd services (if created)
sudo systemctl disable slaygent-tts slaygent-discovery
sudo rm /etc/systemd/system/slaygent-*.service

# Remove installation
rm -rf ~/slaygent

# Clean shell configuration (remove Slaygent lines from .bashrc/.zshrc)
```

## Advanced Configuration

### Environment Variables
Create or modify `.env` file in installation directory:

```bash
# Service Configuration
TTS_HOST=localhost
TTS_PORT=9003
DISCOVERY_HOST=localhost
DISCOVERY_PORT=9005

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
USE_REDIS=true

# Audio Configuration  
AUDIO_BACKEND=auto
DEFAULT_VOICE=amy
VOICE_SPEED=1.0
VOICE_PITCH=1.0

# Logging
LOG_LEVEL=INFO
LOG_FILE=slaygent.log
```

### Voice Model Management
```bash
# Download additional voices
cd voices/
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx.json

# Update config.yaml to include new voices
```

### Custom CLI Integration
Add custom scripts to `bin/` directory and make executable. They'll automatically use the Slaygent environment.

## Support

For issues and questions:
- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Check README.md and docs/ directory  
- **Community**: Join discussions in GitHub Discussions

## Performance Tuning

### Memory Optimization
- Set `MAX_WORKERS=2` in .env for lower memory usage
- Use `VOICE_CACHE_SIZE=3` to limit voice model caching

### Latency Optimization  
- Use local Redis instead of remote instance
- Configure `TTS_BUFFER_SIZE=1024` for faster audio
- Enable `AUDIO_LOW_LATENCY=true` for real-time applications

### Network Configuration
```bash
# For distributed setups, bind to specific interfaces
TTS_HOST=0.0.0.0  # Bind to all interfaces
DISCOVERY_HOST=0.0.0.0

# Configure firewall
sudo ufw allow 9003  # TTS server
sudo ufw allow 9005  # Discovery server
sudo ufw allow 6379  # Redis (if needed)
```