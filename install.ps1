# Slaygent Communication System - Windows Installation Script
# PowerShell-native installation with Windows Terminal integration
# Achieves: <5 minute setup, native Windows Terminal support, optional WSL bridge

[CmdletBinding()]
param(
    [string]$InstallPath = "$env:USERPROFILE\Slaygent",
    [switch]$SkipRedis,
    [switch]$SkipVoices,
    [switch]$UseMemurai,
    [string]$PythonVersion = "3.12",
    [switch]$DevMode,
    [switch]$Quiet
)

# Configuration
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Colors for output
$Colors = @{
    Success = "Green"
    Warning = "Yellow"  
    Error = "Red"
    Info = "Cyan"
    Debug = "Magenta"
}

function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White", [switch]$NoNewline)
    if (-not $Quiet) {
        if ($NoNewline) {
            Write-Host $Message -ForegroundColor $Color -NoNewline
        } else {
            Write-Host $Message -ForegroundColor $Color
        }
    }
}

function Write-Step {
    param([string]$Message)
    Write-ColorOutput "🔄 $Message" $Colors.Info
}

function Write-Success {
    param([string]$Message)
    Write-ColorOutput "✅ $Message" $Colors.Success
}

function Write-Warning {
    param([string]$Message)
    Write-ColorOutput "⚠️  $Message" $Colors.Warning
}

function Write-Error {
    param([string]$Message)
    Write-ColorOutput "❌ $Message" $Colors.Error
}

function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-WindowsTerminal {
    return (Get-Command "wt.exe" -ErrorAction SilentlyContinue) -ne $null
}

function Test-WSL {
    return (Get-Command "wsl.exe" -ErrorAction SilentlyContinue) -ne $null
}

function Install-Python {
    Write-Step "Checking Python installation..."
    
    $pythonExes = @("python3", "python", "py")
    $pythonCmd = $null
    
    foreach ($exe in $pythonExes) {
        if (Get-Command $exe -ErrorAction SilentlyContinue) {
            $version = & $exe --version 2>&1
            if ($version -match "Python (\d+\.\d+)") {
                $ver = [Version]$matches[1]
                if ($ver -ge [Version]"3.8") {
                    $pythonCmd = $exe
                    Write-Success "Found Python $($matches[1]) at $exe"
                    break
                }
            }
        }
    }
    
    if (-not $pythonCmd) {
        Write-Step "Installing Python $PythonVersion via winget..."
        try {
            winget install Python.Python.3.12 --silent --accept-source-agreements
            Start-Sleep 5
            # Refresh PATH
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
            $pythonCmd = "python"
        } catch {
            throw "Failed to install Python. Please install Python 3.8+ manually from python.org"
        }
    }
    
    return $pythonCmd
}

function Install-Redis {
    if ($SkipRedis) {
        Write-Warning "Skipping Redis installation (will use fallback messaging)"
        return $false
    }
    
    Write-Step "Setting up Redis for messaging..."
    
    # Check if Redis is already running
    try {
        $response = Invoke-WebRequest "http://localhost:6379" -TimeoutSec 2 -ErrorAction SilentlyContinue
        Write-Success "Redis already running on localhost:6379"
        return $true
    } catch {
        # Redis not running, need to install
    }
    
    if ($UseMemurai) {
        Write-Step "Installing Memurai (Windows Redis compatible)..."
        try {
            winget install Memurai.Memurai --silent --accept-source-agreements
            Start-Service Memurai
            Write-Success "Memurai installed and started"
            return $true
        } catch {
            Write-Warning "Failed to install Memurai. Trying Redis for Windows..."
        }
    }
    
    # Try Redis for Windows
    Write-Step "Installing Redis for Windows..."
    try {
        # Download and extract Redis
        $redisUrl = "https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip"
        $redisPath = "$InstallPath\redis"
        $redisZip = "$env:TEMP\redis.zip"
        
        if (-not (Test-Path $redisPath)) {
            New-Item -ItemType Directory -Path $redisPath -Force | Out-Null
            
            Write-Step "Downloading Redis..."
            Invoke-WebRequest -Uri $redisUrl -OutFile $redisZip
            
            Write-Step "Extracting Redis..."
            Expand-Archive -Path $redisZip -DestinationPath $redisPath -Force
            Remove-Item $redisZip -Force
        }
        
        # Start Redis server
        $redisExe = Get-ChildItem -Path $redisPath -Filter "redis-server.exe" -Recurse | Select-Object -First 1
        if ($redisExe) {
            Start-Process -FilePath $redisExe.FullName -WindowStyle Hidden
            Start-Sleep 3
            Write-Success "Redis server started"
            return $true
        } else {
            throw "Redis executable not found"
        }
    } catch {
        Write-Warning "Failed to install Redis: $($_.Exception.Message)"
        Write-Warning "Will use fallback file-based messaging"
        return $false
    }
}

function Install-PythonDependencies {
    param([string]$PythonCmd)
    
    Write-Step "Installing Python dependencies..."
    
    try {
        & $PythonCmd -m pip install --upgrade pip
        & $PythonCmd -m pip install -r requirements.txt
        Write-Success "Python dependencies installed"
    } catch {
        throw "Failed to install Python dependencies: $($_.Exception.Message)"
    }
}

function Download-VoiceModels {
    if ($SkipVoices) {
        Write-Warning "Skipping voice model downloads"
        return
    }
    
    Write-Step "Downloading Piper voice models..."
    
    $voicesDir = "$InstallPath\voices"
    if (-not (Test-Path $voicesDir)) {
        New-Item -ItemType Directory -Path $voicesDir -Force | Out-Null
    }
    
    # Default voices to download
    $voices = @(
        @{ Name = "amy"; Url = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx"; Config = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx.json" }
        @{ Name = "danny"; Url = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/danny/low/en_US-danny-low.onnx"; Config = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/danny/low/en_US-danny-low.onnx.json" }
    )
    
    foreach ($voice in $voices) {
        $voicePath = "$voicesDir\$($voice.Name)"
        if (-not (Test-Path $voicePath)) {
            New-Item -ItemType Directory -Path $voicePath -Force | Out-Null
        }
        
        $modelFile = "$voicePath\model.onnx"
        $configFile = "$voicePath\config.json"
        
        if (-not (Test-Path $modelFile)) {
            Write-Step "Downloading $($voice.Name) voice model..."
            try {
                Invoke-WebRequest -Uri $voice.Url -OutFile $modelFile -UseBasicParsing
                Invoke-WebRequest -Uri $voice.Config -OutFile $configFile -UseBasicParsing
                Write-Success "Downloaded $($voice.Name) voice model"
            } catch {
                Write-Warning "Failed to download $($voice.Name): $($_.Exception.Message)"
            }
        } else {
            Write-Success "$($voice.Name) voice model already exists"
        }
    }
}

function Setup-PowerShellModule {
    Write-Step "Setting up Slaygent PowerShell module..."
    
    $moduleDir = "$env:USERPROFILE\Documents\PowerShell\Modules\Slaygent"
    if (-not (Test-Path $moduleDir)) {
        New-Item -ItemType Directory -Path $moduleDir -Force | Out-Null
    }
    
    $moduleContent = @"
# Slaygent PowerShell Module: Native Windows Port
# PowerShell-centric approach for Windows Terminal integration

# Module metadata
@{
    ModuleVersion = '1.0.0'
    GUID = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
    Author = 'Slaygent Team'
    Description = 'Native Windows Terminal integration for Slaygent Communication System'
    PowerShellVersion = '5.1'
    FunctionsToExport = @(
        'Start-SlayServices',
        'Stop-SlayServices', 
        'Test-SlayHealth',
        'Get-SlayAgents',
        'Send-SlayMessage',
        'Invoke-SlayTTS'
    )
}

# Configuration
`$script:Config = @{
    InstallPath = '$InstallPath'
    TTSUrl = 'http://localhost:9003'
    DiscoveryUrl = 'http://localhost:9005'
    RedisHost = 'localhost:6379'
    DefaultVoice = 'amy'
    PaneProfiles = @{ 
        Claude = 'powershell -Command "claude"'
        OpenCode = 'powershell -Command "opencode"'
        Python = 'python'
    }
}

# Import required assemblies
Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue

# Core Functions
function Start-SlayServices {
    [CmdletBinding()]
    param([switch]`$Quiet)
    
    Push-Location `$script:Config.InstallPath
    
    try {
        # Start TTS Server
        if (-not (Test-NetConnection -ComputerName localhost -Port 9003 -InformationLevel Quiet -WarningAction SilentlyContinue)) {
            Start-Process python -ArgumentList "src/servers/tts_server.py" -WindowStyle Hidden -WorkingDirectory `$PWD
            Start-Sleep 2
        }
        
        # Start Discovery Server  
        if (-not (Test-NetConnection -ComputerName localhost -Port 9005 -InformationLevel Quiet -WarningAction SilentlyContinue)) {
            Start-Process python -ArgumentList "src/servers/agent_discovery.py" -WindowStyle Hidden -WorkingDirectory `$PWD
            Start-Sleep 2
        }
        
        # Test services
        if (Test-SlayHealth) {
            if (-not `$Quiet) { Write-Host "✅ Slaygent services started successfully" -ForegroundColor Green }
            Invoke-SlayTTS "Slaygent Hub ignited - PowerShell native"
        } else {
            throw "Services failed to start properly"
        }
    } finally {
        Pop-Location
    }
}

