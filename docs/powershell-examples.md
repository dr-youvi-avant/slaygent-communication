# PowerShell Usage Examples

Advanced PowerShell scripting examples for the Slaygent Communication System.

## 🎯 Basic PowerShell Commands

### Voice and Messaging Commands
```powershell
# Import the Slaygent module
Import-Module "$env:ProgramFiles\Slaygent\scripts\Slaygent.psm1"

# Basic voice output
Say-Text "Hello from Windows PowerShell"
Say-Text "Build completed successfully" -Voice "amy"
Say-Text "Critical alert" -Voice "ryan" -Volume 1.0

# Agent discovery and messaging
Find-Agents                                          # List all agents
Find-Agents -Name "claude"                          # Find specific agent
Send-AgentMessage -Agent "claude" -Text "Hello"     # Send to specific agent
Send-AgentMessage -All -Text "System update ready"  # Broadcast to all

# Service management
Start-SlaygentServices                              # Start all services
Stop-SlaygentServices                               # Stop all services  
Get-SlaygentStatus                                  # Check service status
Restart-SlaygentServices                            # Restart all services
```

## 🏗️ Development Workflow Integration

### Build Process Automation
```powershell
function Invoke-SmartBuild {
    param(
        [Parameter(Mandatory=$true)][string]$ProjectPath,
        [string]$Configuration = "Release",
        [switch]$RunTests,
        [switch]$VoiceNotifications = $true
    )
    
    $startTime = Get-Date
    $projectName = Split-Path $ProjectPath -Leaf
    
    if ($VoiceNotifications) {
        Say-Text "Starting build for $projectName" -Voice "amy"
        Send-AgentMessage -All -Text "🔨 BUILD START: $projectName ($Configuration)"
    }
    
    try {
        Set-Location $ProjectPath
        
        # Clean previous build
        if (Test-Path "bin") { Remove-Item "bin" -Recurse -Force }
        if (Test-Path "obj") { Remove-Item "obj" -Recurse -Force }
        
        # Restore dependencies
        Write-Host "Restoring dependencies..." -ForegroundColor Yellow
        dotnet restore
        if ($LASTEXITCODE -ne 0) { throw "Dependency restoration failed" }
        
        # Build project
        Write-Host "Building project..." -ForegroundColor Yellow  
        dotnet build --configuration $Configuration --no-restore
        if ($LASTEXITCODE -ne 0) { throw "Build compilation failed" }
        
        # Run tests if requested
        if ($RunTests) {
            Write-Host "Running tests..." -ForegroundColor Yellow
            dotnet test --configuration $Configuration --no-build --verbosity normal
            if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
        }
        
        $duration = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)
        
        if ($VoiceNotifications) {
            Say-Text "Build completed successfully in $duration seconds" -Voice "amy"
            Send-AgentMessage -All -Text "✅ BUILD SUCCESS: $projectName ($($duration)s)"
        }
        
        Write-Host "Build completed successfully!" -ForegroundColor Green
        return $true
        
    } catch {
        $duration = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)
        
        if ($VoiceNotifications) {
            Say-Text "Build failed: $($_.Exception.Message)" -Voice "ryan"
            Send-AgentMessage -All -Text "❌ BUILD FAILED: $projectName - $($_.Exception.Message)"
        }
        
        Write-Host "Build failed: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# Usage examples
Invoke-SmartBuild -ProjectPath "C:\Projects\MyApp" -RunTests
Invoke-SmartBuild -ProjectPath "C:\Projects\API" -Configuration "Debug" -VoiceNotifications:$false
```

### Git Workflow Integration
```powershell
function Invoke-GitWorkflow {
    param(
        [string]$CommitMessage,
        [string]$Branch = "main",
        [switch]$PushToRemote,
        [switch]$VoiceConfirmation = $true
    )
    
    try {
        # Check git status
        $status = git status --porcelain
        if (-not $status) {
            if ($VoiceConfirmation) {
                Say-Text "No changes to commit" -Voice "amy"
            }
            Write-Host "No changes detected" -ForegroundColor Yellow
            return
        }
        
        # Show changes
        Write-Host "Changes detected:" -ForegroundColor Cyan
        git status --short
        
        # Add all changes
        git add .
        if ($VoiceConfirmation) {
            Say-Text "Files staged for commit" -Voice "amy"
        }
        
        # Commit changes
        if ($CommitMessage) {
            git commit -m $CommitMessage
        } else {
            # Interactive commit message
            $message = Read-Host "Enter commit message"
            git commit -m $message
        }
        
        if ($LASTEXITCODE -eq 0) {
            if ($VoiceConfirmation) {
                Say-Text "Changes committed successfully" -Voice "amy"
                Send-AgentMessage -All -Text "📝 GIT COMMIT: $(git log -1 --pretty=format:'%s')"
            }
            
            # Push to remote if requested
            if ($PushToRemote) {
                git push origin $Branch
                if ($LASTEXITCODE -eq 0) {
                    if ($VoiceConfirmation) {
                        Say-Text "Changes pushed to remote repository" -Voice "amy"
                        Send-AgentMessage -All -Text "🚀 GIT PUSH: $Branch"
                    }
                }
            }
        }
        
    } catch {
        if ($VoiceConfirmation) {
            Say-Text "Git operation failed: $($_.Exception.Message)" -Voice "ryan"
            Send-AgentMessage -All -Text "❌ GIT ERROR: $($_.Exception.Message)"
        }
        Write-Error $_.Exception.Message
    }
}

# Usage
Invoke-GitWorkflow -CommitMessage "Add new feature" -PushToRemote
Invoke-GitWorkflow  # Interactive mode
```

## 🖥️ System Monitoring and Alerts

### Resource Monitor with Voice Alerts
```powershell
function Start-SystemMonitor {
    param(
        [int]$CPUThreshold = 80,
        [int]$MemoryThreshold = 85,
        [int]$DiskThreshold = 90,
        [int]$CheckInterval = 30,
        [string[]]$MonitoredProcesses = @("code", "devenv", "python", "dotnet"),
        [switch]$VoiceAlerts = $true
    )
    
    Write-Host "Starting system monitoring..." -ForegroundColor Green
    Write-Host "CPU Threshold: $CPUThreshold%" -ForegroundColor Cyan
    Write-Host "Memory Threshold: $MemoryThreshold%" -ForegroundColor Cyan
    Write-Host "Disk Threshold: $DiskThreshold%" -ForegroundColor Cyan
    Write-Host "Check Interval: $CheckInterval seconds" -ForegroundColor Cyan
    
    if ($VoiceAlerts) {
        Say-Text "System monitoring started" -Voice "amy"
        Send-AgentMessage -All -Text "🔍 MONITOR START: CPU<$CPUThreshold% MEM<$MemoryThreshold% DISK<$DiskThreshold%"
    }
    
    while ($true) {
        try {
            # CPU Usage
            $cpu = Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 3 |
                   Select-Object -ExpandProperty CounterSamples |
                   Measure-Object -Property CookedValue -Average |
                   Select-Object -ExpandProperty Average
            
            # Memory Usage  
            $memory = Get-Counter '\Memory\% Committed Bytes In Use' |
                     Select-Object -ExpandProperty CounterSamples |
                     Select-Object -ExpandProperty CookedValue
            
            # Disk Usage (C: drive)
            $disk = Get-WmiObject -Class Win32_LogicalDisk -Filter "DeviceID='C:'" |
                   ForEach-Object { [math]::Round(($_.Size - $_.FreeSpace) / $_.Size * 100, 1) }
            
            # Check thresholds
            $alerts = @()
            
            if ($cpu -gt $CPUThreshold) {
                $alerts += "CPU: $([math]::Round($cpu, 1))%"
                if ($VoiceAlerts) {
                    Say-Text "High CPU usage detected: $([math]::Round($cpu))%" -Voice "ryan"
                }
            }
            
            if ($memory -gt $MemoryThreshold) {
                $alerts += "Memory: $([math]::Round($memory, 1))%"
                if ($VoiceAlerts) {
                    Say-Text "High memory usage detected: $([math]::Round($memory))%" -Voice "kathleen"
                }
            }
            
            if ($disk -gt $DiskThreshold) {
                $alerts += "Disk C: $disk%"
                if ($VoiceAlerts) {
                    Say-Text "Disk space running low: $disk%" -Voice "ryan"
                }
            }
            
            # Check monitored processes
            foreach ($processName in $MonitoredProcesses) {
                $processes = Get-Process -Name $processName -ErrorAction SilentlyContinue
                if ($processes) {
                    $totalCPU = ($processes | Measure-Object CPU -Sum).Sum
                    $totalMemory = ($processes | Measure-Object WorkingSet -Sum).Sum / 1MB
                    
                    if ($totalMemory -gt 1000) {  # > 1GB
                        $alerts += "$processName: $([math]::Round($totalMemory))MB"
                    }
                }
            }
            
            # Send alerts if any
            if ($alerts) {
                $alertMessage = "⚠️ ALERT: " + ($alerts -join ", ")
                Send-AgentMessage -All -Text $alertMessage
                Write-Host "$(Get-Date -Format 'HH:mm:ss') - $alertMessage" -ForegroundColor Red
            } else {
                Write-Host "$(Get-Date -Format 'HH:mm:ss') - System OK: CPU $([math]::Round($cpu,1))% | MEM $([math]::Round($memory,1))% | DISK $disk%" -ForegroundColor Green
            }
            
            Start-Sleep -Seconds $CheckInterval
            
        } catch {
            Write-Host "Monitoring error: $($_.Exception.Message)" -ForegroundColor Red
            if ($VoiceAlerts) {
                Say-Text "System monitoring error occurred" -Voice "ryan"
            }
            Start-Sleep -Seconds 10
        }
    }
}

# Usage
Start-SystemMonitor -VoiceAlerts -CheckInterval 60
Start-SystemMonitor -CPUThreshold 70 -MemoryThreshold 80 -MonitoredProcesses @("python", "node", "code")
```

