#!/usr/bin/env python3
"""
Cross-platform TTS (say) tool for Slaygent Communication System
Supports multiple audio backends on Windows, Linux, and macOS
"""

import sys
import argparse
import asyncio
import logging
import requests
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.manager import get_config
from src.utils.os_utils import get_os_detector


def make_tts_request(text: str, voice: Optional[str] = None, speed: float = 1.0, 
                    volume: float = 1.0, host: str = "localhost", port: int = 9003) -> bool:
    """Make HTTP request to TTS server"""
    try:
        url = f"http://{host}:{port}/speak"
        
        data = {
            "text": text,
            "speed": speed,
            "volume": volume
        }
        
        if voice:
            data["voice"] = voice
        
        response = requests.post(url, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            return result.get("success", False)
        else:
            try:
                error_info = response.json()
                print(f"✗ TTS Error: {error_info.get('detail', 'Unknown error')}")
            except:
                print(f"✗ TTS Error: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to TTS server at {host}:{port}")
        print("  Make sure the TTS server is running:")
        print(f"    python -m src.servers.tts_server")
        return False
    except requests.exceptions.Timeout:
        print("✗ TTS request timed out")
        return False
    except Exception as e:
        print(f"✗ TTS Error: {e}")
        return False


def get_available_voices(host: str = "localhost", port: int = 9003) -> dict:
    """Get available voices from TTS server"""
    try:
        url = f"http://{host}:{port}/voices"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}"}
            
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to TTS server"}
    except Exception as e:
        return {"error": str(e)}


def check_tts_server(host: str = "localhost", port: int = 9003) -> dict:
    """Check TTS server status"""
    try:
        url = f"http://{host}:{port}/health"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "error", "code": response.status_code}
            
    except requests.exceptions.ConnectionError:
        return {"status": "not_running", "error": "Connection refused"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def list_voices(host: str = "localhost", port: int = 9003):
    """List available voices"""
    voices_info = get_available_voices(host, port)
    
    if "error" in voices_info:
        print(f"✗ Error getting voices: {voices_info['error']}")
        return
    
    voices = voices_info.get("voices", {})
    default_voice = voices_info.get("default", "unknown")
    
    if not voices:
        print("No voices available")
        return
    
    print("Available voices:")
    for name, info in voices.items():
        if info.get("loaded", False):
            status = "✓"
            lang = info.get("language", "unknown")
            quality = info.get("quality", "unknown")
            default_marker = " (default)" if name == default_voice else ""
            print(f"  {status} {name:<12} {lang:<8} {quality:<8}{default_marker}")
        else:
            error = info.get("error", "not loaded")
            print(f"  ✗ {name:<12} {error}")
    
    loaded_count = sum(1 for v in voices.values() if v.get("loaded", False))
    print(f"\\nTotal: {len(voices)} voices, {loaded_count} loaded")


def show_status(host: str = "localhost", port: int = 9003):
    """Show TTS server status"""
    health = check_tts_server(host, port)
    
    print(f"TTS Server Status ({host}:{port})")
    print(f"Platform: {get_os_detector().os_type.value}")
    
    if health.get("status") == "not_running":
        print("Status: ✗ Not running")
        print("\\nTo start TTS server:")
        print("  python -m src.servers.tts_server")
        return
    
    status = health.get("status", "unknown")
    if status == "healthy":
        print("Status: ✓ Healthy")
    elif status == "voice_only":
        print("Status: ⚠ Voice synthesis only (no audio output)")
    else:
        print(f"Status: ✗ {status}")
    
    # Audio backend info
    audio_info = health.get("audio", {})
    if audio_info:
        backend = audio_info.get("backend", "unknown")
        initialized = audio_info.get("initialized", False)
        print(f"Audio Backend: {backend} {'✓' if initialized else '✗'}")
    
    # Voice info
    voice_info = health.get("voices", {})
    if voice_info:
        loaded = voice_info.get("loaded", 0)
        total = voice_info.get("total", 0)
        default = voice_info.get("default", "unknown")
        print(f"Voices: {loaded}/{total} loaded (default: {default})")
    
    # Show any errors
    if "error" in health:
        print(f"Error: {health['error']}")


async def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="Slaygent Communication System - Cross-platform TTS Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "Hello world"
  %(prog)s "System alert" --voice danny --speed 0.8
  %(prog)s --list
  %(prog)s --status
        """
    )
    
    # Text argument
    parser.add_argument(
        "text",
        nargs="?",
        help="Text to synthesize and speak"
    )
    
    # Voice options
    parser.add_argument(
        "--voice", "-v",
        help="Voice name to use"
    )
    
    parser.add_argument(
        "--speed", "-s",
        type=float,
        default=1.0,
        help="Speech speed multiplier (default: 1.0)"
    )
    
    parser.add_argument(
        "--volume",
        type=float,
        default=1.0,
        help="Volume level 0.0-1.0 (default: 1.0)"
    )
    
    # Server options
    parser.add_argument(
        "--host",
        default="localhost",
        help="TTS server host (default: localhost)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="TTS server port (default from config)"
    )
    
    # Information commands
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available voices"
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show TTS server status"
    )
    
    # Output options
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Quiet mode"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    elif args.quiet:
        logging.basicConfig(level=logging.ERROR)
    else:
        logging.basicConfig(level=logging.WARNING)
    
    # Get configuration
    try:
        config = get_config()
        port = args.port or config.tts_server.port
    except Exception as e:
        if not args.quiet:
            print(f"Configuration error: {e}")
        port = args.port or 9003
    
    try:
        # Handle information commands
        if args.list:
            list_voices(args.host, port)
            return 0
        
        if args.status:
            show_status(args.host, port)
            return 0
        
        # Validate arguments for synthesis
        if not args.text:
            if not args.quiet:
                print("Error: Text to speak is required")
                print("Use --help for usage information")
            return 1
        
        if not (0.1 <= args.speed <= 3.0):
            if not args.quiet:
                print("Error: Speed must be between 0.1 and 3.0")
            return 1
        
        if not (0.0 <= args.volume <= 1.0):
            if not args.quiet:
                print("Error: Volume must be between 0.0 and 1.0")
            return 1
        
        # Perform TTS
        if not args.quiet:
            voice_info = f" (voice: {args.voice})" if args.voice else ""
            print(f"Speaking{voice_info}...")
        
        success = make_tts_request(
            text=args.text,
            voice=args.voice,
            speed=args.speed,
            volume=args.volume,
            host=args.host,
            port=port
        )
        
        if success and not args.quiet:
            print("✓ Speech completed")
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        if not args.quiet:
            print("\\nOperation cancelled")
        return 130
    except Exception as e:
        if not args.quiet:
            print(f"✗ Error: {e}")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.exit(130)