#!/usr/bin/env python3
"""
Enhanced Cross-Platform TTS Server for Slaygent Communication System
Supports Windows, Linux, and macOS with automatic audio backend selection
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
import uvicorn

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel

from ..config.manager import get_config, SlaygentConfig
from ..audio.manager import get_audio_manager, AudioManager
from ..utils.os_utils import get_os_detector

logger = logging.getLogger(__name__)


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    speed: Optional[float] = 1.0
    volume: Optional[float] = 1.0


class VoiceManager:
    """Manages Piper voice models with auto-download capability"""
    
    def __init__(self, config: SlaygentConfig):
        self.config = config
        self.voices = {}
        self.voice_dir = Path(config.voice.voice_dir)
        self.voice_dir.mkdir(parents=True, exist_ok=True)
    
    async def load_voices(self) -> bool:
        """Load available voice models"""
        try:
            from piper import PiperVoice
        except ImportError:
            logger.error("Piper TTS not installed! Please run: pip install piper-tts")
            return False
        
        voice_models = self.config.voice.models
        loaded_count = 0
        
        for name, filename in voice_models.items():
            voice_file = self.voice_dir / filename
            
            if voice_file.exists():
                try:
                    logger.info(f"Loading {name} voice model...")
                    self.voices[name] = PiperVoice.load(str(voice_file))
                    loaded_count += 1
                    logger.info(f"✓ {name} loaded successfully!")
                except Exception as e:
                    logger.error(f"Failed to load {name}: {e}")
            else:
                logger.warning(f"Voice model not found: {voice_file}")
                if self.config.voice.auto_download:
                    logger.info(f"Auto-downloading {name}...")
                    if await self._download_voice(name, filename):
                        try:
                            self.voices[name] = PiperVoice.load(str(voice_file))
                            loaded_count += 1
                            logger.info(f"✓ {name} downloaded and loaded!")
                        except Exception as e:
                            logger.error(f"Failed to load downloaded {name}: {e}")
        
        if loaded_count == 0:
            logger.error("No voice models loaded! Please install at least one voice model.")
            return False
        
        logger.info(f"✓ Loaded {loaded_count} voice(s): {', '.join(self.voices.keys())}")
        return True
    
    async def _download_voice(self, name: str, filename: str) -> bool:
        """Download voice model (placeholder - would implement actual download)"""
        # This is a placeholder - in a real implementation, you would:
        # 1. Download the .onnx file from Piper repository
        # 2. Download the corresponding .json config file
        # 3. Verify checksums
        
        logger.warning(f"Auto-download not implemented for {name}")
        logger.info(f"Please manually download {filename} to {self.voice_dir}")
        return False
    
    async def synthesize(self, text: str, voice: str = None, speed: float = 1.0) -> np.ndarray:
        """Synthesize speech from text"""
        voice_name = voice or self.config.voice.default_voice
        
        if voice_name not in self.voices:
            available = list(self.voices.keys())
            raise ValueError(f"Voice '{voice_name}' not available. Available: {available}")
        
        try:
            piper_voice = self.voices[voice_name]
            
            # Synthesize audio
            audio_generator = piper_voice.synthesize(text, length_scale=1.0/speed)
            
            # Collect audio data
            audio_chunks = []
            for chunk in audio_generator:
                audio_chunks.append(chunk)
            
            if not audio_chunks:
                raise RuntimeError("No audio generated")
            
            # Concatenate chunks
            audio_data = np.concatenate(audio_chunks)
            return audio_data
            
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            raise RuntimeError(f"Speech synthesis failed: {e}")
    
    def get_available_voices(self) -> Dict[str, Dict[str, Any]]:
        """Get information about available voices"""
        voice_info = {}
        
        for name, voice in self.voices.items():
            try:
                voice_info[name] = {
                    "name": name,
                    "language": getattr(voice.config, 'language', 'en'),
                    "quality": getattr(voice.config, 'quality', 'medium'),
                    "sample_rate": getattr(voice.config, 'sample_rate', 22050),
                    "loaded": True
                }
            except Exception as e:
                voice_info[name] = {
                    "name": name,
                    "error": str(e),
                    "loaded": False
                }
        
        return voice_info


class TTSServer:
    """Enhanced TTS Server with cross-platform audio support"""
    
    def __init__(self):
        self.config = get_config()
        self.audio_manager: Optional[AudioManager] = None
        self.voice_manager: Optional[VoiceManager] = None
        self.os_detector = get_os_detector()
    
    async def initialize(self) -> bool:
        """Initialize TTS server components"""
        try:
            # Initialize audio system
            self.audio_manager = await get_audio_manager()
            
            if not self.audio_manager.is_initialized:
                logger.warning("Audio system not initialized - TTS will work but no sound output")
            else:
                logger.info(f"Audio system ready with {self.audio_manager.get_backend_name()} backend")
            
            # Initialize voice manager
            self.voice_manager = VoiceManager(self.config)
            if not await self.voice_manager.load_voices():
                logger.error("Failed to load voice models")
                return False
            
            logger.info("TTS Server initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"TTS Server initialization failed: {e}")
            return False
    
    async def speak(self, text: str, voice: str = None, speed: float = 1.0, volume: float = 1.0) -> bool:
        """Synthesize and play speech"""
        if not self.voice_manager:
            raise RuntimeError("Voice manager not initialized")
        
        try:
            # Generate speech audio
            audio_data = await self.voice_manager.synthesize(text, voice, speed)
            
            # Set volume
            if self.audio_manager:
                await self.audio_manager.set_volume(volume)
                
                # Play audio
                sample_rate = self.config.audio.sample_rate
                return await self.audio_manager.play_audio(audio_data, sample_rate)
            else:
                logger.warning("No audio manager - speech generated but not played")
                return True
                
        except Exception as e:
            logger.error(f"Speech synthesis/playback failed: {e}")
            raise
    
    async def generate_audio_file(self, text: str, voice: str = None, speed: float = 1.0) -> str:
        """Generate audio file and return path"""
        if not self.voice_manager:
            raise RuntimeError("Voice manager not initialized")
        
        try:
            # Generate speech audio
            audio_data = await self.voice_manager.synthesize(text, voice, speed)
            
            # Create temporary audio file
            import soundfile as sf
            
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_path = temp_file.name
            temp_file.close()
            
            # Write audio to file
            sample_rate = self.config.audio.sample_rate
            sf.write(temp_path, audio_data, sample_rate)
            
            return temp_path
            
        except ImportError:
            raise RuntimeError("soundfile not available for audio file generation")
        except Exception as e:
            logger.error(f"Audio file generation failed: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Get TTS server health status"""
        health = {
            "service": "TTS Server",
            "status": "unknown",
            "os": self.os_detector.os_type.value
        }
        
        try:
            # Check voice manager
            if self.voice_manager:
                voices = self.voice_manager.get_available_voices()
                health["voices"] = {
                    "loaded": len([v for v in voices.values() if v.get("loaded", False)]),
                    "total": len(voices),
                    "available": list(voices.keys()),
                    "default": self.config.voice.default_voice
                }
            else:
                health["voices"] = {"error": "Voice manager not initialized"}
            
            # Check audio manager
            if self.audio_manager:
                audio_health = await self.audio_manager.health_check()
                health["audio"] = audio_health
            else:
                health["audio"] = {"error": "Audio manager not initialized"}
            
            # Overall status
            voices_ok = health.get("voices", {}).get("loaded", 0) > 0
            audio_ok = health.get("audio", {}).get("initialized", False)
            
            if voices_ok and audio_ok:
                health["status"] = "healthy"
            elif voices_ok:
                health["status"] = "voice_only"  # Can generate but not play
            else:
                health["status"] = "unhealthy"
                
        except Exception as e:
            health["status"] = "error"
            health["error"] = str(e)
        
        return health


