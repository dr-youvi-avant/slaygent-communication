#!/usr/bin/env python3
"""
Slaygent Communication System - Installation Validation Script
Validates that the installation is working correctly across all platforms
"""

import sys
import os
import asyncio
import json
import time
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class ValidationError(Exception):
    """Custom exception for validation failures"""
    pass

class InstallationValidator:
    """Validates Slaygent installation across platforms"""
    
    def __init__(self, install_path: Optional[str] = None, quiet: bool = False):
        self.install_path = Path(install_path) if install_path else Path.cwd()
        self.quiet = quiet
        self.results: List[Dict[str, Any]] = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log message with level"""
        if not self.quiet:
            colors = {
                "INFO": "\033[0;36m",  # Cyan
                "SUCCESS": "\033[0;32m",  # Green
                "WARNING": "\033[1;33m",  # Yellow
                "ERROR": "\033[0;31m",  # Red
                "DEBUG": "\033[0;35m"  # Purple
            }
            reset = "\033[0m"
            icon = {
                "INFO": "ℹ️",
                "SUCCESS": "✅",
                "WARNING": "⚠️",
                "ERROR": "❌",
                "DEBUG": "🔍"
            }
            print(f"{colors.get(level, '')}{icon.get(level, '')} {message}{reset}")
    
    def run_test(self, test_name: str, test_func, *args, **kwargs) -> Dict[str, Any]:
        """Run a single validation test"""
        self.log(f"Testing {test_name}...")
        start_time = time.time()
        
        result = {
            "name": test_name,
            "success": False,
            "duration": 0,
            "message": "",
            "details": {}
        }
        
        try:
            details = test_func(*args, **kwargs)
            result["success"] = True
            result["message"] = f"{test_name} passed"
            result["details"] = details if isinstance(details, dict) else {}
            self.log(f"{test_name} - PASSED", "SUCCESS")
            
        except Exception as e:
            result["message"] = str(e)
            self.log(f"{test_name} - FAILED: {e}", "ERROR")
            
        result["duration"] = time.time() - start_time
        self.results.append(result)
        return result
    
    def test_python_environment(self) -> Dict[str, Any]:
        """Test Python installation and version"""
        import sys
        version = sys.version_info
        
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            raise ValidationError(f"Python 3.8+ required, found {version.major}.{version.minor}")
            
        return {
            "python_version": f"{version.major}.{version.minor}.{version.micro}",
            "executable": sys.executable,
            "platform": sys.platform
        }
    
    def test_core_dependencies(self) -> Dict[str, Any]:
        """Test that core Python dependencies are available"""
        dependencies = [
            "fastapi",
            "uvicorn", 
            "piper",
            "redis",
            "psutil",
            "sounddevice",
            "numpy"
        ]
        
        available = {}
        missing = []
        
        for dep in dependencies:
            try:
                __import__(dep)
                available[dep] = True
            except ImportError:
                available[dep] = False
                missing.append(dep)
        
        if missing:
            raise ValidationError(f"Missing dependencies: {', '.join(missing)}")
            
        return {"available": available, "total": len(dependencies)}
    
    def test_project_structure(self) -> Dict[str, Any]:
        """Test that project files and directories exist"""
        required_files = [
            "requirements.txt",
            "config.yaml",
            "src/servers/tts_server.py",
            "src/servers/agent_discovery.py",
            "src/messaging/manager.py",
            "src/audio/manager.py",
            "bin/msg.py",
            "bin/say.py",
            "bin/search-agents.py"
        ]
        
        required_dirs = [
            "src",
            "src/servers",
            "src/messaging", 
            "src/audio",
            "src/utils",
            "src/config",
            "bin",
            "docs"
        ]
        
        missing_files = []
        missing_dirs = []
        
        for file_path in required_files:
            if not (self.install_path / file_path).exists():
                missing_files.append(file_path)
        
        for dir_path in required_dirs:
            if not (self.install_path / dir_path).is_dir():
                missing_dirs.append(dir_path)
        
        if missing_files or missing_dirs:
            errors = []
            if missing_files:
                errors.append(f"Missing files: {', '.join(missing_files)}")
            if missing_dirs:
                errors.append(f"Missing directories: {', '.join(missing_dirs)}")
            raise ValidationError("; ".join(errors))
        
        return {
            "files_checked": len(required_files),
            "dirs_checked": len(required_dirs),
            "install_path": str(self.install_path)
        }
    
    def test_voice_models(self) -> Dict[str, Any]:
        """Test that voice models are available"""
        voices_dir = self.install_path / "voices"
        
        if not voices_dir.exists():
            raise ValidationError("Voices directory not found")
        
        voices = {}
        for voice_dir in voices_dir.iterdir():
            if voice_dir.is_dir():
                model_file = voice_dir / "model.onnx"
                config_file = voice_dir / "config.json"
                
                voices[voice_dir.name] = {
                    "model_exists": model_file.exists(),
                    "config_exists": config_file.exists(),
                    "complete": model_file.exists() and config_file.exists()
                }
        
        complete_voices = [name for name, data in voices.items() if data["complete"]]
        
        if not complete_voices:
            raise ValidationError("No complete voice models found")
        
        return {
            "voices_found": len(voices),
            "complete_voices": complete_voices,
            "voice_details": voices
        }
    
    def test_configuration(self) -> Dict[str, Any]:
        """Test configuration files and loading"""
        config_files = [".env", "config.yaml"]
        found_configs = []
        
        for config_file in config_files:
            config_path = self.install_path / config_file
            if config_path.exists():
                found_configs.append(config_file)
        
        # Test loading configuration
        try:
            from src.config.manager import ConfigManager
            config = ConfigManager.load_config(str(self.install_path))
            config_loaded = True
        except Exception as e:
            config_loaded = False
            if not found_configs:
                raise ValidationError(f"No configuration files found and config loading failed: {e}")
        
        return {
            "config_files_found": found_configs,
            "config_loadable": config_loaded,
            "install_path": str(self.install_path)
        }
    
    async def test_tts_server(self) -> Dict[str, Any]:
        """Test TTS server startup and basic functionality"""
        # Start TTS server
        tts_process = None
        try:
            tts_script = self.install_path / "src" / "servers" / "tts_server.py"
            tts_process = subprocess.Popen([
                sys.executable, str(tts_script)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for server to start
            await asyncio.sleep(3)
            
            # Test health endpoint
            try:
                with urllib.request.urlopen("http://localhost:9003/health", timeout=5) as response:
                    health_data = json.loads(response.read().decode())
                    
                # Test voices endpoint
                with urllib.request.urlopen("http://localhost:9003/voices", timeout=5) as response:
                    voices_data = json.loads(response.read().decode())
                    
                return {
                    "server_started": True,
                    "health_check": health_data,
                    "voices_available": len(voices_data.get("voices", [])),
                    "port": 9003
                }
                
            except urllib.error.URLError as e:
                raise ValidationError(f"TTS server not responding: {e}")
                
        finally:
            if tts_process:
                tts_process.terminate()
                try:
                    tts_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    tts_process.kill()
    
    async def test_discovery_server(self) -> Dict[str, Any]:
        """Test discovery server startup and basic functionality"""
        # Start discovery server
        discovery_process = None
        try:
            discovery_script = self.install_path / "src" / "servers" / "agent_discovery.py"
            discovery_process = subprocess.Popen([
                sys.executable, str(discovery_script)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for server to start
            await asyncio.sleep(3)
            
            # Test health endpoint
            try:
                with urllib.request.urlopen("http://localhost:9005/health", timeout=5) as response:
                    health_data = json.loads(response.read().decode())
                    
                # Test agents endpoint
                with urllib.request.urlopen("http://localhost:9005/agents", timeout=5) as response:
                    agents_data = json.loads(response.read().decode())
                    
                return {
                    "server_started": True,
                    "health_check": health_data,
                    "agents_found": len(agents_data.get("agents", {})),
                    "port": 9005
                }
                
            except urllib.error.URLError as e:
                raise ValidationError(f"Discovery server not responding: {e}")
                
        finally:
            if discovery_process:
                discovery_process.terminate()
                try:
                    discovery_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    discovery_process.kill()
    
    def test_cli_tools(self) -> Dict[str, Any]:
        """Test CLI tools functionality"""
        cli_tools = ["msg.py", "say.py", "search-agents.py"]
        tool_results = {}
        
        for tool in cli_tools:
            tool_path = self.install_path / "bin" / tool
            
            if not tool_path.exists():
                tool_results[tool] = {"exists": False, "executable": False}
                continue
            
            # Test if tool is executable and shows help
            try:
                result = subprocess.run([
                    sys.executable, str(tool_path), "--help"
                ], capture_output=True, text=True, timeout=10)
                
                tool_results[tool] = {
                    "exists": True,
                    "executable": result.returncode == 0,
                    "help_available": "--help" in result.stdout or "usage:" in result.stdout.lower()
                }
            except Exception as e:
                tool_results[tool] = {
                    "exists": True,
                    "executable": False,
                    "error": str(e)
                }
        
        # Check if any tools failed
        failed_tools = [tool for tool, data in tool_results.items() 
                       if not data.get("executable", False)]
        
        if failed_tools:
            raise ValidationError(f"CLI tools not working: {', '.join(failed_tools)}")
        
        return {"tools": tool_results, "total_tools": len(cli_tools)}
    
    def test_audio_system(self) -> Dict[str, Any]:
        """Test audio system availability"""
        audio_info = {
            "audio_backend": "none",
            "devices_available": 0,
            "error": None
        }
        
        try:
            # Test sounddevice
            import sounddevice as sd
            devices = sd.query_devices()
            audio_info["audio_backend"] = "sounddevice"
            audio_info["devices_available"] = len(devices)
            
        except Exception as e:
            audio_info["error"] = str(e)
            
            # Try alternative audio detection
            try:
                import subprocess
                if sys.platform.startswith("linux"):
                    result = subprocess.run(["pactl", "info"], capture_output=True, text=True)
                    if result.returncode == 0:
                        audio_info["audio_backend"] = "pulseaudio"
                elif sys.platform == "darwin":
                    # macOS has built-in audio
                    audio_info["audio_backend"] = "coreaudio"
                elif sys.platform.startswith("win"):
                    # Windows has built-in audio
                    audio_info["audio_backend"] = "directsound"
                    
            except Exception:
                pass
        
        return audio_info
    
    def test_redis_connection(self) -> Dict[str, Any]:
        """Test Redis connection (optional)"""
        redis_info = {
            "redis_available": False,
            "connection_successful": False,
            "version": None,
            "fallback_mode": True
        }
        
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            
            # Test connection
            r.ping()
            redis_info["redis_available"] = True
            redis_info["connection_successful"] = True
            redis_info["fallback_mode"] = False
            
            # Get version
            info = r.info()
            redis_info["version"] = info.get("redis_version", "unknown")
            
        except Exception as e:
            redis_info["error"] = str(e)
        
        return redis_info
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all validation tests"""
        self.log("🚀 Starting Slaygent installation validation...", "INFO")
        
        # Synchronous tests
        sync_tests = [
            ("Python Environment", self.test_python_environment),
            ("Core Dependencies", self.test_core_dependencies), 
            ("Project Structure", self.test_project_structure),
            ("Voice Models", self.test_voice_models),
            ("Configuration", self.test_configuration),
            ("CLI Tools", self.test_cli_tools),
            ("Audio System", self.test_audio_system),
            ("Redis Connection", self.test_redis_connection)
        ]
        
        for test_name, test_func in sync_tests:
            self.run_test(test_name, test_func)
        
        # Asynchronous tests
        async_tests = [
            ("TTS Server", self.test_tts_server),
            ("Discovery Server", self.test_discovery_server)
        ]
        
        for test_name, test_func in async_tests:
            try:
                self.log(f"Testing {test_name}...")
                start_time = time.time()
                
                details = await test_func()
                
                result = {
                    "name": test_name,
                    "success": True,
                    "duration": time.time() - start_time,
                    "message": f"{test_name} passed",
                    "details": details
                }
                self.results.append(result)
                self.log(f"{test_name} - PASSED", "SUCCESS")
                
            except Exception as e:
                result = {
                    "name": test_name,
                    "success": False,
                    "duration": time.time() - start_time,
                    "message": str(e),
                    "details": {}
                }
                self.results.append(result)
                self.log(f"{test_name} - FAILED: {e}", "ERROR")
        
        # Calculate summary
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r["success"])
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        summary = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "success_rate": success_rate,
            "overall_success": success_rate >= 80,  # 80% threshold for success
            "results": self.results
        }
        
        # Log summary
        self.log("", "INFO")  # Empty line
        self.log("📊 Validation Summary:", "INFO")
        self.log(f"   Total Tests: {total_tests}", "INFO")
        self.log(f"   Passed: {passed_tests}", "SUCCESS" if passed_tests > 0 else "INFO")
        self.log(f"   Failed: {total_tests - passed_tests}", "ERROR" if total_tests - passed_tests > 0 else "INFO")
        self.log(f"   Success Rate: {success_rate:.1f}%", "SUCCESS" if success_rate >= 80 else "WARNING")
        
        if summary["overall_success"]:
            self.log("🎉 Installation validation PASSED!", "SUCCESS")
        else:
            self.log("❌ Installation validation FAILED!", "ERROR")
            self.log("Please check the failed tests above and reinstall if necessary.", "WARNING")
        
        return summary

def main():
    """Main function to run validation"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate Slaygent installation")
    parser.add_argument("--install-path", help="Installation path to validate")
    parser.add_argument("--quiet", action="store_true", help="Suppress output except results")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    
    args = parser.parse_args()
    
    validator = InstallationValidator(args.install_path, args.quiet)
    
    try:
        # Run validation
        summary = asyncio.run(validator.run_all_tests())
        
        if args.json:
            print(json.dumps(summary, indent=2))
        
        # Exit with appropriate code
        sys.exit(0 if summary["overall_success"] else 1)
        
    except KeyboardInterrupt:
        validator.log("Validation interrupted by user", "WARNING")
        sys.exit(2)
    except Exception as e:
        validator.log(f"Validation failed with error: {e}", "ERROR")
        sys.exit(3)

if __name__ == "__main__":
    main()