### Log File Monitor
```powershell
function Watch-LogFile {
    param(
        [Parameter(Mandatory=$true)][string]$LogPath,
        [string[]]$ErrorPatterns = @("ERROR", "FATAL", "EXCEPTION", "FAILED"),
        [string[]]$WarningPatterns = @("WARNING", "WARN"),
        [string[]]$SuccessPatterns = @("SUCCESS", "COMPLETED", "FINISHED"),
        [switch]$VoiceAlerts = $true
    )
    
    if (-not (Test-Path $LogPath)) {
        Write-Error "Log file not found: $LogPath"
        return
    }
    
    Write-Host "Monitoring log file: $LogPath" -ForegroundColor Green
    
    if ($VoiceAlerts) {
        Say-Text "Log monitoring started for $(Split-Path $LogPath -Leaf)" -Voice "amy"
    }
    
    # Get current file size to start monitoring from end
    $lastSize = (Get-Item $LogPath).Length
    
    while ($true) {
        try {
            $currentSize = (Get-Item $LogPath).Length
            
            if ($currentSize -gt $lastSize) {
                # Read new content
                $stream = [System.IO.File]::OpenRead($LogPath)
                $stream.Seek($lastSize, [System.IO.SeekOrigin]::Begin)
                $reader = New-Object System.IO.StreamReader($stream)
                $newContent = $reader.ReadToEnd()
                $reader.Close()
                $stream.Close()
                
                # Process new lines
                $newLines = $newContent -split "`n" | Where-Object { $_.Trim() }
                
                foreach ($line in $newLines) {
                    $timestamp = Get-Date -Format "HH:mm:ss"
                    
                    # Check for error patterns
                    $isError = $ErrorPatterns | Where-Object { $line -match $_ }
                    if ($isError) {
                        Write-Host "$timestamp [ERROR] $line" -ForegroundColor Red
                        if ($VoiceAlerts) {
                            Say-Text "Error detected in log file" -Voice "ryan"
                            Send-AgentMessage -All -Text "🚨 LOG ERROR: $line"
                        }
                        continue
                    }
                    
                    # Check for warning patterns
                    $isWarning = $WarningPatterns | Where-Object { $line -match $_ }
                    if ($isWarning) {
                        Write-Host "$timestamp [WARN] $line" -ForegroundColor Yellow
                        if ($VoiceAlerts) {
                            Send-AgentMessage -All -Text "⚠️ LOG WARNING: $line"
                        }
                        continue
                    }
                    
                    # Check for success patterns
                    $isSuccess = $SuccessPatterns | Where-Object { $line -match $_ }
                    if ($isSuccess) {
                        Write-Host "$timestamp [SUCCESS] $line" -ForegroundColor Green
                        if ($VoiceAlerts) {
                            Send-AgentMessage -All -Text "✅ LOG SUCCESS: $line"
                        }
                        continue
                    }
                    
                    # Regular info line
                    Write-Host "$timestamp [INFO] $line" -ForegroundColor White
                }
                
                $lastSize = $currentSize
            }
            
            Start-Sleep -Seconds 2
            
        } catch {
            Write-Host "Log monitoring error: $($_.Exception.Message)" -ForegroundColor Red
            Start-Sleep -Seconds 5
        }
    }
}

# Usage
Watch-LogFile -LogPath "C:\MyApp\logs\application.log" -VoiceAlerts
Watch-LogFile -LogPath "C:\inetpub\logs\LogFiles\W3SVC1\*.log" -ErrorPatterns @("500", "404", "ERROR")
```

## 🔧 Advanced Automation Scripts

### Automated Testing with Notifications
```powershell
function Invoke-TestSuite {
    param(
        [string]$TestProject,
        [string]$Configuration = "Release",
        [string[]]$TestCategories = @(),
        [int]$Timeout = 300,
        [switch]$VoiceNotifications = $true,
        [switch]$GenerateReport = $true
    )
    
    $startTime = Get-Date
    
    if ($VoiceNotifications) {
        Say-Text "Starting test suite execution" -Voice "amy"
        Send-AgentMessage -All -Text "🧪 TESTS START: $(Split-Path $TestProject -Leaf)"
    }
    
    try {
        # Build test project first
        Write-Host "Building test project..." -ForegroundColor Yellow
        dotnet build $TestProject --configuration $Configuration
        if ($LASTEXITCODE -ne 0) { throw "Test project build failed" }
        
        # Prepare test command
        $testCommand = @("test", $TestProject, "--configuration", $Configuration, "--no-build", "--verbosity", "normal")
        
        if ($TestCategories) {
            $filter = ($TestCategories | ForEach-Object { "Category=$_" }) -join "|"
            $testCommand += @("--filter", $filter)
        }
        
        if ($GenerateReport) {
            $reportPath = "TestResults\test-results-$(Get-Date -Format 'yyyyMMdd-HHmmss').trx"
            $testCommand += @("--logger", "trx;LogFileName=$reportPath")
        }
        
        # Run tests with timeout
        Write-Host "Running tests..." -ForegroundColor Yellow
        $job = Start-Job -ScriptBlock {
            param($command)
            & dotnet @command
        } -ArgumentList (,$testCommand)
        
        $completed = Wait-Job $job -Timeout $Timeout
        $testOutput = Receive-Job $job
        Remove-Job $job -Force
        
        if (-not $completed) {
            throw "Tests timed out after $Timeout seconds"
        }
        
        # Parse results
        $duration = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)
        $passed = ($testOutput | Select-String "Passed!.*?(\d+)").Matches.Groups[1].Value
        $failed = ($testOutput | Select-String "Failed!.*?(\d+)").Matches.Groups[1].Value
        $skipped = ($testOutput | Select-String "Skipped!.*?(\d+)").Matches.Groups[1].Value
        
        if ($failed -and $failed -ne "0") {
            if ($VoiceNotifications) {
                Say-Text "$failed tests failed out of $($passed + $failed)" -Voice "ryan"
                Send-AgentMessage -All -Text "❌ TESTS FAILED: $failed/$($passed + $failed) ($($duration)s)"
            }
            Write-Host "Tests failed: $failed failed, $passed passed" -ForegroundColor Red
            return $false
        } else {
            if ($VoiceNotifications) {
                Say-Text "All $passed tests passed successfully" -Voice "amy"
                Send-AgentMessage -All -Text "✅ TESTS PASSED: $passed/$passed ($($duration)s)"
            }
            Write-Host "All tests passed: $passed passed" -ForegroundColor Green
            return $true
        }
        
    } catch {
        $duration = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)
        
        if ($VoiceNotifications) {
            Say-Text "Test execution failed: $($_.Exception.Message)" -Voice "ryan"
            Send-AgentMessage -All -Text "💥 TEST ERROR: $($_.Exception.Message)"
        }
        
        Write-Host "Test execution failed: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# Usage
