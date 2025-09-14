#!/bin/bash
# Enhanced test runner script with comprehensive coverage
# Supports different test types and platforms

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PYTHON_VERSION=${PYTHON_VERSION:-"python3"}
TEST_TIMEOUT=${TEST_TIMEOUT:-300}  # 5 minutes default timeout
COVERAGE_THRESHOLD=${COVERAGE_THRESHOLD:-80}

# Helper functions
print_header() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if running in virtual environment
check_venv() {
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        print_warning "Not running in a virtual environment"
        print_info "Consider activating a virtual environment first"
    else
        print_success "Running in virtual environment: $VIRTUAL_ENV"
    fi
}

# Install dependencies if needed
install_deps() {
    print_header "Installing Dependencies"
    
    # Check if requirements files exist
    if [[ -f "requirements.txt" ]]; then
        print_info "Installing main requirements..."
        pip install -r requirements.txt
    fi
    
    if [[ -f "requirements-dev.txt" ]]; then
        print_info "Installing development requirements..."
        pip install -r requirements-dev.txt
    fi
    
    # Install test dependencies
    print_info "Installing test dependencies..."
    pip install pytest pytest-asyncio pytest-mock pytest-benchmark pytest-xdist pytest-timeout coverage
}

# Detect operating system and environment
detect_environment() {
    print_header "Environment Detection"
    
    # Detect OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        print_info "Operating System: Linux"
        
        # Check for specific Linux distributions
        if command -v apt-get &> /dev/null; then
            print_info "Package Manager: apt (Debian/Ubuntu)"
        elif command -v yum &> /dev/null; then
            print_info "Package Manager: yum (RedHat/CentOS)"
        elif command -v pacman &> /dev/null; then
            print_info "Package Manager: pacman (Arch)"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        print_info "Operating System: macOS"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        OS="windows"
        print_info "Operating System: Windows (Git Bash/Cygwin)"
    else
        OS="unknown"
        print_warning "Unknown operating system: $OSTYPE"
    fi
    
    # Check Python version
    PYTHON_VER=$($PYTHON_VERSION --version 2>&1)
    print_info "Python Version: $PYTHON_VER"
    
    # Check for Redis
    if command -v redis-server &> /dev/null || command -v redis-cli &> /dev/null; then
        print_success "Redis is available"
        REDIS_AVAILABLE=true
    else
        print_warning "Redis not found - some integration tests may be skipped"
        REDIS_AVAILABLE=false
    fi
    
    # Check for tmux
    if command -v tmux &> /dev/null; then
        print_success "tmux is available"
        TMUX_AVAILABLE=true
    else
        print_warning "tmux not found - Unix-specific tests may be skipped"
        TMUX_AVAILABLE=false
    fi
    
    # Check for audio libraries
    if $PYTHON_VERSION -c "import sounddevice" &> /dev/null; then
        print_success "sounddevice library is available"
        AUDIO_AVAILABLE=true
    else
        print_warning "sounddevice not available - audio tests may be skipped"
        AUDIO_AVAILABLE=false
    fi
}

# Run unit tests
run_unit_tests() {
    print_header "Running Unit Tests"
    
    local extra_args=""
    
    # Add platform-specific markers
    case $OS in
        windows)
            extra_args="$extra_args -m 'not unix_only'"
            ;;
        linux|macos)
            extra_args="$extra_args -m 'not windows_only'"
            ;;
    esac
    
    # Add dependency-specific markers
    if [[ "$REDIS_AVAILABLE" == "false" ]]; then
        extra_args="$extra_args and not requires_redis"
    fi
    
    if [[ "$AUDIO_AVAILABLE" == "false" ]]; then
        extra_args="$extra_args and not requires_audio"
    fi
    
    if [[ "$TMUX_AVAILABLE" == "false" ]]; then
        extra_args="$extra_args and not requires_tmux"
    fi
    
    print_info "Running unit tests with args: $extra_args"
    
    if $PYTHON_VERSION -m pytest tests/unit -v --tb=short --timeout=$TEST_TIMEOUT $extra_args; then
        print_success "Unit tests passed"
        return 0
    else
        print_error "Unit tests failed"
        return 1
    fi
}

# Run integration tests
run_integration_tests() {
    print_header "Running Integration Tests"
    
    local extra_args="-m 'not slow'"
    
    # Add platform-specific markers
    case $OS in
        windows)
            extra_args="$extra_args and not unix_only"
            ;;
        linux|macos)
            extra_args="$extra_args and not windows_only"
            ;;
    esac
    
    # Add dependency-specific markers
    if [[ "$REDIS_AVAILABLE" == "false" ]]; then
        extra_args="$extra_args and not requires_redis"
    fi
    
    if [[ "$AUDIO_AVAILABLE" == "false" ]]; then
        extra_args="$extra_args and not requires_audio"
    fi
    
    print_info "Running integration tests with args: $extra_args"
    
    if $PYTHON_VERSION -m pytest tests/integration -v --tb=short --timeout=$TEST_TIMEOUT $extra_args; then
        print_success "Integration tests passed"
        return 0
    else
        print_error "Integration tests failed"
        return 1
    fi
}

# Run performance tests
run_performance_tests() {
    print_header "Running Performance Tests"
    
    if $PYTHON_VERSION -m pytest tests/ -v -m "performance" --benchmark-only --timeout=$TEST_TIMEOUT; then
        print_success "Performance tests completed"
        return 0
    else
        print_error "Performance tests failed"
        return 1
    fi
}

# Run end-to-end tests
run_e2e_tests() {
    print_header "Running End-to-End Tests"
    
    if $PYTHON_VERSION -m pytest tests/integration/test_end_to_end.py -v --tb=short --timeout=$TEST_TIMEOUT; then
        print_success "End-to-end tests passed"
        return 0
    else
        print_error "End-to-end tests failed"
        return 1
    fi
}

# Run stress tests
run_stress_tests() {
    print_header "Running Stress Tests"
    
    if $PYTHON_VERSION -m pytest tests/ -v -m "stress" --timeout=$((TEST_TIMEOUT * 2)); then
        print_success "Stress tests completed"
        return 0
    else
        print_error "Stress tests failed"
        return 1
    fi
}

# Generate coverage report
run_coverage() {
    print_header "Generating Coverage Report"
    
    print_info "Running tests with coverage..."
    if $PYTHON_VERSION -m pytest tests/ --cov=src --cov-report=term-missing --cov-report=html --cov-report=xml; then
        print_success "Coverage report generated"
        
        # Check coverage threshold
        coverage_percent=$($PYTHON_VERSION -m coverage report | grep TOTAL | awk '{print $4}' | sed 's/%//')
        if [[ -n "$coverage_percent" ]]; then
            print_info "Total coverage: ${coverage_percent}%"
            
            if (( $(echo "$coverage_percent >= $COVERAGE_THRESHOLD" | bc -l) )); then
                print_success "Coverage meets threshold of ${COVERAGE_THRESHOLD}%"
            else
                print_error "Coverage ${coverage_percent}% is below threshold of ${COVERAGE_THRESHOLD}%"
                return 1
            fi
        fi
        
        return 0
    else
        print_error "Coverage analysis failed"
        return 1
    fi
}

# Clean test artifacts
clean_artifacts() {
    print_header "Cleaning Test Artifacts"
    
    # Remove coverage files
    rm -f .coverage
    rm -rf htmlcov/
    rm -f coverage.xml
    
    # Remove pytest cache
    rm -rf .pytest_cache/
    
    # Remove Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    
    # Remove temporary test files
    rm -rf test_temp_*
    rm -rf /tmp/slaygent_test_* 2>/dev/null || true
    
    print_success "Test artifacts cleaned"
}

# Validate test environment
validate_environment() {
    print_header "Validating Test Environment"
    
    # Check if source directory exists
    if [[ ! -d "src" ]]; then
        print_error "Source directory 'src' not found"
        return 1
    fi
    
    # Check if tests directory exists
    if [[ ! -d "tests" ]]; then
        print_error "Tests directory not found"
        return 1
    fi
    
    # Check if key modules can be imported
    if ! $PYTHON_VERSION -c "import sys; sys.path.insert(0, 'src'); import src.utils.os_utils" &> /dev/null; then
        print_error "Cannot import core modules - check PYTHONPATH and dependencies"
        return 1
    fi
    
    print_success "Test environment validation passed"
    return 0
}

# Main execution function
main() {
    local test_type="all"
    local install_deps_flag=false
    local clean_flag=false
    local coverage_flag=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --type=*)
                test_type="${1#*=}"
                shift
                ;;
            --install-deps)
                install_deps_flag=true
                shift
                ;;
            --clean)
                clean_flag=true
                shift
                ;;
            --coverage)
                coverage_flag=true
                shift
                ;;
            --timeout=*)
                TEST_TIMEOUT="${1#*=}"
                shift
                ;;
            --python=*)
                PYTHON_VERSION="${1#*=}"
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --type=TYPE          Test type: all, unit, integration, performance, e2e, stress"
                echo "  --install-deps       Install dependencies before running tests"
                echo "  --clean             Clean test artifacts before and after running"
                echo "  --coverage          Generate coverage report"
                echo "  --timeout=SECONDS   Test timeout in seconds (default: 300)"
                echo "  --python=PYTHON     Python executable to use (default: python3)"
                echo "  --help, -h          Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0 --type=unit --coverage"
                echo "  $0 --type=integration --install-deps"
                echo "  $0 --type=all --clean --coverage"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                print_info "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    print_header "Slaygent Communication System - Test Runner"
    
    # Initial setup
    check_venv
    detect_environment
    
    if [[ "$install_deps_flag" == "true" ]]; then
        install_deps
    fi
    
    if ! validate_environment; then
        exit 1
    fi
    
    if [[ "$clean_flag" == "true" ]]; then
        clean_artifacts
    fi
    
    # Run tests based on type
    local test_results=0
    
    case $test_type in
        unit)
            run_unit_tests || test_results=1
            ;;
        integration)
            run_integration_tests || test_results=1
            ;;
        performance)
            run_performance_tests || test_results=1
            ;;
        e2e)
            run_e2e_tests || test_results=1
            ;;
        stress)
            run_stress_tests || test_results=1
            ;;
        all)
            run_unit_tests || test_results=1
            run_integration_tests || test_results=1
            run_e2e_tests || test_results=1
            ;;
        *)
            print_error "Unknown test type: $test_type"
            print_info "Valid types: all, unit, integration, performance, e2e, stress"
            exit 1
            ;;
    esac
    
    # Generate coverage if requested
    if [[ "$coverage_flag" == "true" && "$test_results" == "0" ]]; then
        run_coverage || test_results=1
    fi
    
    # Final cleanup
    if [[ "$clean_flag" == "true" ]]; then
        clean_artifacts
    fi
    
    # Summary
    print_header "Test Summary"
    if [[ "$test_results" == "0" ]]; then
        print_success "All tests completed successfully!"
        
        if [[ "$coverage_flag" == "true" ]]; then
            print_info "Coverage report available in htmlcov/index.html"
        fi
    else
        print_error "Some tests failed!"
        exit 1
    fi
}

# Run main function with all arguments
main "$@"