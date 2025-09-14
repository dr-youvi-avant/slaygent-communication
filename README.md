# Slaygent Communication System

A cross-platform AI agent communication, TTS feedback, and discovery system supporting Windows 11, Linux, and macOS. Transform your development workflow with seamless inter-agent messaging, neural text-to-speech, and intelligent process discovery.

## ✨ Features

### 🔄 **Universal Messaging**
- **Redis pub/sub** messaging replacing tmux dependency
- **Cross-platform** agent-to-agent communication
- **Fallback messaging** via file-based pipes (air-gapped environments)
- **Real-time** message history and persistence

### 🔊 **Neural Text-to-Speech** 
- **Piper TTS** with high-quality neural voices (Amy, Danny, etc.)
- **OS-native audio** backends (Windows DirectSound, Linux PulseAudio, macOS CoreAudio)
- **<200ms latency** for real-time feedback
- **Voice management** with auto-download and caching

### 🔍 **Intelligent Discovery**
- **Multi-platform** process and session scanning
- **REST API** for agent enumeration and status
- **Real-time monitoring** with health checks
- **Windows Terminal**, **tmux**, and **process-based** agent detection

### 🖥️ **Native Platform Integration**
- **Windows Terminal** profiles and PowerShell module integration
- **PowerShell cmdlets** and aliases for native Windows experience  
- **Shell integration** with PATH and aliases for Linux/macOS
- **VS Code tasks** and debugging configurations

## 🚀 Quick Install

### Windows 11 (PowerShell)
```powershell
# Run in PowerShell as Administrator (recommended)
.\install.ps1

# Or with custom options
.\install.ps1 -InstallPath "C:\Tools\Slaygent" -SkipRedis -DevMode
```

### Linux/macOS (Bash)
```bash
# Standard installation
chmod +x install.sh
./install.sh

# Or with custom options  
./install.sh --install-path ~/slaygent --skip-redis --dev-mode
```

### Installation completes in **<5 minutes** with one command!

## 📋 System Requirements

| Platform | Requirements |
|----------|-------------|
| **Windows 11** | PowerShell 5.1+, Windows Terminal (recommended) |
| **Linux** | Python 3.8+, PulseAudio/ALSA, build tools |
| **macOS** | Python 3.8+, Xcode Command Line Tools |
| **All** | 2GB RAM, 2GB storage, internet connection |

## 🎯 Quick Start

### Windows (PowerShell Module)
```powershell
# Import Slaygent module
Import-Module Slaygent

# Start services
Start-SlayServices

# Test TTS
Invoke-SlayTTS "Hello from Slaygent!"

# List agents
Get-SlayAgents

# Send message
Send-SlayMessage -Agent "test" -Message "Build complete"
```

### Linux/macOS (Shell Integration)
```bash
# Start services (aliases auto-created by installer)
slay-start

# Test TTS
slay-say "Hello from Slaygent!"

# List agents  
slay-agents

# Send message
slay-msg test "Build complete"
```

### CLI Tools (Cross-platform)
```bash
# Direct CLI usage
./bin/say "System online" amy
./bin/msg claude "Please review the code"
./bin/search-agents --verbose
```

## 🏗️ Architecture

### **Foundation Layer**: Cross-platform OS abstraction and configuration management
- `src/utils/os_utils.py` - OS detection and platform-specific utilities
- `src/config/manager.py` - Unified configuration with .env and YAML support

### **Messaging Layer**: Redis pub/sub with fallback systems  
- `src/messaging/redis_backend.py` - Primary Redis-based messaging
- `src/messaging/fallback_backend.py` - File-based messaging for air-gapped setups
- `src/messaging/manager.py` - Unified messaging orchestration

### **Audio Layer**: Multi-backend audio system
- `src/audio/sounddevice_backend.py` - Cross-platform audio (primary)
- `src/audio/pulse_backend.py` - Native Linux PulseAudio support
- `src/audio/manager.py` - Automatic backend selection

### **Service Layer**: FastAPI-based microservices
- `src/servers/tts_server.py` - Neural TTS with voice management (port 9003)
- `src/servers/agent_discovery.py` - Process discovery and monitoring (port 9005)

### **Interface Layer**: Native platform integration
- PowerShell module with cmdlets and Windows Terminal profiles
- Shell scripts with PATH integration and aliases
- Cross-platform Python CLI tools in `bin/`

## 🔧 Development