Invoke-TestSuite -TestProject ".\tests\MyApp.Tests.csproj" -VoiceNotifications
Invoke-TestSuite -TestProject ".\tests\Integration.Tests.csproj" -TestCategories @("Integration", "Smoke") -Timeout 600
```

### Database Backup with Notifications
```powershell
function Invoke-DatabaseBackup {
    param(
        [Parameter(Mandatory=$true)][string]$ServerInstance,
        [Parameter(Mandatory=$true)][string]$DatabaseName,
        [string]$BackupPath = "C:\Backups",
        [switch]$Compress = $true,
        [switch]$VoiceNotifications = $true
    )
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupFile = "$BackupPath\$DatabaseName`_$timestamp.bak"
    
    if (-not (Test-Path $BackupPath)) {
        New-Item -Path $BackupPath -ItemType Directory -Force
    }
    
    if ($VoiceNotifications) {
        Say-Text "Starting database backup for $DatabaseName" -Voice "amy"
        Send-AgentMessage -All -Text "💾 BACKUP START: $DatabaseName → $(Split-Path $backupFile -Leaf)"
    }
    
    try {
        $startTime = Get-Date
        
        # Build backup command
        $backupCommand = "BACKUP DATABASE [$DatabaseName] TO DISK = '$backupFile'"
        if ($Compress) {
            $backupCommand += " WITH COMPRESSION"
        }
        
        # Execute backup using Invoke-Sqlcmd
        Write-Host "Backing up database $DatabaseName..." -ForegroundColor Yellow
        Invoke-Sqlcmd -ServerInstance $ServerInstance -Query $backupCommand -QueryTimeout 3600
        
        # Verify backup file
        if (Test-Path $backupFile) {
            $fileSize = [math]::Round((Get-Item $backupFile).Length / 1MB, 2)
            $duration = [math]::Round(((Get-Date) - $startTime).TotalMinutes, 1)
            
            if ($VoiceNotifications) {
                Say-Text "Database backup completed successfully" -Voice "amy"
                Send-AgentMessage -All -Text "✅ BACKUP SUCCESS: $DatabaseName ($fileSize MB, $duration min)"
            }
            
            Write-Host "Backup completed: $backupFile ($fileSize MB)" -ForegroundColor Green
            return $backupFile
        } else {
            throw "Backup file was not created"
        }
        
    } catch {
        if ($VoiceNotifications) {
            Say-Text "Database backup failed: $($_.Exception.Message)" -Voice "ryan"
            Send-AgentMessage -All -Text "❌ BACKUP FAILED: $DatabaseName - $($_.Exception.Message)"
        }
        
        Write-Host "Backup failed: $($_.Exception.Message)" -ForegroundColor Red
        throw
    }
}

# Usage (requires SQL Server PowerShell module)
# Install-Module -Name SqlServer
# Invoke-DatabaseBackup -ServerInstance "localhost" -DatabaseName "MyApp" -VoiceNotifications
```

## 🌐 Web Development Integration

### IIS Management with Voice Feedback
```powershell
function Manage-IISSite {
    param(
        [Parameter(Mandatory=$true)][string]$SiteName,
        [ValidateSet("Start", "Stop", "Restart", "Deploy")][string]$Action,
        [string]$SourcePath,
        [switch]$VoiceNotifications = $true
    )
    
    Import-Module WebAdministration
    
    try {
        switch ($Action) {
            "Start" {
                Start-WebSite -Name $SiteName
                if ($VoiceNotifications) {
                    Say-Text "Website $SiteName started" -Voice "amy"
                    Send-AgentMessage -All -Text "🌐 SITE START: $SiteName"
                }
            }
            
            "Stop" {
                Stop-WebSite -Name $SiteName
                if ($VoiceNotifications) {
                    Say-Text "Website $SiteName stopped" -Voice "amy"
                    Send-AgentMessage -All -Text "🛑 SITE STOP: $SiteName"
                }
            }
            
            "Restart" {
                Stop-WebSite -Name $SiteName
                Start-Sleep -Seconds 2
                Start-WebSite -Name $SiteName
                if ($VoiceNotifications) {
                    Say-Text "Website $SiteName restarted" -Voice "amy"
                    Send-AgentMessage -All -Text "🔄 SITE RESTART: $SiteName"
                }
            }
            
            "Deploy" {
                if (-not $SourcePath) { throw "SourcePath is required for deployment" }
                
                # Stop site
                Stop-WebSite -Name $SiteName
                
                # Get site path
                $sitePath = (Get-WebSite -Name $SiteName).PhysicalPath
                
                # Backup current deployment
                $backupPath = "$sitePath`_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
                Copy-Item -Path $sitePath -Destination $backupPath -Recurse -Force
                
                # Deploy new version
                Remove-Item -Path "$sitePath\*" -Recurse -Force
                Copy-Item -Path "$SourcePath\*" -Destination $sitePath -Recurse -Force
                
                # Start site
                Start-WebSite -Name $SiteName
                
                if ($VoiceNotifications) {
                    Say-Text "Deployment completed for $SiteName" -Voice "amy"
                    Send-AgentMessage -All -Text "🚀 DEPLOY SUCCESS: $SiteName"
                }
            }
        }
        
        Write-Host "$Action completed for $SiteName" -ForegroundColor Green
        
    } catch {
        if ($VoiceNotifications) {
            Say-Text "IIS operation failed: $($_.Exception.Message)" -Voice "ryan"
            Send-AgentMessage -All -Text "❌ IIS ERROR: $SiteName - $($_.Exception.Message)"
        }
        throw
    }
}

