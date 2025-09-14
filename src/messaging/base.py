#!/usr/bin/env python3
"""
Abstract base classes for cross-platform messaging system
Defines the interface for messaging backends (Redis, file-based, etc.)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Message data structure"""
    id: str
    sender: str
    recipient: str
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        return {
            "id": self.id,
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary"""
        return cls(
            id=data["id"],
            sender=data["sender"],
            recipient=data["recipient"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {})
        )


@dataclass
class AgentInfo:
    """Agent information structure"""
    name: str
    location: str  # path, pane_id, process_id, etc.
    type: str     # tmux, process, terminal, etc.
    status: str   # active, idle, busy
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MessageBackend(ABC):
    """Abstract base class for messaging backends"""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to messaging backend"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from messaging backend"""
        pass
    
    @abstractmethod
    async def send_message(self, message: Message) -> bool:
        """Send a message to a recipient"""
        pass
    
    @abstractmethod
    async def broadcast_message(self, message: Message, recipients: List[str] = None) -> int:
        """Broadcast message to multiple recipients, returns number sent"""
        pass
    
    @abstractmethod
    async def subscribe_to_messages(self, agent_name: str, callback: Callable[[Message], None]):
        """Subscribe to messages for a specific agent"""
        pass
    
    @abstractmethod
    async def unsubscribe_from_messages(self, agent_name: str):
        """Unsubscribe from messages"""
        pass
    
    @abstractmethod
    async def get_message_history(self, agent_name: str, limit: int = 100) -> List[Message]:
        """Get message history for an agent"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check backend health status"""
        pass


class AgentDiscoveryBackend(ABC):
    """Abstract base class for agent discovery backends"""
    
    @abstractmethod
    async def discover_agents(self) -> Dict[str, List[AgentInfo]]:
        """Discover available agents"""
        pass
    
    @abstractmethod
    async def register_agent(self, agent_info: AgentInfo) -> bool:
        """Register an agent"""
        pass
    
    @abstractmethod
    async def unregister_agent(self, agent_name: str, location: str = None) -> bool:
        """Unregister an agent"""
        pass
    
    @abstractmethod
    async def get_agent_info(self, agent_name: str) -> List[AgentInfo]:
        """Get information about a specific agent"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check discovery backend health"""
        pass


class MessagingError(Exception):
    """Base exception for messaging errors"""
    pass


class ConnectionError(MessagingError):
    """Connection-related errors"""
    pass


class MessageDeliveryError(MessagingError):
    """Message delivery errors"""
    pass


class AgentDiscoveryError(MessagingError):
    """Agent discovery errors"""
    pass