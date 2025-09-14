# Slaygent Communication System - Development Setup Script
# PowerShell script for setting up development environment

[CmdletBinding()]
param(
    [string]$InstallPath = ".",
    [switch]$SkipRedis,
    [switch]$SkipVoices,
    [switch]$CreateVenv,
    [string]$VenvName = "slaygent-dev"
)

$ErrorActionPreference = "Stop"

function Write-DevStep {
    param([string]$Message)
    Write-Host "🔧 $Message" -ForegroundColor Cyan
}

function Write-DevSuccess {
    param([string]$Message)  
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-DevWarning {
    param([string]$Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

Write-Host "🚀 Slaygent Development Environment Setup" -ForegroundColor Green
Write-Host "Setting up development environment in: $InstallPath" -ForegroundColor Cyan

# Create virtual environment if requested
if ($CreateVenv) {
    Write-DevStep "Creating Python virtual environment: $VenvName"
    python -m venv $VenvName
    & ".\$VenvName\Scripts\Activate.ps1"
    Write-DevSuccess "Virtual environment created and activated"
}

# Install development dependencies
Write-DevStep "Installing development dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install development tools
$devTools = @(
    "pytest",
    "pytest-cov", 
    "pytest-asyncio",
    "black",
    "flake8",
    "mypy",
    "pre-commit"
)

foreach ($tool in $devTools) {
    Write-DevStep "Installing $tool..."
    pip install $tool
}

# Setup pre-commit hooks
Write-DevStep "Setting up pre-commit hooks..."
pre-commit install

# Create development configuration
Write-DevStep "Creating development configuration..."
$devEnv = @"
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
"@

$devEnv | Out-File -FilePath "$InstallPath\.env.dev" -Encoding UTF8

# Create pytest configuration
$pytestConfig = @"
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = --cov=src --cov-report=html --cov-report=term-missing
asyncio_mode = auto
"@

$pytestConfig | Out-File -FilePath "$InstallPath\pytest.ini" -Encoding UTF8

# Create development scripts
$devScripts = @{
    "dev-start.ps1" = @"
# Start Slaygent in development mode
Push-Location `$PSScriptRoot
try {
    if (Test-Path .env.dev) {
        Get-Content .env.dev | ForEach { 
            if (`$_ -match '^([^#][^=]+)=(.*)') {
                [Environment]::SetEnvironmentVariable(`$matches[1], `$matches[2], 'Process')
            }
        }
    }
    
    Write-Host "🚀 Starting Slaygent in development mode..." -ForegroundColor Green
    Start-Process python -ArgumentList "src/servers/tts_server.py" -WindowStyle Normal
    Start-Sleep 2
    Start-Process python -ArgumentList "src/servers/agent_discovery.py" -WindowStyle Normal
    
    Write-Host "✅ Development servers started!" -ForegroundColor Green
    Write-Host "TTS: http://localhost:9003" -ForegroundColor Cyan
    Write-Host "Discovery: http://localhost:9005" -ForegroundColor Cyan
} finally {
    Pop-Location
}
"@

    "dev-test.ps1" = @"
# Run tests in development mode
Push-Location `$PSScriptRoot
try {
    Write-Host "🧪 Running tests..." -ForegroundColor Green
    pytest -v
    
    Write-Host "📊 Running type checks..." -ForegroundColor Green  
    mypy src/
    
    Write-Host "🎨 Running code formatting check..." -ForegroundColor Green
    black --check src/
    
    Write-Host "📏 Running linting..." -ForegroundColor Green
    flake8 src/
} finally {
    Pop-Location
}
"@

    "dev-format.ps1" = @"
# Format code in development mode
Push-Location `$PSScriptRoot
try {
    Write-Host "🎨 Formatting code with Black..." -ForegroundColor Green
    black src/
    
    Write-Host "✅ Code formatting complete!" -ForegroundColor Green
} finally {
    Pop-Location
}
"@
}

foreach ($script in $devScripts.Keys) {
    $devScripts[$script] | Out-File -FilePath "$InstallPath\$script" -Encoding UTF8
    Write-DevSuccess "Created development script: $script"
}