# Usage
Manage-IISSite -SiteName "MyWebApp" -Action "Restart" -VoiceNotifications
Manage-IISSite -SiteName "MyWebApp" -Action "Deploy" -SourcePath "C:\Builds\MyWebApp\Release"
```

## 📝 Custom Notification Functions

### Smart Notification System
```powershell
function Send-SmartNotification {
    param(
        [Parameter(Mandatory=$true)][string]$Message,
        [ValidateSet("Info", "Success", "Warning", "Error", "Critical")][string]$Type = "Info",
        [string[]]$Recipients = @("All"),
        [switch]$VoiceAlert,
        [switch]$EmailAlert,
        [switch]$TeamsAlert,
        [hashtable]$Context = @{}
    )
    
    # Voice configuration by type
    $voiceMap = @{
        "Info" = "amy"
        "Success" = "amy" 
        "Warning" = "kathleen"
        "Error" = "ryan"
        "Critical" = "ryan"
    }
    
    # Emoji configuration by type
    $emojiMap = @{
        "Info" = "ℹ️"
        "Success" = "✅"
        "Warning" = "⚠️"
        "Error" = "❌" 
        "Critical" = "🚨"
    }
    
    $emoji = $emojiMap[$Type]
    $voice = $voiceMap[$Type]
    $formattedMessage = "$emoji $Type`.ToUpper(): $Message"
    
    # Add context information
    if ($Context.Count -gt 0) {
        $contextStr = ($Context.GetEnumerator() | ForEach-Object { "$($_.Key): $($_.Value)" }) -join " | "
        $formattedMessage += " [$contextStr]"
    }
    
    # Voice notification
    if ($VoiceAlert) {
        $voiceMessage = switch ($Type) {
            "Critical" { "Critical alert: $Message" }
            "Error" { "Error occurred: $Message" }
            "Warning" { "Warning: $Message" }
            default { $Message }
        }
        Say-Text $voiceMessage -Voice $voice
    }
    
    # Agent messaging
    if ($Recipients -contains "All") {
        Send-AgentMessage -All -Text $formattedMessage
    } else {
        foreach ($recipient in $Recipients) {
            Send-AgentMessage -Agent $recipient -Text $formattedMessage
        }
    }
    
    # Email alert (if configured)
    if ($EmailAlert -and $Type -in @("Error", "Critical")) {
        # Implement email sending logic here
        Write-Host "Email alert would be sent: $formattedMessage" -ForegroundColor Magenta
    }
    
    # Teams alert (if configured)  
    if ($TeamsAlert -and $Type -in @("Warning", "Error", "Critical")) {
        # Implement Teams webhook logic here
        Write-Host "Teams alert would be sent: $formattedMessage" -ForegroundColor Magenta
    }
    
    # Console output with colors
    $color = switch ($Type) {
        "Success" { "Green" }
        "Warning" { "Yellow" }
        "Error" { "Red" }
        "Critical" { "Magenta" }
        default { "White" }
    }
    
    Write-Host "$(Get-Date -Format 'HH:mm:ss') $formattedMessage" -ForegroundColor $color
}

# Usage examples
Send-SmartNotification -Message "Build completed successfully" -Type "Success" -VoiceAlert
Send-SmartNotification -Message "High CPU usage detected" -Type "Warning" -Context @{CPU="85%"; Process="devenv"}
Send-SmartNotification -Message "Database connection failed" -Type "Error" -VoiceAlert -EmailAlert
Send-SmartNotification -Message "System security breach detected" -Type "Critical" -VoiceAlert -EmailAlert -TeamsAlert
```

This comprehensive PowerShell examples guide provides advanced scripting patterns for Windows developers using the Slaygent Communication System. Each example includes proper error handling, voice notifications, and integration with common development workflows.