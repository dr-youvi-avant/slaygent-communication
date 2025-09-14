# PowerShell wrapper for cross-platform messaging tool
# Slaygent Communication System - Windows PowerShell support

param(
    [Parameter(Position = 0)]
    [string]$Recipient,
    
    [Parameter(Position = 1)]
    [string]$Message,
    
    [string]$All,
    [string]$Broadcast,
    [switch]$List,
    [switch]$Status,
    [string]$Sender,
    [switch]$Verbose,
    [switch]$Quiet,
    [switch]$Help
)

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$PythonScript = Join-Path $ScriptDir "msg.py"

# Check if Python script exists
if (-not (Test-Path $PythonScript)) {
    Write-Error "Python script not found: $PythonScript"
    exit 1
}

# Build command arguments
$Args = @()

if ($Help) {
    $Args += "--help"
}
elseif ($List) {
    $Args += "--list"
}
elseif ($Status) {
    $Args += "--status"
}
elseif ($All) {
    $Args += "--all", $All
}
elseif ($Broadcast) {
    $Args += "--broadcast", $Broadcast
}
elseif ($Recipient -and $Message) {
    $Args += $Recipient, $Message
}
elseif (-not $List -and -not $Status) {
    Write-Host "Slaygent Communication System - Cross-platform Messaging Tool" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  msg <recipient> <message>     Send message to specific agent"
    Write-Host "  msg -All <message>           Broadcast to all agents"
    Write-Host "  msg -List                    List available agents"
    Write-Host "  msg -Status                  Show messaging status"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  msg claude 'Hello from PowerShell'"
    Write-Host "  msg -All 'System alert: Build complete'"
    Write-Host "  msg -List"
    Write-Host ""
    exit 0
}

# Add optional parameters
if ($Sender) {
    $Args += "--sender", $Sender
}

if ($Verbose) {
    $Args += "--verbose"
}

if ($Quiet) {
    $Args += "--quiet"
}

# Try different Python executables
$PythonExes = @("python", "python3", "py")
$PythonFound = $false

foreach ($PythonExe in $PythonExes) {
    try {
        # Test if Python executable works
        $null = & $PythonExe --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            # Run the Python script
            if ($Args.Count -gt 0) {
                & $PythonExe $PythonScript @Args
            } else {
                & $PythonExe $PythonScript
            }
            $ExitCode = $LASTEXITCODE
            $PythonFound = $true
            break
        }
    }
    catch {
        continue
    }
}

if (-not $PythonFound) {
    Write-Error "Python not found. Please install Python 3.8+ and ensure it's in your PATH."
    Write-Host "You can download Python from: https://www.python.org/downloads/"
    exit 1
}

exit $ExitCode