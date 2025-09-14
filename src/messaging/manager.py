#!/usr/bin/env python3
"""
Unified messaging manager for Slaygent Communication System
Handles Redis pub/sub primary and file-based fallback messaging
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any, Union
from datetime import datetime
import uuid

from .base import MessageBackend, AgentDiscoveryBackend, Message, AgentInfo
from .redis_backend import RedisMessageBackend, RedisAgentDiscovery
from .fallback_backend import FallbackMessageBackend
from .process_discovery import ProcessAgentDiscovery
from ..config.manager import SlaygentConfig, get_config

logger = logging.getLogger(__name__)


class MessagingManager:
    """Unified messaging manager with Redis primary and file fallback"""
    
    def __init__(self, config: Optional[SlaygentConfig] = None):
        self.config = config or get_config()
        
        # Messaging backends
        self.redis_backend: Optional[RedisMessageBackend] = None
        self.fallback_backend: Optional[FallbackMessageBackend] = None
        self.active_backend: Optional[MessageBackend] = None
        
        # Discovery backends
        self.redis_discovery: Optional[RedisAgentDiscovery] = None
        self.process_discovery: Optional[ProcessAgentDiscovery] = None
        
        self.is_connected = False
        self._backend_type = "none"
    
    async def initialize(self) -> bool:
        """Initialize messaging system with Redis primary, fallback secondary"""
        
        # Try Redis first if enabled
        if self.config.redis.enabled:
            try:
                self.redis_backend = RedisMessageBackend(self.config)
                if await self.redis_backend.connect():
                    self.active_backend = self.redis_backend
                    self._backend_type = "redis"
                    logger.info("Messaging initialized with Redis backend")
                    
                    # Also initialize Redis discovery
                    self.redis_discovery = RedisAgentDiscovery(self.config)
                    self.redis_discovery.redis_client = self.redis_backend.redis_client
                    self.redis_discovery.is_connected = True
                    
                    self.is_connected = True
                    return True
                    
            except Exception as e:
                logger.warning(f"Redis backend failed, falling back to file messaging: {e}")
        else:
            logger.info("Redis disabled in configuration, using fallback messaging")
        
        # Fall back to file-based messaging
        try:
            self.fallback_backend = FallbackMessageBackend(self.config)
            if await self.fallback_backend.connect():
                self.active_backend = self.fallback_backend
                self._backend_type = "fallback"
                logger.info("Messaging initialized with file-based fallback")
                self.is_connected = True
                return True
                
        except Exception as e:
            logger.error(f"Fallback messaging initialization failed: {e}")
        
        # Initialize process discovery regardless of messaging backend
        try:
            self.process_discovery = ProcessAgentDiscovery(self.config)
            logger.info("Process discovery initialized")
        except Exception as e:
            logger.error(f"Process discovery initialization failed: {e}")
        
        return self.is_connected
    
    async def shutdown(self):
        """Shutdown messaging system"""
        if self.redis_backend:
            await self.redis_backend.disconnect()
        
        if self.fallback_backend:
            await self.fallback_backend.disconnect()
        
        self.is_connected = False
        logger.info("Messaging system shutdown complete")
    
    # Messaging methods
    
    async def send_message(self, sender: str, recipient: str, content: str, metadata: Dict[str, Any] = None) -> bool:
        """Send a message to a recipient"""
        if not self.active_backend:
            raise RuntimeError("No messaging backend available")
        
        message = Message(
            id=str(uuid.uuid4()),
            sender=sender,
            recipient=recipient,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        return await self.active_backend.send_message(message)
    
    async def send_message_obj(self, message: Message) -> bool:
        """Send a message object"""
        if not self.active_backend:
            raise RuntimeError("No messaging backend available")
        
        return await self.active_backend.send_message(message)
    
    async def broadcast_message(self, sender: str, content: str, recipients: List[str] = None, metadata: Dict[str, Any] = None) -> int:
        """Broadcast message to multiple recipients"""
        if not self.active_backend:
            raise RuntimeError("No messaging backend available")
        
        message = Message(
            id=str(uuid.uuid4()),
            sender=sender,
            recipient="broadcast",
            content=content,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        return await self.active_backend.broadcast_message(message, recipients)
    
    async def subscribe_to_messages(self, agent_name: str, callback: Callable[[Message], None]):
        """Subscribe to messages for an agent"""
        if not self.active_backend:
            raise RuntimeError("No messaging backend available")
        
        await self.active_backend.subscribe_to_messages(agent_name, callback)
    
    async def unsubscribe_from_messages(self, agent_name: str):
        """Unsubscribe from messages"""
        if not self.active_backend:
            return
        
        await self.active_backend.unsubscribe_from_messages(agent_name)
    
    async def get_message_history(self, agent_name: str, limit: int = 100) -> List[Message]:
        """Get message history for an agent"""
        if not self.active_backend:
            return []
        
        return await self.active_backend.get_message_history(agent_name, limit)
    
    # Agent discovery methods
    
    async def discover_agents(self) -> Dict[str, List[AgentInfo]]:
        """Discover all available agents"""
        all_agents = {}
        
        # Try Redis discovery first
        if self.redis_discovery:
            try:
                redis_agents = await self.redis_discovery.discover_agents()
                all_agents.update(redis_agents)
            except Exception as e:
                logger.debug(f"Redis discovery failed: {e}")
        
        # Always include process discovery as it provides system-level info
        if self.process_discovery:
            try:
                process_agents = await self.process_discovery.discover_agents()
                
                # Merge process agents with Redis agents
                for name, agent_list in process_agents.items():
                    if name in all_agents:
                        # Add process agents that aren't already registered
                        existing_locations = {agent.location for agent in all_agents[name]}
                        for agent in agent_list:
                            if agent.location not in existing_locations:
                                all_agents[name].append(agent)
                    else:
                        all_agents[name] = agent_list
                        
            except Exception as e:
                logger.error(f"Process discovery failed: {e}")
        
        return all_agents
    
    async def register_agent(self, name: str, location: str, agent_type: str = "process", 
                           status: str = "active", metadata: Dict[str, Any] = None) -> bool:
        """Register an agent"""
        agent_info = AgentInfo(
            name=name,
            location=location,
            type=agent_type,
            status=status,
            metadata=metadata or {}
        )
        
        # Try Redis registration first
        if self.redis_discovery:
            try:
                return await self.redis_discovery.register_agent(agent_info)
            except Exception as e:
                logger.debug(f"Redis agent registration failed: {e}")
        
        # Process discovery doesn't support registration
        return False
    
    async def unregister_agent(self, agent_name: str, location: str = None) -> bool:
        """Unregister an agent"""
        success = False
        
        if self.redis_discovery:
            try:
                success = await self.redis_discovery.unregister_agent(agent_name, location)
            except Exception as e:
                logger.debug(f"Redis agent unregistration failed: {e}")
        
        return success
    
    async def get_agent_info(self, agent_name: str) -> List[AgentInfo]:
        """Get information about a specific agent"""
        # Try Redis discovery first
        if self.redis_discovery:
            try:
                agents = await self.redis_discovery.get_agent_info(agent_name)
                if agents:
                    return agents
            except Exception as e:
                logger.debug(f"Redis agent info failed: {e}")
        
        # Fall back to process discovery
        if self.process_discovery:
            try:
                return await self.process_discovery.get_agent_info(agent_name)
            except Exception as e:
                logger.error(f"Process agent info failed: {e}")
        
        return []
    
    # Health and status methods
    
    async def health_check(self) -> Dict[str, Any]:
        """Get comprehensive health status"""
        health = {
            "messaging": {
                "connected": self.is_connected,
                "backend": self._backend_type,
                "status": "unknown"
            },
            "discovery": {
                "redis": None,
                "process": None
            }
        }
        
        # Check messaging backend health
        if self.active_backend:
            try:
                backend_health = await self.active_backend.health_check()
                health["messaging"].update(backend_health)
            except Exception as e:
                health["messaging"]["status"] = "unhealthy"
                health["messaging"]["error"] = str(e)
        
        # Check discovery backends
        if self.redis_discovery:
            try:
                health["discovery"]["redis"] = await self.redis_discovery.health_check()
            except Exception as e:
                health["discovery"]["redis"] = {"status": "error", "error": str(e)}
        
        if self.process_discovery:
            try:
                health["discovery"]["process"] = await self.process_discovery.health_check()
            except Exception as e:
                health["discovery"]["process"] = {"status": "error", "error": str(e)}
        
        return health
    
    def get_backend_type(self) -> str:
        """Get current messaging backend type"""
        return self._backend_type
    
    def is_redis_available(self) -> bool:
        """Check if Redis backend is available and active"""
        return self._backend_type == "redis" and self.redis_backend is not None


# Global messaging manager instance
_messaging_manager: Optional[MessagingManager] = None


async def get_messaging_manager() -> MessagingManager:
    """Get singleton messaging manager instance"""
    global _messaging_manager
    
    if _messaging_manager is None:
        _messaging_manager = MessagingManager()
        await _messaging_manager.initialize()
    
    return _messaging_manager


async def shutdown_messaging():
    """Shutdown global messaging manager"""
    global _messaging_manager
    
    if _messaging_manager:
        await _messaging_manager.shutdown()
        _messaging_manager = None