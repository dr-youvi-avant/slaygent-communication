#!/usr/bin/env python3
"""
Fallback messaging backend for when Redis is unavailable
Uses file-based messaging and named pipes for cross-platform compatibility
"""

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
import uuid
import threading
import time

from .base import MessageBackend, Message, ConnectionError, MessageDeliveryError
from ..config.manager import SlaygentConfig
from ..utils.os_utils import get_os_detector, get_config_directory

logger = logging.getLogger(__name__)


class FallbackMessageBackend(MessageBackend):
    """File-based messaging fallback for when Redis is unavailable"""
    
    def __init__(self, config: SlaygentConfig):
        self.config = config
        self.os_detector = get_os_detector()
        self.is_connected = False
        self.message_dir: Optional[Path] = None
        self.subscriptions: Dict[str, Callable] = {}
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
    
    async def connect(self) -> bool:
        """Initialize file-based messaging"""
        try:
            # Create message directory
            if self.os_detector.is_windows:
                # Use temp directory on Windows
                base_dir = Path(tempfile.gettempdir()) / "slaygent_messages"
            else:
                # Use /tmp on Unix systems
                base_dir = Path("/tmp/slaygent_messages")
            
            self.message_dir = base_dir
            self.message_dir.mkdir(parents=True, exist_ok=True)
            
            # Create subdirectories
            (self.message_dir / "queues").mkdir(exist_ok=True)
            (self.message_dir / "history").mkdir(exist_ok=True)
            
            self.is_connected = True
            logger.info(f"Fallback messaging initialized at {self.message_dir}")
            
            # Start file monitoring
            self._start_file_monitoring()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize fallback messaging: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Cleanup file-based messaging"""
        self.is_connected = False
        self.subscriptions.clear()
        
        # Stop monitoring thread
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._stop_monitoring.set()
            self._monitor_thread.join(timeout=5)
        
        logger.info("Fallback messaging disconnected")
    
    def _get_queue_file(self, agent_name: str) -> Path:
        """Get queue file path for agent"""
        return self.message_dir / "queues" / f"{agent_name}.queue"
    
    def _get_history_file(self, agent_name: str) -> Path:
        """Get history file path for agent"""
        return self.message_dir / "history" / f"{agent_name}.history"
    
    async def send_message(self, message: Message) -> bool:
        """Send message via file queue"""
        if not self.is_connected:
            raise ConnectionError("Fallback messaging not connected")
        
        try:
            queue_file = self._get_queue_file(message.recipient)
            history_file = self._get_history_file(message.recipient)
            
            # Serialize message
            message_data = json.dumps(message.to_dict()) + "\\n"
            
            # Write to queue file (append mode with locking)
            with open(queue_file, "a", encoding="utf-8") as f:
                # Simple file locking for cross-platform compatibility
                try:
                    if self.os_detector.is_windows:
                        import msvcrt
                        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    
                    f.write(message_data)
                    f.flush()
                    
                finally:
                    if self.os_detector.is_windows:
                        import msvcrt
                        try:
                            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                        except:
                            pass
                    else:
                        import fcntl
                        try:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        except:
                            pass
            
            # Also write to history
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(message_data)
            
            # Trim history file if it gets too large
            await self._trim_history_file(history_file)
            
            logger.debug(f"Message sent to {message.recipient} via file queue")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message via fallback: {e}")
            raise MessageDeliveryError(f"Fallback delivery failed: {e}")
    
    async def _trim_history_file(self, history_file: Path, max_lines: int = 1000):
        """Keep history file size manageable"""
        try:
            if not history_file.exists():
                return
            
            with open(history_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            if len(lines) > max_lines:
                # Keep only the last max_lines
                with open(history_file, "w", encoding="utf-8") as f:
                    f.writelines(lines[-max_lines:])
        
        except Exception as e:
            logger.debug(f"Error trimming history file: {e}")
    
    async def broadcast_message(self, message: Message, recipients: List[str] = None) -> int:
        """Broadcast message to multiple recipients"""
        if not recipients:
            # Find all known agents from queue files
            queue_dir = self.message_dir / "queues"
            recipients = [f.stem for f in queue_dir.glob("*.queue")]
        
        sent_count = 0
        for recipient in recipients:
            try:
                broadcast_msg = Message(
                    id=str(uuid.uuid4()),
                    sender=message.sender,
                    recipient=recipient,
                    content=message.content,
                    timestamp=message.timestamp,
                    metadata={**message.metadata, "broadcast": True}
                )
                if await self.send_message(broadcast_msg):
                    sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send broadcast to {recipient}: {e}")
        
        return sent_count
    
    async def subscribe_to_messages(self, agent_name: str, callback: Callable[[Message], None]):
        """Subscribe to messages for an agent"""
        if not self.is_connected:
            raise ConnectionError("Fallback messaging not connected")
        
        self.subscriptions[agent_name] = callback
        
        # Ensure queue file exists
        queue_file = self._get_queue_file(agent_name)
        queue_file.touch()
        
        logger.info(f"Subscribed to messages for {agent_name} (fallback mode)")
    
    async def unsubscribe_from_messages(self, agent_name: str):
        """Unsubscribe from messages"""
        if agent_name in self.subscriptions:
            del self.subscriptions[agent_name]
        logger.info(f"Unsubscribed from messages for {agent_name}")
    
    def _start_file_monitoring(self):
        """Start background thread to monitor message files"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        
        self._stop_monitoring.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_message_files,
            daemon=True
        )
        self._monitor_thread.start()
    
    def _monitor_message_files(self):
        """Monitor message files for new messages"""
        last_positions = {}
        
        while not self._stop_monitoring.is_set():
            try:
                for agent_name, callback in list(self.subscriptions.items()):
                    queue_file = self._get_queue_file(agent_name)
                    
                    if not queue_file.exists():
                        continue
                    
                    # Check if file has new content
                    try:
                        current_size = queue_file.stat().st_size
                        last_position = last_positions.get(str(queue_file), 0)
                        
                        if current_size > last_position:
                            # Read new messages
                            with open(queue_file, "r", encoding="utf-8") as f:
                                f.seek(last_position)
                                new_lines = f.readlines()
                                last_positions[str(queue_file)] = f.tell()
                            
                            # Process new messages
                            for line in new_lines:
                                line = line.strip()
                                if not line:
                                    continue
                                
                                try:
                                    message_data = json.loads(line)
                                    message = Message.from_dict(message_data)
                                    
                                    # Call callback
                                    callback(message)
                                    
                                except Exception as e:
                                    logger.error(f"Error processing message: {e}")
                    
                    except Exception as e:
                        logger.debug(f"Error monitoring {queue_file}: {e}")
                
                # Sleep briefly before next check
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error in file monitoring: {e}")
                time.sleep(1)
    
    async def get_message_history(self, agent_name: str, limit: int = 100) -> List[Message]:
        """Get message history from file"""
        if not self.is_connected:
            raise ConnectionError("Fallback messaging not connected")
        
        history_file = self._get_history_file(agent_name)
        if not history_file.exists():
            return []
        
        messages = []
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # Get last N lines
            for line in lines[-limit:]:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    message_data = json.loads(line)
                    messages.append(Message.from_dict(message_data))
                except Exception as e:
                    logger.debug(f"Error parsing history message: {e}")
        
        except Exception as e:
            logger.error(f"Error reading message history: {e}")
        
        return messages
    
    async def health_check(self) -> Dict[str, Any]:
        """Check fallback messaging health"""
        if not self.message_dir or not self.is_connected:
            return {
                "status": "disconnected",
                "connected": False,
                "error": "Not initialized"
            }
        
        try:
            # Check directory accessibility
            test_file = self.message_dir / "test_write"
            test_file.write_text("test")
            test_file.unlink()
            
            # Count queue files
            queue_dir = self.message_dir / "queues"
            queue_count = len(list(queue_dir.glob("*.queue")))
            
            return {
                "status": "healthy",
                "connected": True,
                "backend": "fallback_file",
                "message_dir": str(self.message_dir),
                "queue_files": queue_count,
                "subscriptions": len(self.subscriptions),
                "monitoring": self._monitor_thread and self._monitor_thread.is_alive()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }