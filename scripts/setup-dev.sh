#!/bin/bash
# Slaygent Communication System - Development Setup Script
# Bash script for setting up development environment on Linux/macOS

set -euo pipefail

# Configuration
INSTALL_PATH="${INSTALL_PATH:-$(pwd)}"
SKIP_REDIS="${SKIP_REDIS:-false}"
SKIP_VOICES="${SKIP_VOICES:-false}"
CREATE_VENV="${CREATE_VENV:-false}"
VENV_NAME="${VENV_NAME:-slaygent-dev}"
QUIET="${QUIET:-false}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

log_dev_step() {
    [[ "$QUIET" != "true" ]] && echo -e "${CYAN}🔧 $1${NC}"
}

log_dev_success() {
    [[ "$QUIET" != "true" ]] && echo -e "${GREEN}✅ $1${NC}"
}

log_dev_warning() {
    [[ "$QUIET" != "true" ]] && echo -e "${YELLOW}⚠️  $1${NC}"
}

log_dev_info() {
    [[ "$QUIET" != "true" ]] && echo -e "${BLUE}📋 $1${NC}"
}

echo -e "${GREEN}🚀 Slaygent Development Environment Setup${NC}"
echo -e "${CYAN}Setting up development environment in: $INSTALL_PATH${NC}"

cd "$INSTALL_PATH"

# Create virtual environment if requested
if [[ "$CREATE_VENV" == "true" ]]; then
    log_dev_step "Creating Python virtual environment: $VENV_NAME"
    python3 -m venv "$VENV_NAME"
    source "$VENV_NAME/bin/activate"
    log_dev_success "Virtual environment created and activated"
fi

# Install development dependencies
log_dev_step "Installing development dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# Install development tools
DEV_TOOLS=(
    "pytest"
    "pytest-cov"
    "pytest-asyncio"
    "black"
    "flake8"
    "mypy"
    "pre-commit"
    "isort"
)

for tool in "${DEV_TOOLS[@]}"; do
    log_dev_step "Installing $tool..."
    python3 -m pip install "$tool"
done

# Setup pre-commit hooks
log_dev_step "Setting up pre-commit hooks..."
pre-commit install

# Create development configuration
log_dev_step "Creating development configuration..."
cat > "$INSTALL_PATH/.env.dev" <<EOF
# Development Environment Configuration
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Service URLs (development)
TTS_HOST=localhost
TTS_PORT=9003
DISCOVERY_HOST=localhost
DISCOVERY_PORT=9005

# Redis (optional for development)
USE_REDIS=false
REDIS_HOST=localhost
REDIS_PORT=6379

# Audio Configuration
AUDIO_BACKEND=auto
DEFAULT_VOICE=amy
VOICE_SPEED=1.0

# Development-specific
RELOAD_ON_CHANGE=true
ENABLE_CORS=true
API_DOCS_ENABLED=true
EOF

# Create pytest configuration
cat > "$INSTALL_PATH/pytest.ini" <<EOF
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = --cov=src --cov-report=html --cov-report=term-missing
asyncio_mode = auto
EOF

# Create pyproject.toml for tool configuration
cat > "$INSTALL_PATH/pyproject.toml" <<EOF
[tool.black]
line-length = 88
target-version = ['py38']
include = '\.pyi?\$'
exclude = '''
/(
    \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | _build
  | buck-out
  | build
  | dist
)/
'''

[tool.isort]
profile = "black"
multi_line_output = 3
line_length = 88
known_first_party = ["slaygent"]

[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
exclude = ["tests/", "build/", "dist/"]

[tool.flake8]
max-line-length = 88
extend-ignore = ["E203", "W503"]
exclude = [".git", "__pycache__", "build", "dist", ".venv"]
EOF

# Create development scripts
log_dev_step "Creating development scripts..."

# Development start script
cat > "$INSTALL_PATH/dev-start.sh" <<'EOF'
#!/bin/bash
# Start Slaygent in development mode

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load development environment
if [[ -f .env.dev ]]; then
    export $(grep -v '^#' .env.dev | xargs)
fi

echo "🚀 Starting Slaygent in development mode..."

# Start servers in background
python3 src/servers/tts_server.py &
TTS_PID=$!
sleep 2

python3 src/servers/agent_discovery.py &
DISCOVERY_PID=$!
sleep 2

echo "✅ Development servers started!"
echo "TTS Server: http://localhost:9003 (PID: $TTS_PID)"
echo "Discovery Server: http://localhost:9005 (PID: $DISCOVERY_PID)"
echo ""
echo "To stop servers:"
echo "  kill $TTS_PID $DISCOVERY_PID"
echo "  or run: pkill -f 'tts_server.py|agent_discovery.py'"

# Keep script running to monitor processes
trap "kill $TTS_PID $DISCOVERY_PID 2>/dev/null; echo 'Servers stopped'; exit" INT TERM

wait
EOF

# Development test script
cat > "$INSTALL_PATH/dev-test.sh" <<'EOF'
#!/bin/bash
# Run tests in development mode

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🧪 Running tests..."
pytest -v

echo "📊 Running type checks..."
mypy src/

echo "🎨 Running code formatting check..."
black --check src/

echo "📏 Running linting..."
flake8 src/

echo "🔍 Running import sorting check..."
isort --check-only src/

echo "✅ All checks completed!"
EOF

# Development format script
cat > "$INSTALL_PATH/dev-format.sh" <<'EOF'
#!/bin/bash
# Format code in development mode

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🎨 Formatting code with Black..."
black src/

echo "🔍 Sorting imports with isort..."
isort src/

echo "✅ Code formatting complete!"
EOF

# Make scripts executable
chmod +x dev-start.sh dev-test.sh dev-format.sh

log_dev_success "Created development scripts"

# Create test directory structure
TEST_DIRS=(
    "tests"
    "tests/unit"
    "tests/integration"
    "tests/fixtures"
)

for dir in "${TEST_DIRS[@]}"; do
    if [[ ! -d "$dir" ]]; then
        mkdir -p "$dir"
        log_dev_success "Created test directory: $dir"
    fi
done

# Create test package initialization
cat > "$INSTALL_PATH/tests/__init__.py" <<EOF
# Test package initialization
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
EOF

# Create sample test file
cat > "$INSTALL_PATH/tests/test_sample.py" <<EOF
# Sample test file
import pytest
from unittest.mock import Mock, patch


class TestSample:
    def test_sample_function(self):
        """Sample test to verify testing framework works"""
        assert 1 + 1 == 2
        
    @pytest.mark.asyncio
    async def test_async_sample(self):
        """Sample async test"""
        result = await self.async_sample_function()
        assert result == "success"
        
    async def async_sample_function(self):
        return "success"
EOF

# Create VS Code configuration
VSCODE_DIR="$INSTALL_PATH/.vscode"
mkdir -p "$VSCODE_DIR"

# VS Code settings
cat > "$VSCODE_DIR/settings.json" <<EOF
{
    "python.defaultInterpreterPath": $(if [[ "$CREATE_VENV" == "true" ]]; then echo "\"./$VENV_NAME/bin/python\""; else echo "\"python3\""; fi),
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false,
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "python.sortImports.args": ["--profile", "black"],
    "files.exclude": {
        "**/__pycache__": true,
        "**/.pytest_cache": true,
        "**/*.pyc": true
    }
}
EOF

# VS Code tasks
cat > "$VSCODE_DIR/tasks.json" <<EOF
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Start Development Servers",
            "type": "shell",
            "command": "./dev-start.sh",
            "group": "build",
            "presentation": {
                "echo": true,
                "reveal": "always",
                "focus": false,
                "panel": "new"
            }
        },
        {
            "label": "Run Tests",
            "type": "shell",
            "command": "./dev-test.sh",
            "group": "test",
            "presentation": {
                "echo": true,
                "reveal": "always",
                "focus": false,
                "panel": "new"
            }
        },
        {
            "label": "Format Code",
            "type": "shell",
            "command": "./dev-format.sh",
            "group": "build"
        }
    ]
}
EOF

