# PowerShell test runner script for Slaygent Communication System
# Enhanced version with comprehensive coverage and Windows-specific features

param(
    [Parameter(Position=0)]
    [ValidateSet("all", "unit", "integration", "performance", "e2e", "stress")]
    [string]$TestType = "all",
    
    [switch]$InstallDeps,
    [switch]$Clean,
    [switch]$Coverage,
    [int]$Timeout = 300,
    [string]$PythonPath = "python",
    [int]$CoverageThreshold = 80,
    [switch]$Verbose,
    [switch]$Help
)

# Color output functions
function Write-Header {
    param([string]$Message)
    Write-Host "`n================================================" -ForegroundColor Blue
    Write-Host $Message -ForegroundColor Blue
    Write-Host "================================================`n" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Cyan
}

# Show help
if ($Help) {
    Write-Host "Slaygent Communication System - PowerShell Test Runner" -ForegroundColor Blue
    Write-Host ""
    Write-Host "SYNTAX"
    Write-Host "    .\run-tests.ps1 [-TestType <string>] [-InstallDeps] [-Clean] [-Coverage]"
    Write-Host "                    [-Timeout <int>] [-PythonPath <string>] [-Verbose] [-Help]"
    Write-Host ""
    Write-Host "PARAMETERS"
    Write-Host "    -TestType <string>"
    Write-Host "        Test type to run: all, unit, integration, performance, e2e, stress"
    Write-Host "        Default: all"
    Write-Host ""
    Write-Host "    -InstallDeps"
    Write-Host "        Install dependencies before running tests"
    Write-Host ""
    Write-Host "    -Clean"
    Write-Host "        Clean test artifacts before and after running"
    Write-Host ""
    Write-Host "    -Coverage"
    Write-Host "        Generate coverage report"
    Write-Host ""
    Write-Host "    -Timeout <int>"
    Write-Host "        Test timeout in seconds (default: 300)"
    Write-Host ""
    Write-Host "    -PythonPath <string>"
    Write-Host "        Python executable path (default: python)"
    Write-Host ""
    Write-Host "    -CoverageThreshold <int>"
    Write-Host "        Minimum coverage percentage required (default: 80)"
    Write-Host ""
    Write-Host "    -Verbose"
    Write-Host "        Enable verbose output"
    Write-Host ""
    Write-Host "    -Help"
    Write-Host "        Show this help message"
    Write-Host ""
    Write-Host "EXAMPLES"
    Write-Host "    .\run-tests.ps1 -TestType unit -Coverage"
    Write-Host "    .\run-tests.ps1 -TestType integration -InstallDeps"
    Write-Host "    .\run-tests.ps1 -TestType all -Clean -Coverage -Verbose"
    exit 0
}

# Error handling
$ErrorActionPreference = "Stop"
trap {
    Write-Error "An error occurred: $_"
    exit 1
}

# Check if running in virtual environment
function Test-VirtualEnvironment {
    Write-Header "Virtual Environment Check"
    
    if ($env:VIRTUAL_ENV) {
        Write-Success "Running in virtual environment: $env:VIRTUAL_ENV"
        return $true
    } elseif ($env:CONDA_DEFAULT_ENV) {
        Write-Success "Running in Conda environment: $env:CONDA_DEFAULT_ENV"
        return $true
    } else {
        Write-Warning "Not running in a virtual environment"
        Write-Info "Consider activating a virtual environment first"
        return $false
    }
}

# Install dependencies
function Install-Dependencies {
    Write-Header "Installing Dependencies"
    
    try {
        # Check if requirements files exist
        if (Test-Path "requirements.txt") {
            Write-Info "Installing main requirements..."
            & $PythonPath -m pip install -r requirements.txt
            if ($LASTEXITCODE -ne 0) { throw "Failed to install main requirements" }
        }
        
        if (Test-Path "requirements-dev.txt") {
            Write-Info "Installing development requirements..."
            & $PythonPath -m pip install -r requirements-dev.txt
            if ($LASTEXITCODE -ne 0) { throw "Failed to install dev requirements" }
        }
        
        # Install test dependencies
        Write-Info "Installing test dependencies..."
        $testDeps = @(
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-mock>=3.10.0",
            "pytest-benchmark>=4.0.0",
            "pytest-xdist>=3.0.0",
            "pytest-timeout>=2.1.0",
            "coverage[toml]>=7.0.0"
        )
        
        foreach ($dep in $testDeps) {
            & $PythonPath -m pip install $dep
            if ($LASTEXITCODE -ne 0) { throw "Failed to install $dep" }
        }
        
        Write-Success "Dependencies installed successfully"
    }
    catch {
        Write-Error "Failed to install dependencies: $_"
        throw
    }
}

