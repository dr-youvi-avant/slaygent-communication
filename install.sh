#!/bin/bash
# Slaygent Communication System - Linux/macOS Installation Script
# Enhanced cross-platform installation with auto-detection and unified configuration
# Achieves: <5 minute setup, tmux integration, Redis pub/sub, voice auto-download

set -euo pipefail

# Configuration
INSTALL_PATH="${INSTALL_PATH:-$HOME/slaygent}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
SKIP_REDIS="${SKIP_REDIS:-false}"
SKIP_VOICES="${SKIP_VOICES:-false}"
DEV_MODE="${DEV_MODE:-false}"
QUIET="${QUIET:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[0;37m'
NC='\033[0m' # No Color

# Utility functions
log_info() {
    [[ "$QUIET" != "true" ]] && echo -e "${CYAN}🔄 $1${NC}"
}

log_success() {
    [[ "$QUIET" != "true" ]] && echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    [[ "$QUIET" != "true" ]] && echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}" >&2
}

log_step() {
    [[ "$QUIET" != "true" ]] && echo -e "${BLUE}📋 $1${NC}"
}

# OS Detection
detect_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macos" ;;
        Linux*)     
            if [[ -f /etc/os-release ]]; then
                . /etc/os-release
                echo "linux-$ID"
            else
                echo "linux"
            fi
            ;;
        CYGWIN*|MINGW*|MSYS*)    echo "windows" ;;
        *)          echo "unknown" ;;
    esac
}

# Package manager detection
detect_package_manager() {
    if command -v apt >/dev/null 2>&1; then
        echo "apt"
    elif command -v yum >/dev/null 2>&1; then
        echo "yum"
    elif command -v dnf >/dev/null 2>&1; then
        echo "dnf"
    elif command -v brew >/dev/null 2>&1; then
        echo "brew"
    elif command -v pacman >/dev/null 2>&1; then
        echo "pacman"
    elif command -v zypper >/dev/null 2>&1; then
        echo "zypper"
    else
        echo "none"
    fi
}

# Python installation
install_python() {
    log_step "Checking Python installation..."
    
    # Check existing Python installations
    local python_cmd=""
    for cmd in python3 python python3.12 python3.11 python3.10; do
        if command -v "$cmd" >/dev/null 2>&1; then
            local version=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
            if [[ $(echo "$version >= 3.8" | bc 2>/dev/null || echo "0") == "1" ]]; then
                python_cmd="$cmd"
                log_success "Found Python $version at $cmd"
                break
            fi
        fi
    done
    
    if [[ -z "$python_cmd" ]]; then
        log_step "Installing Python $PYTHON_VERSION..."
        
        local os=$(detect_os)
        local pkg_mgr=$(detect_package_manager)
        
        case "$pkg_mgr" in
            apt)
                sudo apt update
                sudo apt install -y python3 python3-pip python3-venv python3-dev
                python_cmd="python3"
                ;;
            yum|dnf)
                sudo $pkg_mgr install -y python3 python3-pip python3-devel
                python_cmd="python3"
                ;;
            brew)
                brew install python@3.12
                python_cmd="python3.12"
                ;;
            pacman)
                sudo pacman -S --noconfirm python python-pip
                python_cmd="python"
                ;;
            zypper)
                sudo zypper install -y python3 python3-pip python3-devel
                python_cmd="python3"
                ;;
            *)
                log_error "No supported package manager found. Please install Python 3.8+ manually."
                return 1
                ;;
        esac
    fi
    
    echo "$python_cmd"
}

# System dependencies
install_system_deps() {
    log_step "Installing system dependencies..."
    
    local os=$(detect_os)
    local pkg_mgr=$(detect_package_manager)
    
    case "$pkg_mgr" in
        apt)
            sudo apt update
            sudo apt install -y \
                build-essential \
                portaudio19-dev \
                pulseaudio \
                pulseaudio-utils \
                alsa-utils \
                tmux \
                curl \
                wget \
                git \
                bc
            ;;
        yum|dnf)
            sudo $pkg_mgr groupinstall -y "Development Tools"
            sudo $pkg_mgr install -y \
                portaudio-devel \
                pulseaudio \
                pulseaudio-utils \
                alsa-utils \
                tmux \
                curl \
                wget \
                git \
                bc
            ;;
        brew)
            brew install \
                portaudio \
                tmux \
                curl \
                wget \
                git \
                bc
            ;;
        pacman)
            sudo pacman -S --noconfirm \
                base-devel \
                portaudio \
                pulseaudio \
                pulseaudio-alsa \
                alsa-utils \
                tmux \
                curl \
                wget \
                git \
                bc
            ;;
        zypper)
            sudo zypper install -y \
                -t pattern devel_basis \
                portaudio-devel \
                pulseaudio \
                pulseaudio-utils \
                alsa-utils \
                tmux \
                curl \
                wget \
                git \
                bc
            ;;
        *)
            log_warning "Unknown package manager. Please install system dependencies manually."
            log_info "Required: build tools, portaudio, pulseaudio/alsa, tmux, curl, wget, git, bc"
            ;;
    esac
    
    log_success "System dependencies installed"
}

# Redis installation
install_redis() {
    if [[ "$SKIP_REDIS" == "true" ]]; then
        log_warning "Skipping Redis installation (will use fallback messaging)"
        return 1
    fi
    
    log_step "Installing Redis for messaging..."
    
    # Check if Redis is already running
    if redis-cli ping >/dev/null 2>&1; then
        log_success "Redis already running"
        return 0
    fi
    
    local pkg_mgr=$(detect_package_manager)
    
    case "$pkg_mgr" in
        apt)
            sudo apt update
            sudo apt install -y redis-server
            sudo systemctl enable redis-server
            sudo systemctl start redis-server
            ;;
        yum|dnf)
            sudo $pkg_mgr install -y redis
            sudo systemctl enable redis
            sudo systemctl start redis
            ;;
        brew)
            brew install redis
            brew services start redis
            ;;
        pacman)
            sudo pacman -S --noconfirm redis
            sudo systemctl enable redis
            sudo systemctl start redis
            ;;
        zypper)
            sudo zypper install -y redis
            sudo systemctl enable redis
            sudo systemctl start redis
            ;;
        *)
            log_warning "Installing Redis from source..."
            # Fallback: compile from source
            local redis_version="7.2.4"
            local redis_url="https://download.redis.io/releases/redis-${redis_version}.tar.gz"
            
            cd /tmp
            wget "$redis_url" -O redis.tar.gz
            tar xzf redis.tar.gz
            cd "redis-${redis_version}"
            make
            sudo make install
            
            # Create Redis user and directories
            sudo useradd -r -s /bin/false redis 2>/dev/null || true
            sudo mkdir -p /var/lib/redis /var/log/redis /etc/redis
            sudo chown redis:redis /var/lib/redis /var/log/redis
            
            # Simple Redis config
            sudo tee /etc/redis/redis.conf > /dev/null <<EOF
bind 127.0.0.1
port 6379
daemonize yes
pidfile /var/run/redis.pid
loglevel notice
logfile /var/log/redis/redis.log
dir /var/lib/redis
EOF
            
            # Start Redis
            sudo -u redis redis-server /etc/redis/redis.conf
            ;;
    esac
    
    # Test Redis
    if redis-cli ping >/dev/null 2>&1; then
        log_success "Redis installed and running"
        return 0
    else
        log_warning "Redis installation failed, will use fallback messaging"
        return 1
    fi
}

# Python dependencies
install_python_deps() {
    local python_cmd="$1"
    
    log_step "Installing Python dependencies..."
    
    # Upgrade pip
    "$python_cmd" -m pip install --upgrade pip
    
    # Install requirements
    if [[ -f "requirements.txt" ]]; then
        "$python_cmd" -m pip install -r requirements.txt
    else
        log_error "requirements.txt not found!"
        return 1
    fi
    
    log_success "Python dependencies installed"
}

# Voice model downloads
download_voices() {
    if [[ "$SKIP_VOICES" == "true" ]]; then
        log_warning "Skipping voice model downloads"
        return
    fi
    
    log_step "Downloading Piper voice models..."
    
    local voices_dir="$INSTALL_PATH/voices"
    mkdir -p "$voices_dir"
    
    # Voice model definitions
    declare -A voices
    voices[amy]="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx"
    voices[danny]="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/danny/low/en_US-danny-low.onnx"
    
    for voice in "${!voices[@]}"; do
        local voice_dir="$voices_dir/$voice"
        mkdir -p "$voice_dir"
        
        local model_file="$voice_dir/model.onnx"
        local config_file="$voice_dir/config.json"
        local config_url="${voices[$voice]}.json"
        
        if [[ ! -f "$model_file" ]]; then
            log_step "Downloading $voice voice model..."
            if wget -q "${voices[$voice]}" -O "$model_file" && wget -q "$config_url" -O "$config_file"; then
                log_success "Downloaded $voice voice model"
            else
                log_warning "Failed to download $voice voice model"
                rm -f "$model_file" "$config_file"
            fi
        else
            log_success "$voice voice model already exists"
        fi
    done
}

# Configuration setup
setup_configuration() {
    log_step "Creating configuration files..."
    
    # Create .env file
    cat > "$INSTALL_PATH/.env" <<EOF
# Slaygent Communication System Configuration
# Generated by install.sh on $(date)

# Service URLs
TTS_HOST=localhost
TTS_PORT=9003
DISCOVERY_HOST=localhost
DISCOVERY_PORT=9005

# Redis Configuration (optional - will use fallback if not available)
REDIS_HOST=localhost
REDIS_PORT=6379
USE_REDIS=true

# Audio Configuration
AUDIO_BACKEND=auto
DEFAULT_VOICE=amy
VOICE_SPEED=1.0
VOICE_PITCH=1.0

# Paths
VOICE_MODEL_PATH=./voices
CONFIG_PATH=./config.yaml

# Logging
LOG_LEVEL=INFO
LOG_FILE=slaygent.log

# Unix-specific
TMUX_INTEGRATION=true
USE_PULSEAUDIO=true
EOF

    log_success "Configuration files created"
}

# Shell integration
setup_shell_integration() {
    log_step "Setting up shell integration..."
    
    local shell_rc=""
    if [[ -n "${BASH_VERSION:-}" ]]; then
        shell_rc="$HOME/.bashrc"
    elif [[ -n "${ZSH_VERSION:-}" ]]; then
        shell_rc="$HOME/.zshrc"
    else
        shell_rc="$HOME/.profile"
    fi
    
    # Add Slaygent to PATH
    local path_line="export PATH=\"$INSTALL_PATH/bin:\$PATH\""
    if ! grep -q "$INSTALL_PATH/bin" "$shell_rc" 2>/dev/null; then
        echo "" >> "$shell_rc"
        echo "# Slaygent Communication System" >> "$shell_rc"
        echo "$path_line" >> "$shell_rc"
        log_success "Added Slaygent to PATH in $shell_rc"
    else
        log_success "Slaygent already in PATH"
    fi
    
    # Create aliases
    cat >> "$shell_rc" <<EOF

# Slaygent aliases
alias slay-start='cd $INSTALL_PATH && python src/servers/tts_server.py & python src/servers/agent_discovery.py &'
alias slay-stop='pkill -f "tts_server.py|agent_discovery.py"'
alias slay-say='$INSTALL_PATH/bin/say'
alias slay-msg='$INSTALL_PATH/bin/msg'
alias slay-agents='$INSTALL_PATH/bin/search-agents'
EOF

    log_success "Shell aliases created"
}

