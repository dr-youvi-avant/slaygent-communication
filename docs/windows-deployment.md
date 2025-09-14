# Windows Deployment Guide

Complete guide for deploying the Slaygent Communication System on Windows 11 with cross-platform compatibility.

## 🚀 Quick Windows Installation

### Prerequisites
- **Windows 11** (recommended) or Windows 10 version 1909+
- **PowerShell 5.1+** (included with Windows)
- **Windows Terminal** (recommended, available from Microsoft Store)
- **Administrator privileges** (for initial setup only)

### One-Command Installation
```powershell
# Run as Administrator (first time only)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\install.ps1
```

This installs:
✅ **Memurai Redis** (Windows-native Redis implementation)  
✅ **Python dependencies** with Windows-optimized packages  
✅ **Piper TTS voices** with automatic download  
✅ **PowerShell module** integration  
✅ **Windows Terminal** profiles and shortcuts  
✅ **System services** configuration (optional)  

## 📋 Windows Terminal Configuration

### Automatic Profile Setup
The installer automatically creates Windows Terminal profiles:

```json
{
    "name": "Slaygent TTS Server",
    "commandline": "powershell.exe -NoExit -Command \"cd C:\\slaygent; python src/servers/tts_server.py\"",
    "icon": "🎤",
    "colorScheme": "Campbell Powershell"
},
{
    "name": "Slaygent Agent Discovery",
    "commandline": "powershell.exe -NoExit -Command \"cd C:\\slaygent; python src/servers/agent_discovery.py\"",
    "icon": "🤖",
    "colorScheme": "Campbell Powershell"
}
```

### Manual Terminal Configuration
If you prefer manual setup:

1. **Open Windows Terminal Settings** (`Ctrl+,`)
2. **Add New Profile**:
```json
{
    "name": "Slaygent Communication",
    "commandline": "powershell.exe -NoExit -Command \"Import-Module C:\\slaygent\\scripts\\Slaygent.psm1; Set-Location C:\\slaygent\"",
    "startingDirectory": "C:\\slaygent",
    "icon": "🎯",
    "colorScheme": "Campbell Powershell",
    "fontSize": 12,
    "fontFace": "Cascadia Code"
}
```

## 🎯 PowerShell Module Usage

### Core Commands
The PowerShell module provides Windows-native commands:

```powershell
# Import the module (done automatically by installer)
Import-Module C:\slaygent\scripts\Slaygent.psm1

# Voice Commands
Say-Text "Hello from Windows!"                    # Default voice
Say-Text "System ready" -Voice "kathleen"         # Specific voice
Say-Text "Build completed" -Volume 0.8            # Custom volume

# Agent Discovery
Find-Agents                                       # List all agents
Find-Agents -Name "claude"                        # Find specific agent

# Messaging
Send-AgentMessage -Agent "claude" -Text "Hello"   # Send message
Send-AgentMessage -All -Text "System update"      # Broadcast message

# Service Management  
Start-SlaygentServices                            # Start all services
Stop-SlaygentServices                             # Stop all services
Get-SlaygentStatus                                # Check service status
```

### Advanced PowerShell Examples

#### Development Workflow Integration
```powershell
# Build notification workflow
function Invoke-BuildWithNotification {
    param([string]$ProjectPath)
    
    Set-Location $ProjectPath
    Say-Text "Starting build process"
    
    try {
        dotnet build --configuration Release
        if ($LASTEXITCODE -eq 0) {
            Say-Text "Build completed successfully" -Voice "amy"
            Send-AgentMessage -All -Text "✅ Build SUCCESS: $ProjectPath"
        } else {
            Say-Text "Build failed with errors" -Voice "kathleen"  
            Send-AgentMessage -All -Text "❌ Build FAILED: $ProjectPath"
        }
    } catch {
        Say-Text "Build process encountered an error" -Voice "ryan"
        Send-AgentMessage -All -Text "💥 Build ERROR: $($_.Exception.Message)"
    }
}

# Usage
Invoke-BuildWithNotification -ProjectPath "C:\MyProject"
```

#### System Monitoring
```powershell
# CPU and Memory monitoring with voice alerts
function Start-SystemMonitoring {
    param(
        [int]$CPUThreshold = 80,
        [int]$MemoryThreshold = 85,
        [int]$CheckInterval = 30
    )
    
    while ($true) {
        $cpu = Get-Counter '\Processor(_Total)\% Processor Time' | 
               Select-Object -ExpandProperty CounterSamples | 
               Select-Object -ExpandProperty CookedValue
               
        $memory = Get-Counter '\Memory\% Committed Bytes In Use' |
                 Select-Object -ExpandProperty CounterSamples |
                 Select-Object -ExpandProperty CookedValue
        
        if ($cpu -gt $CPUThreshold) {
            Say-Text "High CPU usage detected: $([math]::Round($cpu))%" -Voice "ryan"
            Send-AgentMessage -All -Text "⚠️ CPU: $([math]::Round($cpu))%"
        }
        
        if ($memory -gt $MemoryThreshold) {
            Say-Text "High memory usage: $([math]::Round($memory))%" -Voice "kathleen"
            Send-AgentMessage -All -Text "⚠️ Memory: $([math]::Round($memory))%"
        }
        
        Start-Sleep -Seconds $CheckInterval
    }
}

# Start monitoring in background
Start-Job -ScriptBlock { Start-SystemMonitoring }
```

## 🏭 Windows Deployment Scenarios

### Scenario 1: Developer Workstation
**Target**: Single developer with multiple AI coding assistants

```powershell
# Installation
.\install.ps1 -InstallLocation "C:\slaygent" -CreateDesktopShortcuts

# Configuration for development
$config = @{
    redis_host = "localhost"
    redis_port = 6379
    tts_voice = "amy"
    audio_device = "default"
    message_history_size = 1000
    enable_logging = $true
    log_level = "INFO"
}
$config | ConvertTo-Json | Set-Content "C:\slaygent\.env.json"

# Start services
Start-SlaygentServices -Mode "Development"
```

### Scenario 2: Team Development Server
**Target**: Shared development server for team collaboration

```powershell
# Installation with service configuration
.\install.ps1 -InstallAsService -ServiceAccount "NetworkService" -AllowRemoteConnections

# Configuration for team server
$config = @{
    redis_host = "0.0.0.0"          # Allow external connections
    redis_port = 6379
    redis_password = "team_secret"   # Secure with password
    tts_enabled = $false            # Disable audio on server
    web_ui_enabled = $true          # Enable web interface
    max_concurrent_users = 10       # Limit connections
    message_retention_hours = 24    # Auto-cleanup messages
}

# Configure Windows Firewall
New-NetFirewallRule -DisplayName "Slaygent Redis" -Direction Inbound -Protocol TCP -LocalPort 6379 -Action Allow
New-NetFirewallRule -DisplayName "Slaygent TTS" -Direction Inbound -Protocol TCP -LocalPort 9003 -Action Allow
New-NetFirewallRule -DisplayName "Slaygent Discovery" -Direction Inbound -Protocol TCP -LocalPort 9005 -Action Allow

# Install as Windows Service
New-Service -Name "SlaygentComm" -BinaryPathName "C:\slaygent\scripts\service-wrapper.exe" -StartupType Automatic
Start-Service -Name "SlaygentComm"
```

### Scenario 3: CI/CD Integration
**Target**: Automated builds with voice notifications

```powershell
# Azure DevOps Pipeline Integration
# azure-pipelines.yml snippet:
# - powershell: |
#     Import-Module C:\slaygent\scripts\Slaygent.psm1
#     Say-Text "Starting CI/CD pipeline for $(Build.Repository.Name)"
#     Send-AgentMessage -All -Text "🚀 CI/CD Started: $(Build.BuildNumber)"

# GitHub Actions Integration  
# .github/workflows/build-with-notifications.yml
name: 'Build with Slaygent Notifications'
on: [push, pull_request]
jobs:
  build:
    runs-on: windows-latest
    steps:
    - uses: actions/checkout@v3
    - name: Setup Slaygent
      run: |
        .\install.ps1 -QuietMode -NoServices
        Import-Module .\scripts\Slaygent.psm1
        Say-Text "GitHub Actions build started"
    - name: Build Project
      run: |
        dotnet build
        if ($LASTEXITCODE -eq 0) {
          Say-Text "Build successful"
        } else {
          Say-Text "Build failed" -Voice "ryan"
        }
```

### Scenario 4: WSL2 Integration
**Target**: Windows Subsystem for Linux integration

```powershell
# Install on Windows host
.\install.ps1 -EnableWSLIntegration

# Configure WSL2 access
$wslConfig = @"
[network]
generateResolvConf = false
hostname = windows-host

[interop]
enabled = true
appendWindowsPath = true
"@
$wslConfig | Set-Content "$env:USERPROFILE\.wslconfig"

# WSL2 client configuration (run in WSL2 terminal)
# export SLAYGENT_REDIS_HOST="$(cat /etc/resolv.conf | grep nameserver | cut -d' ' -f2)"
# export SLAYGENT_TTS_URL="http://${SLAYGENT_REDIS_HOST}:9003"
# pip install redis pydantic requests
```

## 🔧 Advanced Configuration

### Environment Variables (Windows-Specific)
```powershell
# System-wide configuration (requires admin)
[Environment]::SetEnvironmentVariable("SLAYGENT_REDIS_HOST", "localhost", "Machine")
[Environment]::SetEnvironmentVariable("SLAYGENT_TTS_VOICE", "amy", "Machine")
[Environment]::SetEnvironmentVariable("SLAYGENT_AUDIO_DEVICE", "default", "Machine")

# User-specific configuration  
[Environment]::SetEnvironmentVariable("SLAYGENT_LOG_LEVEL", "DEBUG", "User")
[Environment]::SetEnvironmentVariable("SLAYGENT_MESSAGE_HISTORY", "500", "User")
```

### Windows Registry Integration
```powershell
# Add to Windows context menu (right-click integration)
$regPath = "HKCU:\Software\Classes\Directory\Background\shell\Slaygent"
New-Item -Path $regPath -Force
Set-ItemProperty -Path $regPath -Name "(Default)" -Value "Send to Slaygent Agents"
Set-ItemProperty -Path $regPath -Name "Icon" -Value "C:\slaygent\assets\icon.ico"

$commandPath = "$regPath\command"
New-Item -Path $commandPath -Force  
Set-ItemProperty -Path $commandPath -Name "(Default)" -Value 'powershell.exe -Command "Import-Module C:\slaygent\scripts\Slaygent.psm1; Send-AgentMessage -All -Text \"Folder context: %V\""'
```

### Audio Device Configuration
```powershell
# List available audio devices
Get-AudioDevice | Format-Table Name, Default, Type

# Set specific audio device for Slaygent
Set-SlaygentAudioDevice -DeviceName "Speakers (High Definition Audio)"

# Configure audio levels
Set-SlaygentVolume -Master 0.8 -Voice 0.9 -Effects 0.5
```

## 🚨 Troubleshooting Windows Issues

### Common Windows Problems

#### Redis/Memurai Connection Issues
```powershell
# Check Memurai service status
Get-Service -Name "Memurai" | Format-List

# Restart Memurai service
Restart-Service -Name "Memurai" -Force

# Test Redis connection
Test-NetConnection -ComputerName localhost -Port 6379

# Check Redis logs
Get-Content "C:\Program Files\Memurai\logs\memurai.log" -Tail 20
```

#### Audio Playback Problems
```powershell
# Check Windows audio service
Get-Service -Name "AudioSrv" | Restart-Service

# Test system audio
[console]::beep(440, 500)  # 440Hz beep for 500ms

# Verify Slaygent audio backend
Test-SlaygentAudio -Voice "amy" -Text "Audio test"

# Check audio device permissions
Get-AudioDevicePermissions | Where-Object {$_.Process -like "*python*"}
```

#### PowerShell Module Issues
```powershell
# Reload Slaygent module
Remove-Module Slaygent -Force
Import-Module C:\slaygent\scripts\Slaygent.psm1 -Force

# Check module version and functions
Get-Module Slaygent | Format-List
Get-Command -Module Slaygent

# Verify execution policy
Get-ExecutionPolicy -Scope CurrentUser
# Should be "RemoteSigned" or "Unrestricted"
```