# Detect environment
function Get-EnvironmentInfo {
    Write-Header "Environment Detection"
    
    $env_info = @{}
    
    # Operating System
    $os_info = Get-CimInstance Win32_OperatingSystem
    Write-Info "Operating System: $($os_info.Caption) ($($os_info.Version))"
    $env_info.OS = "windows"
    
    # PowerShell version
    Write-Info "PowerShell Version: $($PSVersionTable.PSVersion)"
    
    # Python version
    try {
        $python_version = & $PythonPath --version 2>&1
        Write-Info "Python Version: $python_version"
        $env_info.PythonVersion = $python_version
    }
    catch {
        Write-Error "Python not found or not accessible at: $PythonPath"
        throw "Python executable not found"
    }
    
    # Check for Redis
    $redis_available = $false
    try {
        $redis_service = Get-Service -Name "*redis*" -ErrorAction SilentlyContinue
        if ($redis_service) {
            Write-Success "Redis service found: $($redis_service.Name)"
            $redis_available = $true
        } else {
            # Check for Redis executable
            $redis_exe = Get-Command redis-server -ErrorAction SilentlyContinue
            if ($redis_exe) {
                Write-Success "Redis executable found at: $($redis_exe.Source)"
                $redis_available = $true
            }
        }
    }
    catch { }
    
    if (-not $redis_available) {
        Write-Warning "Redis not found - some integration tests may be skipped"
    }
    $env_info.RedisAvailable = $redis_available
    
    # Check for audio libraries
    $audio_available = $false
    try {
        & $PythonPath -c "import sounddevice" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "sounddevice library is available"
            $audio_available = $true
        }
    }
    catch { }
    
    if (-not $audio_available) {
        Write-Warning "sounddevice not available - audio tests may be skipped"
    }
    $env_info.AudioAvailable = $audio_available
    
    # Windows Terminal check
    if (Get-Command wt -ErrorAction SilentlyContinue) {
        Write-Success "Windows Terminal is available"
        $env_info.WindowsTerminal = $true
    } else {
        Write-Info "Windows Terminal not found"
        $env_info.WindowsTerminal = $false
    }
    
    return $env_info
}

# Build test arguments based on environment
function Get-TestArgs {
    param(
        [hashtable]$EnvInfo,
        [string]$BaseMarkers = ""
    )
    
    $args = @()
    
    # Add base markers
    if ($BaseMarkers) {
        $args += "-m"
        $args += $BaseMarkers
    }
    
    # Platform-specific markers
    $markers = @("not unix_only")
    
    # Dependency-specific markers
    if (-not $EnvInfo.RedisAvailable) {
        $markers += "not requires_redis"
    }
    
    if (-not $EnvInfo.AudioAvailable) {
        $markers += "not requires_audio"
    }
    
    # Always exclude tmux tests on Windows
    $markers += "not requires_tmux"
    
    # Combine markers
    if ($markers.Count -gt 0) {
        if ($BaseMarkers) {
            $combined_markers = "$BaseMarkers and (" + ($markers -join " and ") + ")"
        } else {
            $combined_markers = $markers -join " and "
        }
        $args = @("-m", $combined_markers)
    }
    
    # Add other standard arguments
    $args += @("-v", "--tb=short", "--timeout=$Timeout")
    
    if ($Verbose) {
        $args += "-s"
    }
    
    return $args
}

