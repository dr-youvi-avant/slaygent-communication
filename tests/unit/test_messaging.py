"""
Unit tests for messaging system
Tests Redis backend, fallback messaging, and cross-platform message routing
"""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

from src.messaging.manager import MessagingManager
from src.messaging.redis_backend import RedisBackend
from src.messaging.fallback_backend import FallbackBackend
from src.messaging.process_discovery import ProcessDiscovery
from src.messaging.base import Message, AgentInfo


class TestMessage:
    """Test Message dataclass functionality."""
    
    def test_message_creation(self):
        """Test Message creation and serialization."""
        msg = Message(
            sender="test_agent",
            recipient="target_agent", 
            content="Hello, World!",
            message_type="text",
            timestamp=1234567890.0
        )
        
        assert msg.sender == "test_agent"
        assert msg.recipient == "target_agent"
        assert msg.content == "Hello, World!"
        assert msg.message_type == "text"
        assert msg.timestamp == 1234567890.0
    
    def test_message_to_dict(self):
        """Test Message serialization to dictionary."""
        msg = Message(
            sender="agent1",
            recipient="agent2",
            content="test message"
        )
        
        msg_dict = msg.to_dict()
        
        assert msg_dict['sender'] == "agent1"
        assert msg_dict['recipient'] == "agent2"
        assert msg_dict['content'] == "test message"
        assert 'timestamp' in msg_dict
        assert 'message_id' in msg_dict
    
    def test_message_from_dict(self):
        """Test Message deserialization from dictionary."""
        msg_dict = {
            'message_id': '12345',
            'sender': 'agent1',
            'recipient': 'agent2', 
            'content': 'test message',
            'message_type': 'text',
            'timestamp': 1234567890.0
        }
        
        msg = Message.from_dict(msg_dict)
        
        assert msg.message_id == '12345'
        assert msg.sender == 'agent1'
        assert msg.recipient == 'agent2'
        assert msg.content == 'test message'


class TestAgentInfo:
    """Test AgentInfo dataclass functionality."""
    
    def test_agent_info_creation(self):
        """Test AgentInfo creation."""
        agent = AgentInfo(
            agent_id="claude_001",
            name="Claude Assistant",
            process_id=1234,
            status="running",
            last_seen=time.time()
        )
        
        assert agent.agent_id == "claude_001"
        assert agent.name == "Claude Assistant"
        assert agent.process_id == 1234
        assert agent.status == "running"
    
    def test_agent_info_serialization(self):
        """Test AgentInfo serialization."""
        agent = AgentInfo(
            agent_id="test_agent",
            name="Test Agent",
            process_id=5678
        )
        
        agent_dict = agent.to_dict()
        
        assert agent_dict['agent_id'] == "test_agent"
        assert agent_dict['name'] == "Test Agent"
        assert agent_dict['process_id'] == 5678
        assert 'last_seen' in agent_dict