# Service management
setup_systemd_services() {
    if ! command -v systemctl >/dev/null 2>&1; then
        log_warning "systemd not available, skipping service setup"
        return
    fi
    
    log_step "Setting up systemd services..."
    
    # TTS Server service
    sudo tee /etc/systemd/system/slaygent-tts.service > /dev/null <<EOF
[Unit]
Description=Slaygent TTS Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_PATH
ExecStart=$(which python3) src/servers/tts_server.py
Restart=always
RestartSec=3
Environment=PYTHONPATH=$INSTALL_PATH

[Install]
WantedBy=multi-user.target
EOF

    # Discovery Server service
    sudo tee /etc/systemd/system/slaygent-discovery.service > /dev/null <<EOF
[Unit]
Description=Slaygent Agent Discovery Server  
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_PATH
ExecStart=$(which python3) src/servers/agent_discovery.py
Restart=always
RestartSec=3
Environment=PYTHONPATH=$INSTALL_PATH

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    
    if [[ "$DEV_MODE" != "true" ]]; then
        sudo systemctl enable slaygent-tts slaygent-discovery
        log_success "Systemd services created and enabled"
    else
        log_success "Systemd services created (not enabled in dev mode)"
    fi
}

# Installation testing
test_installation() {
    log_step "Testing installation..."
    
    local tests_passed=0
    local total_tests=6
    
    # Test 1: Python availability
    if python3 --version >/dev/null 2>&1; then
        log_success "✓ Python executable working"
        ((tests_passed++))
    else
        log_error "✗ Python test failed"
    fi
    
    # Test 2: Dependencies
    if python3 -c "import fastapi, piper, redis" 2>/dev/null; then
        log_success "✓ Python dependencies available"
        ((tests_passed++))
    else
        log_error "✗ Dependency test failed"
    fi
    
    # Test 3: Voice models
    if [[ -f "$INSTALL_PATH/voices/amy/model.onnx" ]]; then
        log_success "✓ Voice models downloaded"
        ((tests_passed++))
    else
        log_error "✗ Voice models missing"
    fi
    
    # Test 4: Configuration
    if [[ -f "$INSTALL_PATH/.env" ]]; then
        log_success "✓ Configuration files created"
        ((tests_passed++))
    else
        log_error "✗ Configuration files missing"  
    fi
    
    # Test 5: CLI tools
    if [[ -x "$INSTALL_PATH/bin/msg" ]]; then
        log_success "✓ CLI tools executable"
        ((tests_passed++))
    else
        log_error "✗ CLI tools not executable"
    fi
    
    # Test 6: Audio system
    if command -v pulseaudio >/dev/null 2>&1 || command -v alsa >/dev/null 2>&1; then
        log_success "✓ Audio system available"
        ((tests_passed++))
    else
        log_warning "⚠ Audio system not detected"
    fi
    
    echo -e "${CYAN}📊 Installation Test Results: $tests_passed/$total_tests tests passed${NC}"
    
    if [[ $tests_passed -eq $total_tests ]]; then
        log_success "🎉 Installation completed successfully!"
        return 0
    else
        log_warning "⚠️  Installation completed with issues. See errors above."
        return 1
    fi
}

# Quick start guide
show_quickstart() {
    echo -e "${CYAN}🚀 Quick Start Guide:${NC}"
    echo -e "${CYAN}1. Source your shell configuration:${NC}"
    echo -e "${PURPLE}   source ~/.bashrc${NC}"
    echo -e "${CYAN}2. Start services:${NC}"
    echo -e "${PURPLE}   slay-start${NC}"
    echo -e "${CYAN}3. Test TTS:${NC}"
    echo -e "${PURPLE}   slay-say \"Hello from Slaygent!\"${NC}"
    echo -e "${CYAN}4. Check agents:${NC}"
    echo -e "${PURPLE}   slay-agents${NC}"
    echo -e "${CYAN}5. Send a message:${NC}"
    echo -e "${PURPLE}   slay-msg <agent> \"Your message here\"${NC}"
    
    if [[ "$DEV_MODE" == "true" ]]; then
        echo -e "${CYAN}🔧 Developer Commands:${NC}"
        echo -e "${PURPLE}   cd $INSTALL_PATH${NC}"
        echo -e "${PURPLE}   python src/servers/tts_server.py${NC}"
        echo -e "${PURPLE}   python src/servers/agent_discovery.py${NC}"
    fi
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --install-path)
                INSTALL_PATH="$2"
                shift 2
                ;;
            --skip-redis)
                SKIP_REDIS=true
                shift
                ;;
            --skip-voices)
                SKIP_VOICES=true
                shift
                ;;
            --dev-mode)
                DEV_MODE=true
                shift
                ;;
            --quiet)
                QUIET=true
                shift
                ;;
            --python-version)
                PYTHON_VERSION="$2"
                shift 2
                ;;
            --help)
                cat <<EOF
Slaygent Communication System - Installation Script

Usage: $0 [OPTIONS]

Options:
    --install-path PATH     Installation directory (default: ~/slaygent)
    --skip-redis           Skip Redis installation (use fallback messaging)
    --skip-voices          Skip voice model downloads
    --dev-mode             Development mode (no service auto-start)
    --quiet                Suppress output except errors
    --python-version VER   Python version to install (default: 3.12)
    --help                 Show this help message

Examples:
    $0                                          # Standard installation
    $0 --install-path /opt/slaygent --quiet    # Custom path, quiet mode
    $0 --skip-redis --dev-mode                 # Minimal dev installation
EOF
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                log_info "Use --help to see available options"
                exit 1
                ;;
        esac
    done
}

# Main installation function
main() {
    local start_time=$(date +%s)
    
    echo -e "${GREEN}🤖 Slaygent Communication System - Linux/macOS Installer${NC}"
    echo -e "${CYAN}Installing to: $INSTALL_PATH${NC}"
    echo -e "${CYAN}OS: $(detect_os)${NC}"
    echo -e "${CYAN}Package Manager: $(detect_package_manager)${NC}"
    
    if [[ "$QUIET" != "true" ]]; then
        echo -e "${YELLOW}Press Ctrl+C to cancel, or Enter to continue...${NC}"
        read -r
    fi
    
    # Create installation directory
    mkdir -p "$INSTALL_PATH"
    
    # Copy files if not installing from current directory
    if [[ "$(pwd)" != "$INSTALL_PATH" ]]; then
        log_step "Copying Slaygent files to $INSTALL_PATH..."
        cp -r ./* "$INSTALL_PATH/"
    fi
    
    cd "$INSTALL_PATH"
    
    # Installation steps
    install_system_deps
    local python_cmd=$(install_python)
    install_python_deps "$python_cmd"
    local redis_installed=false
    install_redis && redis_installed=true
    download_voices
    setup_configuration
    setup_shell_integration
    setup_systemd_services
    
    # Test installation
    local install_success=false
    test_installation && install_success=true
    
    # Show usage guide
    show_quickstart
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if $install_success; then
        log_success "🎉 Slaygent installation completed successfully!"
        echo -e "${CYAN}⏱️  Installation time: ${duration}s${NC}"
        
        if [[ "$QUIET" != "true" ]] && [[ "$DEV_MODE" != "true" ]]; then
            echo -n -e "${YELLOW}Would you like to start Slaygent services now? (y/n): ${NC}"
            read -r response
            if [[ "$response" =~ ^[Yy] ]]; then
                log_step "Starting services..."
                python3 src/servers/tts_server.py &
                python3 src/servers/agent_discovery.py &
                sleep 2
                log_success "Services started! Check http://localhost:9003 and http://localhost:9005"
            fi
        fi
    else
        log_error "Installation completed with issues"
        exit 1
    fi
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    parse_args "$@"
    main
fi