function Stop-SlayServices {
    Get-Process python -ErrorAction SilentlyContinue | Where-Object { `$_.MainWindowTitle -match "tts_server|agent_discovery" } | Stop-Process -Force
    Write-Host "🛑 Slaygent services stopped" -ForegroundColor Yellow
}

function Test-SlayHealth {
    try {
        `$tts = Invoke-WebRequest "`$(`$script:Config.TTSUrl)/health" -UseBasicParsing -TimeoutSec 5
        `$disc = Invoke-WebRequest "`$(`$script:Config.DiscoveryUrl)/health" -UseBasicParsing -TimeoutSec 5
        return (`$tts.StatusCode -eq 200) -and (`$disc.StatusCode -eq 200)
    } catch {
        return `$false
    }
}

function Get-SlayAgents {
    try {
        `$response = Invoke-WebRequest "`$(`$script:Config.DiscoveryUrl)/agents" -UseBasicParsing
        `$agents = `$response.Content | ConvertFrom-Json
        return `$agents
    } catch {
        Write-Warning "Failed to get agents: `$(`$_.Exception.Message)"
        return @{}
    }
}

function Send-SlayMessage {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=`$true)][string]`$Agent,
        [Parameter(Mandatory=`$true)][string]`$Message,
        [switch]`$ToAll,
        [switch]`$Command
    )
    
    try {
        `$body = @{
            agent = `$Agent
            message = `$Message
            broadcast = `$ToAll.IsPresent
        } | ConvertTo-Json
        
        Invoke-WebRequest "`$(`$script:Config.TTSUrl)/message" -Method Post -Body `$body -ContentType "application/json" -UseBasicParsing | Out-Null
        
        if (`$Command) {
            Invoke-SlayTTS "Command executed for `$Agent"
        }
        
        Write-Host "📨 Message sent to `$Agent`: `$Message" -ForegroundColor Cyan
    } catch {
        Write-Warning "Failed to send message: `$(`$_.Exception.Message)"
    }
}

function Invoke-SlayTTS {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=`$true)][string]`$Text,
        [string]`$Voice = `$script:Config.DefaultVoice
    )
    
    try {
        `$uri = "`$(`$script:Config.TTSUrl)/speak?text=`$([uri]::EscapeDataString(`$Text))&voice=`$Voice"
        Invoke-WebRequest -Uri `$uri -Method Get -UseBasicParsing -TimeoutSec 10 | Out-Null
        Write-Host "🔊 TTS: `$Text (`$Voice)" -ForegroundColor Green
    } catch {
        Write-Warning "TTS failed: `$(`$_.Exception.Message)"
        Write-Host "📢 `$Text" -ForegroundColor Yellow  # Fallback to text
    }
}

# Aliases for convenience
Set-Alias -Name slay-start -Value Start-SlayServices
Set-Alias -Name slay-stop -Value Stop-SlayServices
Set-Alias -Name slay-health -Value Test-SlayHealth
Set-Alias -Name slay-agents -Value Get-SlayAgents
Set-Alias -Name slay-msg -Value Send-SlayMessage
Set-Alias -Name slay-say -Value Invoke-SlayTTS

# Export functions
Export-ModuleMember -Function * -Alias *
"@

    $manifestPath = "$moduleDir\Slaygent.psd1"
    $modulePath = "$moduleDir\Slaygent.psm1"
    
    $moduleContent | Out-File -FilePath $modulePath -Encoding UTF8
    
    # Create module manifest
    $manifest = @"
@{
    RootModule = 'Slaygent.psm1'
    ModuleVersion = '1.0.0'
    GUID = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
    Author = 'Slaygent Team'
    CompanyName = 'Slaygent'
    Copyright = '(c) 2025 Slaygent Team'
    Description = 'Native Windows Terminal integration for Slaygent Communication System'
    PowerShellVersion = '5.1'
    FunctionsToExport = @(
        'Start-SlayServices',
        'Stop-SlayServices', 
        'Test-SlayHealth',
        'Get-SlayAgents',
        'Send-SlayMessage',
        'Invoke-SlayTTS'
    )
    AliasesToExport = @(
        'slay-start',
        'slay-stop', 
        'slay-health',
        'slay-agents',
        'slay-msg',
        'slay-say'
    )
}
"@
    
    $manifest | Out-File -FilePath $manifestPath -Encoding UTF8
    Write-Success "PowerShell module installed at $moduleDir"
}

function Setup-Configuration {
    Write-Step "Creating configuration files..."
    
    # Create .env file
    $envContent = @"
# Slaygent Communication System Configuration
# Generated by install.ps1 on $(Get-Date)

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

# Windows-specific
WINDOWS_TERMINAL_INTEGRATION=true
POWERSHELL_MODULE_PATH=$env:USERPROFILE\Documents\PowerShell\Modules\Slaygent
"@

    $envContent | Out-File -FilePath "$InstallPath\.env" -Encoding UTF8
    
    Write-Success "Configuration files created"
}

function Setup-WindowsTerminalProfile {
    if (-not (Test-WindowsTerminal)) {
        Write-Warning "Windows Terminal not found. Please install from Microsoft Store for optimal experience."
        return
    }
    
    Write-Step "Configuring Windows Terminal integration..."
    
    $settingsPath = "$env:LOCALAPPDATA\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json"
    
    if (Test-Path $settingsPath) {
        try {
            $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
            
            # Add Slaygent profile if not exists
            $slaygentProfile = @{
                guid = "{12345678-1234-1234-1234-123456789abc}"
                name = "Slaygent Hub"
                commandline = "powershell.exe -NoExit -Command `"Import-Module Slaygent; Start-SlayServices`""
                startingDirectory = $InstallPath
                icon = "🤖"
                colorScheme = "Campbell"
            }
            
            $existingProfile = $settings.profiles.list | Where-Object { $_.name -eq "Slaygent Hub" }
            if (-not $existingProfile) {
                $settings.profiles.list += $slaygentProfile
                $settings | ConvertTo-Json -Depth 10 | Out-File -FilePath $settingsPath -Encoding UTF8
                Write-Success "Added Slaygent Hub profile to Windows Terminal"
            } else {
                Write-Success "Slaygent Hub profile already exists in Windows Terminal"
            }
        } catch {
            Write-Warning "Failed to modify Windows Terminal settings: $($_.Exception.Message)"
        }
    }
}

function Test-Installation {
    Write-Step "Testing installation..."
    
    $testsPassed = 0
    $totalTests = 5
    
    # Test 1: Python availability
    try {
        $python = Install-Python
        & $python --version | Out-Null
        Write-Success "✓ Python executable working"
        $testsPassed++
    } catch {
        Write-Error "✗ Python test failed: $($_.Exception.Message)"
    }
    
    # Test 2: Dependencies
    try {
        & python -c "import fastapi, piper, redis" 2>$null
        Write-Success "✓ Python dependencies available"
        $testsPassed++
    } catch {
        Write-Error "✗ Dependency test failed"
    }
    
    # Test 3: Voice models
    if (Test-Path "$InstallPath\voices\amy\model.onnx") {
        Write-Success "✓ Voice models downloaded"
        $testsPassed++
    } else {
        Write-Error "✗ Voice models missing"
    }
    
    # Test 4: Configuration
    if (Test-Path "$InstallPath\.env") {
        Write-Success "✓ Configuration files created"
        $testsPassed++
    } else {
        Write-Error "✗ Configuration files missing"
    }
    
    # Test 5: PowerShell module
    try {
        Import-Module Slaygent -ErrorAction Stop
        Write-Success "✓ PowerShell module loadable"
        $testsPassed++
    } catch {
        Write-Error "✗ PowerShell module test failed: $($_.Exception.Message)"
    }
    
    Write-ColorOutput "`n📊 Installation Test Results: $testsPassed/$totalTests tests passed" $Colors.Info
    
    if ($testsPassed -eq $totalTests) {
        Write-Success "🎉 Installation completed successfully!"
        return $true
    } else {
        Write-Warning "⚠️  Installation completed with issues. See errors above."
        return $false
    }
}

function Show-QuickStart {
    Write-ColorOutput "`n🚀 Quick Start Guide:" $Colors.Info
    Write-ColorOutput "1. Open Windows Terminal" $Colors.Info
    Write-ColorOutput "2. Import the Slaygent module:" $Colors.Info
    Write-ColorOutput "   Import-Module Slaygent" $Colors.Debug
    Write-ColorOutput "3. Start services:" $Colors.Info  
    Write-ColorOutput "   Start-SlayServices" $Colors.Debug
    Write-ColorOutput "4. Test TTS:" $Colors.Info
    Write-ColorOutput "   Invoke-SlayTTS 'Hello from Slaygent!'" $Colors.Debug
    Write-ColorOutput "5. Check agents:" $Colors.Info
    Write-ColorOutput "   Get-SlayAgents" $Colors.Debug
    Write-ColorOutput "`nAlternatively, use the Slaygent Hub profile in Windows Terminal!" $Colors.Success
    
    if ($DevMode) {
        Write-ColorOutput "`n🔧 Developer Commands:" $Colors.Info
        Write-ColorOutput "   cd $InstallPath" $Colors.Debug
        Write-ColorOutput "   python src/servers/tts_server.py" $Colors.Debug
        Write-ColorOutput "   python src/servers/agent_discovery.py" $Colors.Debug
    }
}

# Main Installation Process
try {
    Write-ColorOutput "🤖 Slaygent Communication System - Windows Installer" $Colors.Success
    Write-ColorOutput "Installing to: $InstallPath" $Colors.Info
    
    if (-not $Quiet) {
        Write-ColorOutput "Press Ctrl+C to cancel, or Enter to continue..." $Colors.Warning
        Read-Host
    }
    
    # Create installation directory
    if (-not (Test-Path $InstallPath)) {
        New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
    }
    
    # Copy current directory to install path if not the same
    if ((Get-Location).Path -ne $InstallPath) {
        Write-Step "Copying Slaygent files to $InstallPath..."
        Copy-Item -Path ".\*" -Destination $InstallPath -Recurse -Force
    }
    
    Push-Location $InstallPath
    
    try {
        # Installation steps
        $python = Install-Python
        Install-PythonDependencies -PythonCmd $python
        $redisInstalled = Install-Redis
        Download-VoiceModels
        Setup-Configuration
        Setup-PowerShellModule
        Setup-WindowsTerminalProfile
        
        # Test installation
        $installSuccess = Test-Installation
        
        # Show usage guide
        Show-QuickStart
        
        if ($installSuccess) {
            Write-ColorOutput "`n🎉 Slaygent installation completed successfully!" $Colors.Success
            Write-ColorOutput "⏱️  Installation time: $((Get-Date) - $startTime)" $Colors.Info
            
            if (-not $Quiet) {
                $response = Read-Host "`nWould you like to start Slaygent services now? (y/n)"
                if ($response -match '^[Yy]') {
                    Import-Module Slaygent
                    Start-SlayServices
                }
            }
        }
        
    } finally {
        Pop-Location
    }
    
} catch {
    Write-Error "Installation failed: $($_.Exception.Message)"
    Write-ColorOutput "Please check the error above and try again." $Colors.Error
    Write-ColorOutput "For help, visit: https://github.com/slaygent/communication-system" $Colors.Info
    exit 1
}