@pytest.mark.redis
class TestRedisBackend:
    """Test Redis messaging backend."""
    
    def test_redis_backend_init(self, mock_redis):
        """Test Redis backend initialization."""
        with patch('redis.Redis', return_value=mock_redis):
            backend = RedisBackend(host='localhost', port=6379)
            
            assert backend.host == 'localhost'
            assert backend.port == 6379
            assert backend.redis_client == mock_redis
    
    @pytest.mark.asyncio
    async def test_redis_connect(self, mock_redis):
        """Test Redis connection establishment."""
        mock_redis.ping.return_value = True
        
        with patch('redis.Redis', return_value=mock_redis):
            backend = RedisBackend()
            
            success = await backend.connect()
            
            assert success
            assert backend.is_connected
            mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_redis_connect_failure(self, mock_redis):
        """Test Redis connection failure handling."""
        mock_redis.ping.side_effect = Exception("Connection failed")
        
        with patch('redis.Redis', return_value=mock_redis):
            backend = RedisBackend()
            
            success = await backend.connect()
            
            assert not success
            assert not backend.is_connected
    
    @pytest.mark.asyncio
    async def test_send_message(self, mock_redis):
        """Test sending message via Redis."""
        mock_redis.ping.return_value = True
        mock_redis.publish.return_value = 1
        
        with patch('redis.Redis', return_value=mock_redis):
            backend = RedisBackend()
            await backend.connect()
            
            msg = Message(
                sender="agent1",
                recipient="agent2",
                content="test message"
            )
            
            success = await backend.send_message(msg)
            
            assert success
            mock_redis.publish.assert_called()
            
            # Verify message was published to correct channel
            call_args = mock_redis.publish.call_args
            channel = call_args[0][0]
            message_data = call_args[0][1]
            
            assert channel == "slaygent:messages:agent2"
            assert "test message" in message_data
    
    @pytest.mark.asyncio
    async def test_send_broadcast_message(self, mock_redis):
        """Test sending broadcast message via Redis."""
        mock_redis.ping.return_value = True
        mock_redis.publish.return_value = 2
        
        with patch('redis.Redis', return_value=mock_redis):
            backend = RedisBackend()
            await backend.connect()
            
            msg = Message(
                sender="broadcaster",
                recipient="*",  # Broadcast
                content="broadcast message"
            )
            
            success = await backend.send_message(msg)
            
            assert success
            mock_redis.publish.assert_called()
            
            # Should publish to broadcast channel
            call_args = mock_redis.publish.call_args
            channel = call_args[0][0]
            assert channel == "slaygent:messages:broadcast"
    
    @pytest.mark.asyncio
    async def test_receive_messages(self, mock_redis):
        """Test receiving messages via Redis."""
        # Mock Redis pubsub
        mock_pubsub = Mock()
        mock_redis.pubsub.return_value = mock_pubsub
        mock_redis.ping.return_value = True
        
        # Mock message data
        test_message = Message(
            sender="agent1",
            recipient="agent2",
            content="test message"
        )
        
        mock_pubsub.get_message.side_effect = [
            None,  # First call returns None (no messages)
            {
                'type': 'message',
                'data': json.dumps(test_message.to_dict()).encode('utf-8')
            },
            None  # Subsequent calls return None
        ]
        
        with patch('redis.Redis', return_value=mock_redis):
            backend = RedisBackend()
            await backend.connect()
            
            messages = []
            
            async def message_handler(msg):
                messages.append(msg)
            
            # Start receiving messages for agent2
            await backend.subscribe("agent2", message_handler)
            
            # Simulate message processing
            await asyncio.sleep(0.1)
            
            assert len(messages) > 0
            received_msg = messages[0]
            assert received_msg.content == "test message"
    
    @pytest.mark.asyncio
    async def test_register_agent(self, mock_redis):
        """Test agent registration in Redis."""
        mock_redis.ping.return_value = True
        mock_redis.hset.return_value = 1
        
        with patch('redis.Redis', return_value=mock_redis):
            backend = RedisBackend()
            await backend.connect()
            
            agent = AgentInfo(
                agent_id="test_agent",
                name="Test Agent",
                process_id=1234
            )
            
            success = await backend.register_agent(agent)
            
            assert success
            mock_redis.hset.assert_called()
            
            # Verify agent was stored with correct key
            call_args = mock_redis.hset.call_args
            key = call_args[0][0]
            assert key == "slaygent:agents:test_agent"
    
    @pytest.mark.asyncio
    async def test_get_agents(self, mock_redis):
        """Test getting registered agents from Redis."""
        mock_redis.ping.return_value = True
        mock_redis.keys.return_value = [b'slaygent:agents:agent1', b'slaygent:agents:agent2']
        
        # Mock agent data
        mock_redis.hgetall.side_effect = [
            {
                b'agent_id': b'agent1',
                b'name': b'Agent 1',
                b'process_id': b'1234',
                b'status': b'running'
            },
            {
                b'agent_id': b'agent2', 
                b'name': b'Agent 2',
                b'process_id': b'5678',
                b'status': b'running'
            }
        ]
        
        with patch('redis.Redis', return_value=mock_redis):
            backend = RedisBackend()
            await backend.connect()
            
            agents = await backend.get_agents()
            
            assert len(agents) == 2
            assert agents[0].agent_id == 'agent1'
            assert agents[1].agent_id == 'agent2'