#### Windows Firewall Configuration
```powershell
# Check firewall rules
Get-NetFirewallRule -DisplayName "*Slaygent*" | Format-Table DisplayName, Enabled, Action

# Test port accessibility
Test-NetConnection -ComputerName localhost -Port 9003  # TTS Server
Test-NetConnection -ComputerName localhost -Port 9005  # Discovery Server
Test-NetConnection -ComputerName localhost -Port 6379  # Redis/Memurai

# Add firewall rules if needed
New-NetFirewallRule -DisplayName "Slaygent TTS" -Direction Inbound -Protocol TCP -LocalPort 9003 -Action Allow
New-NetFirewallRule -DisplayName "Slaygent Discovery" -Direction Inbound -Protocol TCP -LocalPort 9005 -Action Allow
```

### Performance Optimization

#### Windows-Specific Optimizations
```powershell
# Disable Windows Defender real-time scanning for Slaygent directory (optional)
Add-MpPreference -ExclusionPath "C:\slaygent"

# Set high performance power plan
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c

# Optimize Python process priority
Get-Process -Name python | ForEach-Object { $_.PriorityClass = "High" }

# Configure Windows Timer Resolution for low-latency audio
# Note: Requires additional tools or registry modifications
```

#### Memory and CPU Management
```powershell
# Monitor Slaygent resource usage
Get-Process -Name python | Select-Object Name, CPU, WorkingSet, PagedMemorySize | Format-Table

# Set memory limits for Python processes (if needed)
# This requires process-specific configuration in the application
```

## 📚 Integration Examples

### Visual Studio Code Integration
```json
// .vscode/tasks.json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Notify Build Start",
            "type": "shell",
            "command": "powershell",
            "args": [
                "-Command",
                "Import-Module C:\\slaygent\\scripts\\Slaygent.psm1; Say-Text 'Build started for ${workspaceFolderBasename}'"
            ],
            "group": "build",
            "presentation": {
                "echo": false,
                "reveal": "never"
            }
        },
        {
            "label": "Build with Notifications",
            "type": "shell",
            "command": "dotnet",
            "args": ["build"],
            "dependsOn": "Notify Build Start",
            "group": {
                "kind": "build",
                "isDefault": true
            },
            "problemMatcher": "$msCompile"
        }
    ]
}
```

### Windows Task Scheduler Integration
```powershell
# Create scheduled task for system monitoring
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-File C:\slaygent\scripts\monitor-system.ps1"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

Register-ScheduledTask -TaskName "Slaygent System Monitor" -Action $action -Trigger $trigger -Principal $principal -Description "Monitor system resources with Slaygent notifications"
```

### Windows Event Log Integration
```powershell
# Create custom event log source
New-EventLog -LogName "Application" -Source "SlaygentComm"

# Log events with voice notifications
function Write-SlaygentEvent {
    param(
        [string]$Message,
        [string]$EventType = "Information",
        [int]$EventID = 1000,
        [bool]$VoiceAlert = $false
    )
    
    Write-EventLog -LogName "Application" -Source "SlaygentComm" -EntryType $EventType -EventId $EventID -Message $Message
    
    if ($VoiceAlert) {
        $voice = switch ($EventType) {
            "Error" { "ryan" }
            "Warning" { "kathleen" }
            default { "amy" }
        }
        Say-Text $Message -Voice $voice
        Send-AgentMessage -All -Text "📋 Event: $Message"
    }
}

# Usage
Write-SlaygentEvent -Message "Slaygent services started successfully" -VoiceAlert $true
```

## 🎯 Next Steps

After successful Windows deployment:

1. **Test Core Functionality**:
   ```powershell
   Test-SlaygentInstallation  # Run comprehensive test suite
   ```

2. **Configure Team Integration**:
   ```powershell
   Set-SlaygentTeamConfig -TeamName "MyTeam" -SharedRedis "team-redis.company.com"
   ```

3. **Set Up Monitoring**:
   ```powershell
   Enable-SlaygentMonitoring -AlertThreshold "High" -VoiceAlerts $true
   ```

4. **Explore Advanced Features**:
   - Custom voice training with Windows Speech Platform
   - Integration with Microsoft Teams or Slack
   - Windows-specific agent plugins and extensions

---

## 📞 Support

For Windows-specific issues:
- **PowerShell Module**: Check `Get-Help Slaygent` for built-in documentation
- **Event Logs**: Check Windows Event Viewer → Applications and Services Logs
- **Performance**: Use Windows Performance Monitor for detailed metrics
- **Network**: Use `netstat -an | findstr 9003` to check port bindings

**Made with ❤️ for Windows developers and AI agent communication**