# Run unit tests
function Invoke-UnitTests {
    param([hashtable]$EnvInfo)
    
    Write-Header "Running Unit Tests"
    
    $args = Get-TestArgs -EnvInfo $EnvInfo
    $args = @("tests/unit") + $args
    
    Write-Info "Test command: $PythonPath -m pytest $($args -join ' ')"
    
    try {
        & $PythonPath -m pytest @args
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Unit tests passed"
            return $true
        } else {
            Write-Error "Unit tests failed"
            return $false
        }
    }
    catch {
        Write-Error "Unit test execution failed: $_"
        return $false
    }
}

# Run integration tests
function Invoke-IntegrationTests {
    param([hashtable]$EnvInfo)
    
    Write-Header "Running Integration Tests"
    
    $args = Get-TestArgs -EnvInfo $EnvInfo -BaseMarkers "not slow"
    $args = @("tests/integration") + $args
    
    Write-Info "Test command: $PythonPath -m pytest $($args -join ' ')"
    
    try {
        & $PythonPath -m pytest @args
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Integration tests passed"
            return $true
        } else {
            Write-Error "Integration tests failed"
            return $false
        }
    }
    catch {
        Write-Error "Integration test execution failed: $_"
        return $false
    }
}

# Run performance tests
function Invoke-PerformanceTests {
    param([hashtable]$EnvInfo)
    
    Write-Header "Running Performance Tests"
    
    $args = @("tests/", "-v", "-m", "performance", "--benchmark-only", "--timeout=$Timeout")
    
    Write-Info "Test command: $PythonPath -m pytest $($args -join ' ')"
    
    try {
        & $PythonPath -m pytest @args
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Performance tests completed"
            return $true
        } else {
            Write-Error "Performance tests failed"
            return $false
        }
    }
    catch {
        Write-Error "Performance test execution failed: $_"
        return $false
    }
}

# Run end-to-end tests
function Invoke-E2ETests {
    param([hashtable]$EnvInfo)
    
    Write-Header "Running End-to-End Tests"
    
    $args = @("tests/integration/test_end_to_end.py", "-v", "--tb=short", "--timeout=$Timeout")
    
    Write-Info "Test command: $PythonPath -m pytest $($args -join ' ')"
    
    try {
        & $PythonPath -m pytest @args
        if ($LASTEXITCODE -eq 0) {
            Write-Success "End-to-end tests passed"
            return $true
        } else {
            Write-Error "End-to-end tests failed"
            return $false
        }
    }
    catch {
        Write-Error "End-to-end test execution failed: $_"
        return $false
    }
}

# Run stress tests
function Invoke-StressTests {
    param([hashtable]$EnvInfo)
    
    Write-Header "Running Stress Tests"
    
    $stress_timeout = $Timeout * 2
    $args = @("tests/", "-v", "-m", "stress", "--timeout=$stress_timeout")
    
    Write-Info "Test command: $PythonPath -m pytest $($args -join ' ')"
    
    try {
        & $PythonPath -m pytest @args
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Stress tests completed"
            return $true
        } else {
            Write-Error "Stress tests failed"
            return $false
        }
    }
    catch {
        Write-Error "Stress test execution failed: $_"
        return $false
    }
}

# Generate coverage report
function Invoke-Coverage {
    Write-Header "Generating Coverage Report"
    
    try {
        Write-Info "Running tests with coverage..."
        $args = @("tests/", "--cov=src", "--cov-report=term-missing", "--cov-report=html", "--cov-report=xml")
        
        & $PythonPath -m pytest @args
        if ($LASTEXITCODE -ne 0) {
            throw "Coverage test execution failed"
        }
        
        Write-Success "Coverage report generated"
        
        # Check coverage threshold
        try {
            $coverage_output = & $PythonPath -m coverage report 2>&1
            $total_line = $coverage_output | Where-Object { $_ -match "TOTAL" }
            if ($total_line) {
                $coverage_match = [regex]::Match($total_line, "(\d+)%")
                if ($coverage_match.Success) {
                    $coverage_percent = [int]$coverage_match.Groups[1].Value
                    Write-Info "Total coverage: ${coverage_percent}%"
                    
                    if ($coverage_percent -ge $CoverageThreshold) {
                        Write-Success "Coverage meets threshold of ${CoverageThreshold}%"
                    } else {
                        Write-Error "Coverage ${coverage_percent}% is below threshold of ${CoverageThreshold}%"
                        return $false
                    }
                }
            }
        }
        catch {
            Write-Warning "Could not parse coverage percentage: $_"
        }
        
        return $true
    }
    catch {
        Write-Error "Coverage analysis failed: $_"
        return $false
    }
}