class TestFallbackBackend:
    """Test fallback messaging backend."""
    
    def test_fallback_backend_init(self, temp_dir):
        """Test fallback backend initialization."""
        backend = FallbackBackend(base_path=str(temp_dir))
        
        assert backend.base_path == Path(temp_dir)
        assert not backend.is_connected
    
    @pytest.mark.asyncio
    async def test_fallback_connect(self, temp_dir):
        """Test fallback backend connection (directory creation)."""
        backend = FallbackBackend(base_path=str(temp_dir))
        
        success = await backend.connect()
        
        assert success
        assert backend.is_connected
        assert backend.messages_dir.exists()
        assert backend.agents_dir.exists()
    
    @pytest.mark.asyncio
    async def test_send_message_fallback(self, temp_dir):
        """Test sending message via fallback backend."""
        backend = FallbackBackend(base_path=str(temp_dir))
        await backend.connect()
        
        msg = Message(
            sender="agent1",
            recipient="agent2",
            content="test message"
        )
        
        success = await backend.send_message(msg)
        
        assert success
        
        # Verify message file was created
        message_files = list(backend.messages_dir.glob("*.json"))
        assert len(message_files) > 0
        
        # Verify message content
        with open(message_files[0], 'r') as f:
            saved_msg = json.load(f)
        
        assert saved_msg['content'] == "test message"
        assert saved_msg['sender'] == "agent1"
        assert saved_msg['recipient'] == "agent2"
    
    @pytest.mark.asyncio
    async def test_receive_messages_fallback(self, temp_dir):
        """Test receiving messages via fallback backend."""
        backend = FallbackBackend(base_path=str(temp_dir))
        await backend.connect()
        
        # Create a message file manually
        msg = Message(
            sender="agent1", 
            recipient="agent2",
            content="test message"
        )
        
        message_file = backend.messages_dir / f"msg_{int(time.time())}.json"
        with open(message_file, 'w') as f:
            json.dump(msg.to_dict(), f)
        
        messages = []
        
        async def message_handler(received_msg):
            messages.append(received_msg)
        
        # Start monitoring for agent2
        await backend.subscribe("agent2", message_handler)
        
        # Give some time for file monitoring to detect the message
        await asyncio.sleep(0.2)
        
        assert len(messages) > 0
        received_msg = messages[0]
        assert received_msg.content == "test message"
    
    @pytest.mark.asyncio
    async def test_register_agent_fallback(self, temp_dir):
        """Test agent registration via fallback backend."""
        backend = FallbackBackend(base_path=str(temp_dir))
        await backend.connect()
        
        agent = AgentInfo(
            agent_id="test_agent",
            name="Test Agent",
            process_id=1234
        )
        
        success = await backend.register_agent(agent)
        
        assert success
        
        # Verify agent file was created
        agent_file = backend.agents_dir / "test_agent.json"
        assert agent_file.exists()
        
        # Verify agent data
        with open(agent_file, 'r') as f:
            saved_agent = json.load(f)
        
        assert saved_agent['agent_id'] == "test_agent"
        assert saved_agent['name'] == "Test Agent"
        assert saved_agent['process_id'] == 1234


