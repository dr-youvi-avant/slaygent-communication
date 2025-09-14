# PowerShell wrapper for cross-platform agent discovery tool
# Slaygent Communication System - Windows PowerShell support

param(
    [switch]$Fresh,
    [Alias("f")]
    [switch]$FreshShort,
    
    [switch]$Direct,
    [Alias("d")]
    [switch]$DirectShort,
    
    [switch]$Verbose,
    [Alias("v")]
    [switch]$VerboseShort,
    
    [ValidateSet("table", "json")]
    [string]$Format = "table",
    
    [switch]$Statistics,
    [switch]$Stats,
    
    [switch]$Status,
    [Alias("s")]
    [switch]$StatusShort,
    
    [string]$Host = "localhost",
    [int]$Port,
    
    [switch]$Quiet,
    [Alias("q")]
    [switch]$QuietShort,
    
    [switch]$Help
)

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$PythonScript = Join-Path $ScriptDir "search-agents.py"

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
else {
    # Add flags
    if ($Fresh -or $FreshShort) {
        $Args += "--fresh"
    }
    
    if ($Direct -or $DirectShort) {
        $Args += "--direct"
    }
    
    if ($Verbose -or $VerboseShort) {
        $Args += "--verbose"
    }
    
    if ($Statistics -or $Stats) {
        $Args += "--statistics"
    }
    
    if ($Status -or $StatusShort) {
        $Args += "--status"
    }
    
    if ($Quiet -or $QuietShort) {
        $Args += "--quiet"
    }
    
    # Add parameters with values
    if ($Format -ne "table") {
        $Args += "--format", $Format
    }
    
    if ($Host -ne "localhost") {
        $Args += "--host", $Host
    }
    
    if ($Port) {
        $Args += "--port", $Port.ToString()
    }
    
    # Show help if no specific action requested
    if (-not ($Fresh -or $FreshShort -or $Direct -or $DirectShort -or $Statistics -or $Stats -or $Status -or $StatusShort)) {
        # Default action - just search
    }
}

# Show help if requested or no args
if ($Help -or ($Args.Count -eq 0 -and -not ($Fresh -or $FreshShort -or $Direct -or $DirectShort -or $Statistics -or $Stats -or $Status -or $StatusShort))) {
    Write-Host "Slaygent Communication System - Agent Discovery Tool" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  search-agents                Discover agents using server"
    Write-Host "  search-agents -Fresh         Force fresh scan"
    Write-Host "  search-agents -Direct        Use direct discovery"
    Write-Host "  search-agents -Verbose       Show detailed information"
    Write-Host "  search-agents -Statistics    Show discovery statistics"
    Write-Host "  search-agents -Status        Show server status"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Format <table|json>         Output format"
    Write-Host "  -Host <hostname>             Discovery server host"
    Write-Host "  -Port <port>                 Discovery server port"
    Write-Host "  -Quiet                       Suppress output"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  search-agents"
    Write-Host "  search-agents -Verbose -Fresh"
    Write-Host "  search-agents -Format json"
    Write-Host "  search-agents -Statistics"
    Write-Host ""
    if (-not $Help) { exit 0 }
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