### Setup Development Environment
```bash
# Windows
.\scripts\setup-dev.ps1 -CreateVenv

# Linux/macOS  
./scripts/setup-dev.sh --create-venv
```

### Development Commands
```bash
# Start development servers
./dev-start.sh         # Linux/macOS
.\dev-start.ps1        # Windows

# Run tests
./dev-test.sh          # Linux/macOS
.\dev-test.ps1         # Windows

# Format code
./dev-format.sh        # Linux/macOS  
.\dev-format.ps1       # Windows

# Or use Makefile (Linux/macOS)
make dev-start         # Start servers
make test              # Run tests
make format            # Format code
```

### VS Code Integration
1. Open project in VS Code
2. Use `Ctrl+Shift+P` > "Tasks: Run Task" for development tasks
3. Use `F5` to debug servers with breakpoints
4. Pre-commit hooks ensure code quality

## 🧪 Testing & Validation

### Validate Installation
```bash
# Test complete installation
python scripts/validate-install.py

# JSON output for automation
python scripts/validate-install.py --json
```

### Manual Testing
```bash
# Test services
curl http://localhost:9003/health  # TTS server
curl http://localhost:9005/health  # Discovery server

# Test TTS
curl "http://localhost:9003/speak?text=hello&voice=amy"

# Test discovery
curl http://localhost:9005/agents
```

## 📖 Documentation

- [**Installation Guide**](docs/INSTALLATION.md) - Detailed installation instructions
- [**Development Guide**](docs/DEVELOPMENT.md) - Development setup and workflows  
- [**API Reference**](http://localhost:9003/docs) - FastAPI auto-generated docs (when running)
- [**Architecture Overview**](OVERARCHING-OBJECTIVES.md) - Complete project requirements and design

## 🐛 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| **Python not found** | Install Python 3.8+ from python.org |
| **Permission errors** | Run installer as Administrator (Windows) or with sudo (Linux) |
| **Port conflicts** | Check if ports 9003/9005 are available |
| **Audio not working** | Verify audio system and permissions |
| **Redis connection failed** | Use `--skip-redis` flag for fallback messaging |

### Platform-Specific

**Windows:**
- Set PowerShell execution policy: `Set-ExecutionPolicy RemoteSigned`
- Add installation directory to Windows Defender exclusions
- Grant audio permissions to terminal applications

**Linux:**
- Install audio utilities: `sudo apt install pulseaudio-utils alsa-utils`
- Add user to audio group: `sudo usermod -a -G audio $USER`
- Check systemd services: `journalctl -u slaygent-*`

**macOS:**
- Install Homebrew if needed: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
- Grant terminal microphone access in System Preferences > Security & Privacy
- Allow unsigned apps if needed

## 🎛️ Configuration

### Environment Variables (.env)
```bash
# Service Configuration
TTS_HOST=localhost
TTS_PORT=9003
DISCOVERY_HOST=localhost
DISCOVERY_PORT=9005

# Redis Configuration (optional)
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

### Voice Models
```bash
# Available voices (auto-downloaded)
amy    - English, medium quality, balanced
danny  - English, low quality, fast

# Add custom voices to voices/ directory
# Update config.yaml to include new voices
```

## 🚀 Performance

### Benchmarks
- **Messaging latency**: <50ms (Redis pub/sub)
- **TTS playback**: <200ms (neural synthesis + audio)
- **Agent discovery**: <100ms (cached results)
- **Memory usage**: <500MB (typical workload)
- **Startup time**: <10s (all services)

### Optimization
```bash
# Memory optimization
MAX_WORKERS=2
VOICE_CACHE_SIZE=3

# Latency optimization  
AUDIO_LOW_LATENCY=true
TTS_BUFFER_SIZE=1024

# Network optimization (distributed setups)
TTS_HOST=0.0.0.0
DISCOVERY_HOST=0.0.0.0
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Setup development environment: `./scripts/setup-dev.sh`
4. Write tests for new features
5. Ensure all tests pass: `make test`
6. Format code: `make format`
7. Submit pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Piper TTS** - High-quality neural text-to-speech synthesis
- **FastAPI** - Modern, fast web framework for APIs
- **Redis** - In-memory data structure store for messaging
- **Windows Terminal** - Modern terminal application for Windows
- **The AI/ML community** - For feedback and contributions

---

**Ready to supercharge your AI agent workflows?** Install Slaygent and experience seamless cross-platform agent communication! 🚀