# VS Code launch configuration
cat > "$VSCODE_DIR/launch.json" <<EOF
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Debug TTS Server",
            "type": "python",
            "request": "launch",
            "program": "\${workspaceFolder}/src/servers/tts_server.py",
            "console": "integratedTerminal",
            "envFile": "\${workspaceFolder}/.env.dev"
        },
        {
            "name": "Debug Discovery Server",
            "type": "python",
            "request": "launch",
            "program": "\${workspaceFolder}/src/servers/agent_discovery.py",
            "console": "integratedTerminal",
            "envFile": "\${workspaceFolder}/.env.dev"
        },
        {
            "name": "Debug Tests",
            "type": "python",
            "request": "launch",
            "module": "pytest",
            "args": ["-v"],
            "console": "integratedTerminal",
            "envFile": "\${workspaceFolder}/.env.dev"
        }
    ]
}
EOF

log_dev_success "VS Code configuration created"

# Create pre-commit configuration
cat > "$INSTALL_PATH/.pre-commit-config.yaml" <<EOF
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3
        
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ["--profile", "black"]
        
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
EOF

# Create Makefile for common development tasks
cat > "$INSTALL_PATH/Makefile" <<EOF
.PHONY: help install test format lint clean dev-start dev-stop

help:  ## Show this help message
	@echo "Slaygent Development Commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*\$\$' \$(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \\033[36m%-15s\\033[0m %s\\n", \$\$1, \$\$2}'

install:  ## Install development dependencies
	python3 -m pip install --upgrade pip
	python3 -m pip install -r requirements.txt
	python3 -m pip install pytest pytest-cov pytest-asyncio black flake8 mypy pre-commit isort

test:  ## Run all tests
	./dev-test.sh

format:  ## Format code with black and isort
	./dev-format.sh

lint:  ## Run linting checks
	flake8 src/
	mypy src/
	black --check src/
	isort --check-only src/

clean:  ## Clean up generated files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov/ .pytest_cache/ .mypy_cache/

dev-start:  ## Start development servers
	./dev-start.sh

dev-stop:  ## Stop development servers
	pkill -f 'tts_server.py|agent_discovery.py' || true

coverage:  ## Generate coverage report
	pytest --cov=src --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/"

typecheck:  ## Run type checking
	mypy src/

pre-commit:  ## Run pre-commit hooks
	pre-commit run --all-files
EOF

# Create development documentation
cat > "$INSTALL_PATH/docs/DEVELOPMENT.md" <<EOF
# Development Guide

This guide covers development setup and workflows for the Slaygent Communication System.

## Quick Setup

\`\`\`bash
# Clone and setup development environment
git clone <repo-url>
cd slaygent-communication-system
./scripts/setup-dev.sh

# Or with virtual environment
./scripts/setup-dev.sh --create-venv
\`\`\`

## Development Commands

### Using Shell Scripts
\`\`\`bash
./dev-start.sh    # Start development servers
./dev-test.sh     # Run tests and linting  
./dev-format.sh   # Format code
\`\`\`

### Using Makefile
\`\`\`bash
make help         # Show all commands
make install      # Install dependencies
make test         # Run tests
make format       # Format code
make lint         # Run linting
make dev-start    # Start servers
make dev-stop     # Stop servers
\`\`\`

## VS Code Integration

1. Open project in VS Code
2. Install recommended extensions (Python, Black, etc.)
3. Use Ctrl+Shift+P > "Tasks: Run Task" for development tasks
4. Use F5 to debug servers with breakpoints

## Testing

\`\`\`bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest tests/test_sample.py::TestSample::test_sample_function

# Run async tests
pytest -k async
\`\`\`

## Code Quality

### Formatting
\`\`\`bash
# Format code
black src/
isort src/

# Check formatting
black --check src/
isort --check-only src/
\`\`\`

### Linting
\`\`\`bash
# Run flake8
flake8 src/

# Run mypy type checking
mypy src/
\`\`\`

### Pre-commit Hooks
\`\`\`bash
# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
\`\`\`

## Project Structure

\`\`\`
src/
├── servers/          # FastAPI servers
├── messaging/        # Messaging backends
├── audio/           # Audio backends
├── utils/           # Utilities
└── config/          # Configuration

tests/
├── unit/            # Unit tests
├── integration/     # Integration tests
└── fixtures/        # Test fixtures

docs/               # Documentation
bin/                # CLI scripts
scripts/            # Development scripts
\`\`\`

## Environment Configuration

Development uses \`.env.dev\` for configuration:

\`\`\`bash
# Copy and modify as needed
cp .env.example .env.dev
\`\`\`

## Adding New Features

1. Create feature branch: \`git checkout -b feature/new-feature\`
2. Write tests first: \`tests/test_new_feature.py\`
3. Implement feature in appropriate module
4. Run tests: \`make test\`
5. Format code: \`make format\`
6. Commit with pre-commit hooks
7. Submit pull request

## Debugging

### VS Code Debugging
- Set breakpoints in code
- Use F5 to start debugging
- Choose "Debug TTS Server" or "Debug Discovery Server"

### Manual Debugging
\`\`\`bash
# Start server with debugging
python3 -m pdb src/servers/tts_server.py

# Or with ipdb (install first)
python3 -c "import ipdb; ipdb.set_trace()" -m src.servers.tts_server
\`\`\`

### Logging
Development mode enables debug logging:
\`\`\`python
import logging
logging.getLogger().setLevel(logging.DEBUG)
\`\`\`

## Performance Testing

\`\`\`bash
# Benchmark TTS latency
time curl "http://localhost:9003/speak?text=hello&voice=amy"

# Load testing with ab (Apache Bench)
ab -n 100 -c 10 http://localhost:9003/health

# Memory profiling
python3 -m memory_profiler src/servers/tts_server.py
\`\`\`

## Contributing

1. Follow code style (Black, isort, flake8)
2. Write tests for new features
3. Update documentation
4. Ensure all tests pass
5. Use descriptive commit messages

## Troubleshooting

### Common Issues
- **Import errors**: Check PYTHONPATH includes src/
- **Audio issues**: Verify audio system is working
- **Port conflicts**: Check ports 9003/9005 are free

### Development Environment
- **Virtual environment**: Use \`source venv/bin/activate\`
- **Dependencies**: Run \`make install\` to update
- **Clean build**: Run \`make clean\` to remove cache files
EOF

# Final verification
log_dev_step "Verifying development setup..."

CHECKS=(
    "python3 --version"
    "pytest --version"
    "black --version" 
    "flake8 --version"
    "mypy --version"
    "isort --version"
)

for check in "${CHECKS[@]}"; do
    if $check >/dev/null 2>&1; then
        tool_name=$(echo "$check" | cut -d' ' -f1)
        log_dev_success "$tool_name: Available"
    else
        tool_name=$(echo "$check" | cut -d' ' -f1)
        log_dev_warning "$tool_name: Not available"
    fi
done

echo -e "\n${GREEN}🎉 Development environment setup complete!${NC}"
echo -e "\n${CYAN}🔧 Development Commands:${NC}"
echo -e "  ./dev-start.sh     - Start development servers"
echo -e "  ./dev-test.sh      - Run tests and linting"
echo -e "  ./dev-format.sh    - Format code"
echo -e "  make help          - Show all make commands"
echo -e "\n${CYAN}📝 VS Code:${NC}"
echo -e "  Use Ctrl+Shift+P > 'Tasks: Run Task' to run development tasks"
echo -e "  Use F5 to debug servers with breakpoints"

if [[ "$CREATE_VENV" == "true" ]]; then
    echo -e "\n${CYAN}🐍 Virtual Environment:${NC}"
    echo -e "  Activate: source $VENV_NAME/bin/activate"
    echo -e "  Deactivate: deactivate"
fi

echo -e "\n${CYAN}📚 Documentation:${NC}"
echo -e "  docs/DEVELOPMENT.md - Development guide"
echo -e "  docs/INSTALLATION.md - Installation guide"