# Create test directory structure
$testDirs = @(
    "tests",
    "tests\unit",
    "tests\integration", 
    "tests\fixtures"
)

foreach ($dir in $testDirs) {
    $fullPath = "$InstallPath\$dir"
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
        Write-DevSuccess "Created test directory: $dir"
    }
}

# Create sample test files
$testInit = @"
# Test package initialization
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
"@

$testInit | Out-File -FilePath "$InstallPath\tests\__init__.py" -Encoding UTF8

$sampleTest = @"
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
"@

$sampleTest | Out-File -FilePath "$InstallPath\tests\test_sample.py" -Encoding UTF8

# Create VS Code configuration
$vscodeDir = "$InstallPath\.vscode"
if (-not (Test-Path $vscodeDir)) {
    New-Item -ItemType Directory -Path $vscodeDir -Force | Out-Null
}

$vscodeSettings = @{
    "python.defaultInterpreterPath" = if ($CreateVenv) { ".\$VenvName\Scripts\python.exe" } else { "python" }
    "python.testing.pytestEnabled" = $true
    "python.testing.unittestEnabled" = $false
    "python.linting.enabled" = $true
    "python.linting.flake8Enabled" = $true
    "python.formatting.provider" = "black"
    "python.sortImports.args" = @("--profile", "black")
    "files.exclude" = @{
        "**/__pycache__" = $true
        "**/.pytest_cache" = $true
        "**/*.pyc" = $true
    }
}

$vscodeSettings | ConvertTo-Json -Depth 3 | Out-File -FilePath "$vscodeDir\settings.json" -Encoding UTF8

$vscodeTasksContent = @"
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Start Development Servers",
            "type": "shell",
            "command": "powershell",
            "args": ["-File", "./dev-start.ps1"],
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
            "command": "powershell",
            "args": ["-File", "./dev-test.ps1"],
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
            "command": "powershell", 
            "args": ["-File", "./dev-format.ps1"],
            "group": "build"
        }
    ]
}
"@

$vscodeTasksContent | Out-File -FilePath "$vscodeDir\tasks.json" -Encoding UTF8

# Create launch configuration for debugging
$vscodelaunchContent = @"
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
"@

$vscodelaunchContent | Out-File -FilePath "$vscodeDir\launch.json" -Encoding UTF8

Write-DevSuccess "VS Code configuration created"

# Create pre-commit configuration
$preCommitConfig = @"
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
        
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
"@

$preCommitConfig | Out-File -FilePath "$InstallPath\.pre-commit-config.yaml" -Encoding UTF8

# Final development setup verification
Write-DevStep "Verifying development setup..."

$checks = @(
    @{ Name = "Python"; Command = "python --version" }
    @{ Name = "Pytest"; Command = "pytest --version" }
    @{ Name = "Black"; Command = "black --version" }
    @{ Name = "Flake8"; Command = "flake8 --version" }
    @{ Name = "MyPy"; Command = "mypy --version" }
)

foreach ($check in $checks) {
    try {
        $result = Invoke-Expression $check.Command 2>&1
        Write-DevSuccess "$($check.Name): Available"
    } catch {
        Write-DevWarning "$($check.Name): Not available - $($_.Exception.Message)"
    }
}

Write-Host "`n🎉 Development environment setup complete!" -ForegroundColor Green
Write-Host "`n🔧 Development Commands:" -ForegroundColor Cyan
Write-Host "  .\dev-start.ps1    - Start development servers" -ForegroundColor White
Write-Host "  .\dev-test.ps1     - Run tests and linting" -ForegroundColor White  
Write-Host "  .\dev-format.ps1   - Format code with Black" -ForegroundColor White
Write-Host "`n📝 VS Code:" -ForegroundColor Cyan
Write-Host "  Use Ctrl+Shift+P > 'Tasks: Run Task' to run development tasks" -ForegroundColor White
Write-Host "  Use F5 to debug servers with breakpoints" -ForegroundColor White

if ($CreateVenv) {
    Write-Host "`n🐍 Virtual Environment:" -ForegroundColor Cyan
    Write-Host "  Activate: .\$VenvName\Scripts\Activate.ps1" -ForegroundColor White
    Write-Host "  Deactivate: deactivate" -ForegroundColor White
}