# Global TTS server instance
tts_server: Optional[TTSServer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan management"""
    global tts_server
    
    # Startup
    logger.info("Starting TTS Server...")
    tts_server = TTSServer()
    
    if not await tts_server.initialize():
        logger.error("Failed to initialize TTS Server")
        raise RuntimeError("TTS Server initialization failed")
    
    logger.info("TTS Server ready")
    
    yield
    
    # Shutdown
    logger.info("Shutting down TTS Server...")
    tts_server = None


# Create FastAPI app
app = FastAPI(
    title="Slaygent Communication System - TTS Server",
    description="Cross-platform Text-to-Speech API with Redis messaging integration",
    version="2.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check and service information"""
    if not tts_server:
        raise HTTPException(status_code=503, detail="TTS Server not ready")
    
    health = await tts_server.health_check()
    
    return {
        "service": "Slaygent Communication System - TTS Server",
        "version": "2.0.0",
        "status": health.get("status", "unknown"),
        "platform": health.get("os", "unknown"),
        "endpoints": {
            "speak": "/speak - Synthesize and play text",
            "play": "/play - Alias for /speak",
            "generate": "/generate - Generate audio file",
            "voices": "/voices - List available voices",
            "health": "/health - Detailed health check"
        },
        "voices_loaded": health.get("voices", {}).get("loaded", 0),
        "audio_backend": health.get("audio", {}).get("backend", "unknown")
    }


@app.post("/speak")
async def speak_text(request: TTSRequest):
    """Synthesize and play text as speech"""
    if not tts_server:
        raise HTTPException(status_code=503, detail="TTS Server not ready")
    
    try:
        success = await tts_server.speak(
            text=request.text,
            voice=request.voice,
            speed=request.speed,
            volume=request.volume
        )
        
        return {
            "success": success,
            "message": "Speech synthesis completed",
            "text": request.text[:100] + "..." if len(request.text) > 100 else request.text,
            "voice": request.voice or tts_server.config.voice.default_voice
        }
        
    except Exception as e:
        logger.error(f"Speech synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Speech synthesis failed: {e}")


@app.get("/play")
async def play_text(
    text: str = Query(..., description="Text to synthesize"),
    voice: Optional[str] = Query(None, description="Voice name"),
    speed: float = Query(1.0, description="Speech speed multiplier"),
    volume: float = Query(1.0, description="Volume (0.0-1.0)")
):
    """Synthesize and play text (GET endpoint for easy CLI access)"""
    request = TTSRequest(text=text, voice=voice, speed=speed, volume=volume)
    return await speak_text(request)


@app.post("/generate")
async def generate_audio(request: TTSRequest):
    """Generate audio file from text"""
    if not tts_server:
        raise HTTPException(status_code=503, detail="TTS Server not ready")
    
    try:
        audio_file_path = await tts_server.generate_audio_file(
            text=request.text,
            voice=request.voice,
            speed=request.speed
        )
        
        return FileResponse(
            path=audio_file_path,
            media_type="audio/wav",
            filename=f"tts_output.wav"
        )
        
    except Exception as e:
        logger.error(f"Audio generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Audio generation failed: {e}")


@app.get("/voices")
async def list_voices():
    """List available voice models"""
    if not tts_server or not tts_server.voice_manager:
        raise HTTPException(status_code=503, detail="Voice manager not ready")
    
    try:
        voices = tts_server.voice_manager.get_available_voices()
        
        return {
            "voices": voices,
            "default": tts_server.config.voice.default_voice,
            "total": len(voices),
            "loaded": len([v for v in voices.values() if v.get("loaded", False)])
        }
        
    except Exception as e:
        logger.error(f"Failed to list voices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list voices: {e}")


@app.get("/health")
async def health_check():
    """Detailed health check"""
    if not tts_server:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": "TTS Server not initialized"}
        )
    
    try:
        health = await tts_server.health_check()
        
        status_code = 200
        if health.get("status") == "unhealthy":
            status_code = 503
        elif health.get("status") == "voice_only":
            status_code = 206  # Partial Content
        
        return JSONResponse(status_code=status_code, content=health)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


def main():
    """Run TTS server"""
    config = get_config()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO if not config.debug else logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run server
    uvicorn.run(
        "src.servers.tts_server:app",
        host=config.tts_server.host,
        port=config.tts_server.port,
        workers=config.tts_server.workers,
        log_level="info" if not config.debug else "debug"
    )


if __name__ == "__main__":
    main()