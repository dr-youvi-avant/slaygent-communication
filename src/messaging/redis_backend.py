#!/usr/bin/env python3
"""
Redis-based messaging backend for cross-platform agent communication
Replaces tmux dependency with Redis pub/sub for Windows compatibility
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
import uuid

import redis.asyncio as redis
from redis.asyncio import ConnectionError as RedisConnectionError

from .base import MessageBackend, AgentDiscoveryBackend, Message, AgentInfo
from .base import ConnectionError, MessageDeliveryError, AgentDiscoveryError
from ..config.manager import SlaygentConfig

logger = logging.getLogger(__name__)


class RedisMessageBackend(MessageBackend):
    """Redis pub/sub messaging backend"""
    
    def __init__(self, config: SlaygentConfig):
        self.config = config
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.subscriptions: Dict[str, Callable] = {}
        self.is_connected = False
        self._listen_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> bool:
        """Connect to Redis server"""
        try:
            redis_config = self.config.redis
            
            # Build connection parameters
            connection_params = {
                "host": redis_config.host,
                "port": redis_config.port,
                "db": redis_config.db,
                "decode_responses": True,
                "socket_connect_timeout": 5,
                "socket_timeout": 5
            }
            
            if redis_config.password:
                connection_params["password"] = redis_config.password
            
            # Create Redis client
            self.redis_client = redis.Redis(**connection_params)
            
            # Test connection
            await self.redis_client.ping()
            
            # Create pub/sub client
            self.pubsub = self.redis_client.pubsub()
            
            self.is_connected = True
            logger.info(f"Connected to Redis at {redis_config.host}:{redis_config.port}")
            
            return True
            
        except RedisConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.is_connected = False
            raise ConnectionError(f"Redis connection failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}")
            self.is_connected = False
            raise ConnectionError(f"Unexpected Redis error: {e}")
    
    async def disconnect(self):
        """Disconnect from Redis"""
        try:
            if self._listen_task and not self._listen_task.done():
                self._listen_task.cancel()
                try:
                    await self._listen_task
                except asyncio.CancelledError:
                    pass
            
            if self.pubsub:
                await self.pubsub.close()
                self.pubsub = None
            
            if self.redis_client:
                await self.redis_client.close()
                self.redis_client = None
            
            self.is_connected = False
            self.subscriptions.clear()
            logger.info("Disconnected from Redis")
            
        except Exception as e:
            logger.error(f"Error disconnecting from Redis: {e}")
    
    def _get_channel_name(self, recipient: str) -> str:
        """Get Redis channel name for agent"""
        return f"slaygent:messages:{recipient}"
    
    def _get_history_key(self, agent_name: str) -> str:
        """Get Redis key for message history"""
        return f"slaygent:history:{agent_name}"
    
    async def send_message(self, message: Message) -> bool:
        """Send message via Redis pub/sub"""
        if not self.is_connected or not self.redis_client:
            raise ConnectionError("Not connected to Redis")
        
        try:
            channel = self._get_channel_name(message.recipient)
            history_key = self._get_history_key(message.recipient)
            
            # Serialize message
            message_data = json.dumps(message.to_dict())
            
            # Publish to channel
            subscribers = await self.redis_client.publish(channel, message_data)
            
            # Store in history (keep last 1000 messages)
            await self.redis_client.lpush(history_key, message_data)
            await self.redis_client.ltrim(history_key, 0, 999)
            
            logger.debug(f"Message sent to {message.recipient} ({subscribers} subscribers)")
            return subscribers > 0
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise MessageDeliveryError(f"Failed to send message: {e}")
    
    async def broadcast_message(self, message: Message, recipients: List[str] = None) -> int:
        """Broadcast message to multiple recipients"""
        if not recipients:
            # Get all known agents for broadcasting
            discovery = RedisAgentDiscovery(self.config)
            if discovery.redis_client is None:
                discovery.redis_client = self.redis_client
            agents = await discovery.discover_agents()
            recipients = list(agents.keys())
        
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
        if not self.is_connected or not self.pubsub:
            raise ConnectionError("Not connected to Redis")
        
        try:
            channel = self._get_channel_name(agent_name)
            await self.pubsub.subscribe(channel)
            
            self.subscriptions[agent_name] = callback
            
            # Start listening task if not already running
            if self._listen_task is None or self._listen_task.done():
                self._listen_task = asyncio.create_task(self._listen_for_messages())
            
            logger.info(f"Subscribed to messages for {agent_name}")
            
        except Exception as e:
            logger.error(f"Failed to subscribe to messages: {e}")
            raise ConnectionError(f"Subscription failed: {e}")
    
    async def unsubscribe_from_messages(self, agent_name: str):
        """Unsubscribe from messages"""
        if not self.pubsub:
            return
        
        try:
            channel = self._get_channel_name(agent_name)
            await self.pubsub.unsubscribe(channel)
            
            if agent_name in self.subscriptions:
                del self.subscriptions[agent_name]
            
            logger.info(f"Unsubscribed from messages for {agent_name}")
            
        except Exception as e:
            logger.error(f"Failed to unsubscribe: {e}")
    
    async def _listen_for_messages(self):
        """Listen for incoming messages"""
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    try:
                        # Parse message data
                        message_data = json.loads(message["data"])
                        msg = Message.from_dict(message_data)
                        
                        # Find callback for recipient
                        callback = self.subscriptions.get(msg.recipient)
                        if callback:
                            try:
                                callback(msg)
                            except Exception as e:
                                logger.error(f"Error in message callback: {e}")
                    
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
        
        except asyncio.CancelledError:
            logger.debug("Message listener cancelled")
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
    
    async def get_message_history(self, agent_name: str, limit: int = 100) -> List[Message]:
        """Get message history for agent"""
        if not self.is_connected or not self.redis_client:
            raise ConnectionError("Not connected to Redis")
        
        try:
            history_key = self._get_history_key(agent_name)
            messages_data = await self.redis_client.lrange(history_key, 0, limit - 1)
            
            messages = []
            for msg_data in messages_data:
                try:
                    message_dict = json.loads(msg_data)
                    messages.append(Message.from_dict(message_dict))
                except Exception as e:
                    logger.warning(f"Failed to parse message from history: {e}")
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get message history: {e}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Redis connection health"""
        if not self.redis_client:
            return {
                "status": "disconnected",
                "connected": False,
                "error": "No Redis client"
            }
        
        try:
            await self.redis_client.ping()
            info = await self.redis_client.info("server")
            
            return {
                "status": "healthy",
                "connected": True,
                "redis_version": info.get("redis_version"),
                "uptime_seconds": info.get("uptime_in_seconds"),
                "subscriptions": len(self.subscriptions)
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }


class RedisAgentDiscovery(AgentDiscoveryBackend):
    """Redis-based agent discovery"""
    
    def __init__(self, config: SlaygentConfig):
        self.config = config
        self.redis_client: Optional[redis.Redis] = None
        self.is_connected = False
    
    async def connect(self) -> bool:
        """Connect to Redis (shared with messaging)"""
        try:
            redis_config = self.config.redis
            
            connection_params = {
                "host": redis_config.host,
                "port": redis_config.port,
                "db": redis_config.db,
                "decode_responses": True,
                "socket_connect_timeout": 5,
                "socket_timeout": 5
            }
            
            if redis_config.password:
                connection_params["password"] = redis_config.password
            
            self.redis_client = redis.Redis(**connection_params)
            await self.redis_client.ping()
            
            self.is_connected = True
            return True
            
        except Exception as e:
            logger.error(f"Redis discovery connection failed: {e}")
            self.is_connected = False
            return False
    
    def _get_agent_key(self, agent_name: str) -> str:
        """Get Redis key for agent information"""
        return f"slaygent:agents:{agent_name}"
    
    def _get_agents_set_key(self) -> str:
        """Get Redis key for set of all agents"""
        return "slaygent:agents:all"
    
    async def discover_agents(self) -> Dict[str, List[AgentInfo]]:
        """Discover agents from Redis and system processes"""
        agents = {}
        
        if self.redis_client and self.is_connected:
            try:
                # Get all registered agents
                agent_names = await self.redis_client.smembers(self._get_agents_set_key())
                
                for agent_name in agent_names:
                    agent_data = await self.redis_client.hgetall(self._get_agent_key(agent_name))
                    if agent_data:
                        agent_info = AgentInfo(
                            name=agent_data.get("name", agent_name),
                            location=agent_data.get("location", ""),
                            type=agent_data.get("type", "process"),
                            status=agent_data.get("status", "unknown"),
                            metadata=json.loads(agent_data.get("metadata", "{}"))
                        )
                        
                        if agent_name not in agents:
                            agents[agent_name] = []
                        agents[agent_name].append(agent_info)
            
            except Exception as e:
                logger.error(f"Failed to discover agents from Redis: {e}")
        
        # Also discover from system processes (as fallback)
        try:
            from .process_discovery import ProcessAgentDiscovery
            process_discovery = ProcessAgentDiscovery(self.config)
            process_agents = await process_discovery.discover_agents()
            
            # Merge with Redis agents
            for name, agent_list in process_agents.items():
                if name not in agents:
                    agents[name] = agent_list
                else:
                    agents[name].extend(agent_list)
        
        except ImportError:
            logger.warning("Process discovery not available")
        except Exception as e:
            logger.error(f"Failed to discover system processes: {e}")
        
        return agents
    
    async def register_agent(self, agent_info: AgentInfo) -> bool:
        """Register agent in Redis"""
        if not self.redis_client or not self.is_connected:
            return False
        
        try:
            agent_key = self._get_agent_key(agent_info.name)
            agents_set_key = self._get_agents_set_key()
            
            # Store agent information
            await self.redis_client.hset(agent_key, {
                "name": agent_info.name,
                "location": agent_info.location,
                "type": agent_info.type,
                "status": agent_info.status,
                "metadata": json.dumps(agent_info.metadata),
                "last_seen": datetime.now().isoformat()
            })
            
            # Add to agents set
            await self.redis_client.sadd(agents_set_key, agent_info.name)
            
            # Set expiration (30 minutes)
            await self.redis_client.expire(agent_key, 1800)
            
            logger.debug(f"Registered agent: {agent_info.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register agent: {e}")
            return False
    
    async def unregister_agent(self, agent_name: str, location: str = None) -> bool:
        """Unregister agent from Redis"""
        if not self.redis_client or not self.is_connected:
            return False
        
        try:
            agent_key = self._get_agent_key(agent_name)
            agents_set_key = self._get_agents_set_key()
            
            # Remove agent data
            await self.redis_client.delete(agent_key)
            
            # Remove from agents set
            await self.redis_client.srem(agents_set_key, agent_name)
            
            logger.debug(f"Unregistered agent: {agent_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister agent: {e}")
            return False
    
    async def get_agent_info(self, agent_name: str) -> List[AgentInfo]:
        """Get specific agent information"""
        if not self.redis_client or not self.is_connected:
            return []
        
        try:
            agent_data = await self.redis_client.hgetall(self._get_agent_key(agent_name))
            if not agent_data:
                return []
            
            agent_info = AgentInfo(
                name=agent_data.get("name", agent_name),
                location=agent_data.get("location", ""),
                type=agent_data.get("type", "process"),
                status=agent_data.get("status", "unknown"),
                metadata=json.loads(agent_data.get("metadata", "{}"))
            )
            
            return [agent_info]
            
        except Exception as e:
            logger.error(f"Failed to get agent info: {e}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Redis agent discovery health"""
        if not self.redis_client:
            return {"status": "disconnected", "connected": False}
        
        try:
            await self.redis_client.ping()
            agents_count = await self.redis_client.scard(self._get_agents_set_key())
            
            return {
                "status": "healthy",
                "connected": True,
                "registered_agents": agents_count
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }