# PowerShell wrapper for cross-platform TTS tool
# Slaygent Communication System - Windows PowerShell support

param(
    [Parameter(Position = 0)]
    [string]$Text,
    
    [string]$Voice,
    [Alias("v")]
    [string]$VoiceShort,
    
    [double]$Speed = 1.0,
    [Alias("s")]
    [double]$SpeedShort = 1.0,
    
    [double]$Volume = 1.0,
    [string]$Host = "localhost",
    [int]$Port,
    
    [switch]$List,
    [Alias("l")]
    [switch]$ListShort,
    
    [switch]$Status,
    [switch]$Verbose,
    [switch]$Quiet,
    [Alias("q")]
    [switch]$QuietShort,
    
    [switch]$Help
)

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$PythonScript = Join-Path $ScriptDir "say.py"

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
elseif ($List -or $ListShort) {
    $Args += "--list"
}
elseif ($Status) {
    $Args += "--status"
}
elseif ($Text) {
    $Args += $Text
}
elseif (-not $List -and -not $ListShort -and -not $Status) {
    Write-Host "Slaygent Communication System - Cross-platform TTS Tool" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  say <text>                   Speak text using default voice"
    Write-Host "  say <text> -Voice <voice>    Speak with specific voice"
    Write-Host "  say -List                    List available voices"
    Write-Host "  say -Status                  Show TTS server status"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  say 'Hello from PowerShell'"
    Write-Host "  say 'System alert' -Voice danny -Speed 0.8"
    Write-Host "  say -List"
    Write-Host ""
    exit 0
}

# Add optional parameters
$VoiceParam = $Voice
if (-not $VoiceParam) { $VoiceParam = $VoiceShort }
if ($VoiceParam) {
    $Args += "--voice", $VoiceParam
}

$SpeedParam = $Speed
if ($SpeedShort -ne 1.0) { $SpeedParam = $SpeedShort }
if ($SpeedParam -ne 1.0) {
    $Args += "--speed", $SpeedParam.ToString()
}

if ($Volume -ne 1.0) {
    $Args += "--volume", $Volume.ToString()
}

if ($Host -ne "localhost") {
    $Args += "--host", $Host
}

if ($Port) {
    $Args += "--port", $Port.ToString()
}

if ($Verbose) {
    $Args += "--verbose"
}

if ($Quiet -or $QuietShort) {
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