# Clean test artifacts
function Clear-TestArtifacts {
    Write-Header "Cleaning Test Artifacts"
    
    try {
        # Remove coverage files
        Remove-Item -Path ".coverage" -Force -ErrorAction SilentlyContinue
        Remove-Item -Path "htmlcov" -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -Path "coverage.xml" -Force -ErrorAction SilentlyContinue
        
        # Remove pytest cache
        Remove-Item -Path ".pytest_cache" -Recurse -Force -ErrorAction SilentlyContinue
        
        # Remove Python cache
        Get-ChildItem -Path . -Recurse -Name "__pycache__" -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Get-ChildItem -Path . -Recurse -Name "*.pyc" -Force | Remove-Item -Force -ErrorAction SilentlyContinue
        
        # Remove temporary test files
        Get-ChildItem -Path . -Name "test_temp_*" -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        
        # Remove Windows-specific temp files
        $temp_path = $env:TEMP
        Get-ChildItem -Path $temp_path -Name "slaygent_test_*" -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        
        Write-Success "Test artifacts cleaned"
    }
    catch {
        Write-Warning "Some artifacts could not be cleaned: $_"
    }
}

# Validate test environment
function Test-Environment {
    Write-Header "Validating Test Environment"
    
    try {
        # Check if source directory exists
        if (-not (Test-Path "src")) {
            Write-Error "Source directory 'src' not found"
            return $false
        }
        
        # Check if tests directory exists
        if (-not (Test-Path "tests")) {
            Write-Error "Tests directory not found"
            return $false
        }
        
        # Check if key modules can be imported
        & $PythonPath -c "import sys; sys.path.insert(0, 'src'); import src.utils.os_utils" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Cannot import core modules - check PYTHONPATH and dependencies"
            return $false
        }
        
        Write-Success "Test environment validation passed"
        return $true
    }
    catch {
        Write-Error "Environment validation failed: $_"
        return $false
    }
}

# Main execution
function Main {
    Write-Header "Slaygent Communication System - PowerShell Test Runner"
    
    # Initial setup
    Test-VirtualEnvironment
    $env_info = Get-EnvironmentInfo
    
    if ($InstallDeps) {
        Install-Dependencies
    }
    
    if (-not (Test-Environment)) {
        exit 1
    }
    
    if ($Clean) {
        Clear-TestArtifacts
    }
    
    # Run tests based on type
    $test_success = $true
    
    switch ($TestType) {
        "unit" {
            $test_success = Invoke-UnitTests -EnvInfo $env_info
        }
        "integration" {
            $test_success = Invoke-IntegrationTests -EnvInfo $env_info
        }
        "performance" {
            $test_success = Invoke-PerformanceTests -EnvInfo $env_info
        }
        "e2e" {
            $test_success = Invoke-E2ETests -EnvInfo $env_info
        }
        "stress" {
            $test_success = Invoke-StressTests -EnvInfo $env_info
        }
        "all" {
            $test_success = (Invoke-UnitTests -EnvInfo $env_info) -and
                          (Invoke-IntegrationTests -EnvInfo $env_info) -and
                          (Invoke-E2ETests -EnvInfo $env_info)
        }
        default {
            Write-Error "Unknown test type: $TestType"
            Write-Info "Valid types: all, unit, integration, performance, e2e, stress"
            exit 1
        }
    }
    
    # Generate coverage if requested and tests passed
    if ($Coverage -and $test_success) {
        $test_success = Invoke-Coverage
    }
    
    # Final cleanup
    if ($Clean) {
        Clear-TestArtifacts
    }
    
    # Summary
    Write-Header "Test Summary"
    if ($test_success) {
        Write-Success "All tests completed successfully!"
        
        if ($Coverage) {
            Write-Info "Coverage report available in htmlcov\index.html"
        }
    } else {
        Write-Error "Some tests failed!"
        exit 1
    }
}

# Execute main function
Main