class TestProcessDiscovery:
    """Test process discovery functionality."""
    
    def test_process_discovery_init(self):
        """Test ProcessDiscovery initialization."""
        discovery = ProcessDiscovery()
        assert discovery is not None
    
    @pytest.mark.asyncio
    async def test_scan_processes_generic(self, mock_process_list):
        """Test generic process scanning."""
        with patch('psutil.process_iter') as mock_process_iter:
            # Mock psutil processes
            mock_processes = []
            for proc_data in mock_process_list:
                mock_proc = Mock()
                mock_proc.info = proc_data
                mock_processes.append(mock_proc)
            
            mock_process_iter.return_value = mock_processes
            
            discovery = ProcessDiscovery()
            processes = await discovery.scan_processes()
            
            assert len(processes) >= 1  # Should find at least one process
            
            # Look for python process
            python_processes = [p for p in processes if 'python' in p.get('name', '').lower()]
            assert len(python_processes) > 0
    
    @pytest.mark.windows
    async def test_scan_processes_windows(self, test_env):
        """Test Windows-specific process scanning."""
        if not test_env.is_windows():
            pytest.skip("Windows-only test")
        
        with patch('subprocess.run') as mock_run:
            # Mock tasklist output
            mock_run.return_value.stdout = (
                'python.exe,1234,Console,1,50000 K\n'
                'notepad.exe,5678,Console,1,10000 K\n'
            )
            mock_run.return_value.returncode = 0
            
            discovery = ProcessDiscovery()
            processes = await discovery.scan_windows_processes()
            
            assert len(processes) >= 1
            python_proc = next((p for p in processes if 'python' in p['name']), None)
            assert python_proc is not None
            assert python_proc['pid'] == 1234
    
    @pytest.mark.unix_only
    async def test_scan_processes_unix(self, test_env):
        """Test Unix-specific process scanning."""
        if test_env.is_windows():
            pytest.skip("Unix-only test")
        
        with patch('subprocess.run') as mock_run:
            # Mock ps output
            mock_run.return_value.stdout = (
                '1234 python /path/to/script.py\n'
                '5678 vim /etc/config\n'
            )
            mock_run.return_value.returncode = 0
            
            discovery = ProcessDiscovery()
            processes = await discovery.scan_unix_processes()
            
            assert len(processes) >= 1
            python_proc = next((p for p in processes if 'python' in p['name']), None)
            assert python_proc is not None
            assert python_proc['pid'] == 1234
    
    @pytest.mark.tmux
    async def test_scan_tmux_sessions(self, test_env):
        """Test tmux session scanning."""
        if not test_env.has_tmux():
            pytest.skip("tmux not available")
        
        with patch('subprocess.run') as mock_run:
            # Mock tmux list-sessions output
            mock_run.return_value.stdout = (
                'session1: 2 windows (created Mon Jan 1 12:00:00 2024)\n'
                'claude_session: 1 windows (created Mon Jan 1 12:05:00 2024)\n'
            )
            mock_run.return_value.returncode = 0
            
            discovery = ProcessDiscovery()
            sessions = await discovery.scan_tmux_sessions()
            
            assert len(sessions) >= 1
            claude_session = next((s for s in sessions if 'claude' in s['name']), None)
            assert claude_session is not None
    
    @pytest.mark.asyncio
    async def test_identify_agents(self, mock_process_list):
        """Test agent identification from process list."""
        discovery = ProcessDiscovery()
        
        # Mock process scanning
        with patch.object(discovery, 'scan_processes', return_value=mock_process_list):
            agents = await discovery.identify_agents()
            
            assert len(agents) >= 1
            
            # Should identify claude process as an agent
            claude_agent = next((a for a in agents if 'claude' in a.name.lower()), None)
            assert claude_agent is not None
            assert claude_agent.process_id == 1234


class TestMessagingManager:
    """Test messaging manager orchestration."""
    
    def test_messaging_manager_init_redis(self, mock_redis):
        """Test MessagingManager initialization with Redis."""
        with patch('redis.Redis', return_value=mock_redis):
            manager = MessagingManager(backend_type='redis')
            
            assert manager.backend_type == 'redis'
            assert isinstance(manager.backend, RedisBackend)
    
    def test_messaging_manager_init_fallback(self, temp_dir):
        """Test MessagingManager initialization with fallback."""
        manager = MessagingManager(backend_type='fallback', fallback_path=str(temp_dir))
        
        assert manager.backend_type == 'fallback'
        assert isinstance(manager.backend, FallbackBackend)
    
    @pytest.mark.asyncio
    async def test_messaging_manager_auto_fallback(self, temp_dir):
        """Test automatic fallback when Redis is unavailable."""
        # Mock Redis connection failure
        with patch('redis.Redis') as mock_redis_class:
            mock_redis = Mock()
            mock_redis.ping.side_effect = Exception("Connection refused")
            mock_redis_class.return_value = mock_redis
            
            manager = MessagingManager(
                backend_type='redis',
                fallback_enabled=True,
                fallback_path=str(temp_dir)
            )
            
            success = await manager.connect()
            
            assert success
            # Should have fallen back to FallbackBackend
            assert isinstance(manager.backend, FallbackBackend)
    
    @pytest.mark.asyncio
    async def test_messaging_manager_send_message(self, mock_redis):
        """Test sending message through MessagingManager."""
        mock_redis.ping.return_value = True
        mock_redis.publish.return_value = 1
        
        with patch('redis.Redis', return_value=mock_redis):
            manager = MessagingManager(backend_type='redis')
            await manager.connect()
            
            success = await manager.send_message(
                sender="agent1",
                recipient="agent2", 
                content="test message"
            )
            
            assert success
            mock_redis.publish.assert_called()
    
    @pytest.mark.asyncio
    async def test_messaging_manager_broadcast(self, mock_redis):
        """Test broadcasting message through MessagingManager."""
        mock_redis.ping.return_value = True
        mock_redis.publish.return_value = 2
        
        with patch('redis.Redis', return_value=mock_redis):
            manager = MessagingManager(backend_type='redis')
            await manager.connect()
            
            success = await manager.broadcast_message(
                sender="broadcaster",
                content="broadcast message"
            )
            
            assert success
            mock_redis.publish.assert_called()


@pytest.mark.integration
class TestMessagingIntegration:
    """Integration tests for messaging system."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_messaging_redis(self, mock_redis):
        """Test end-to-end messaging with Redis backend."""
        mock_redis.ping.return_value = True
        mock_redis.publish.return_value = 1
        
        # Mock pubsub for receiving
        mock_pubsub = Mock()
        mock_redis.pubsub.return_value = mock_pubsub
        
        with patch('redis.Redis', return_value=mock_redis):
            # Setup sender and receiver
            sender = MessagingManager(backend_type='redis')
            receiver = MessagingManager(backend_type='redis')
            
            await sender.connect()
            await receiver.connect()
            
            # Send message
            success = await sender.send_message(
                sender="agent1",
                recipient="agent2",
                content="Hello, Agent 2!"
            )
            
            assert success
            mock_redis.publish.assert_called()
    
    @pytest.mark.asyncio
    async def test_end_to_end_messaging_fallback(self, temp_dir):
        """Test end-to-end messaging with fallback backend."""
        # Setup sender and receiver with same directory
        sender = MessagingManager(backend_type='fallback', fallback_path=str(temp_dir))
        receiver = MessagingManager(backend_type='fallback', fallback_path=str(temp_dir))
        
        await sender.connect()
        await receiver.connect()
        
        # Setup message handler
        received_messages = []
        
        async def handle_message(msg):
            received_messages.append(msg)
        
        await receiver.subscribe("agent2", handle_message)
        
        # Send message
        success = await sender.send_message(
            sender="agent1",
            recipient="agent2",
            content="Hello via fallback!"
        )
        
        assert success
        
        # Give time for file system monitoring
        await asyncio.sleep(0.2)
        
        assert len(received_messages) > 0
        assert received_messages[0].content == "Hello via fallback!"
    
    @pytest.mark.performance
    async def test_messaging_performance(self, benchmark_config, mock_redis):
        """Test messaging performance benchmarks."""
        mock_redis.ping.return_value = True
        mock_redis.publish.return_value = 1
        
        with patch('redis.Redis', return_value=mock_redis):
            manager = MessagingManager(backend_type='redis')
            await manager.connect()
            
            # Measure message sending latency
            start_time = time.time()
            
            for i in range(10):  # Send 10 messages
                await manager.send_message(
                    sender="benchmark_agent",
                    recipient=f"target_{i}",
                    content=f"Benchmark message {i}"
                )
            
            end_time = time.time()
            avg_latency = (end_time - start_time) / 10
            
            # Should be under target latency
            assert avg_latency < benchmark_config['messaging_latency_target']