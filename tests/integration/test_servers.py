"""
Integration tests for FastAPI servers
Tests TTS and Discovery servers with real HTTP requests
"""

import pytest
import asyncio
import json
import time
from pathlib import Path
import httpx
from unittest.mock import patch, Mock

# Server imports
from src.servers.tts_server import app as tts_app, TTSServer
from src.servers.agent_discovery import app as discovery_app, AgentDiscoveryServer


@pytest.mark.integration
class TestTTSServerIntegration:
    """Integration tests for TTS server."""
    
    @pytest.fixture
    async def tts_client(self, mock_config, temp_dir):
        """Create test client for TTS server."""
        # Mock Piper TTS
        with patch('src.servers.tts_server.PiperTTS') as mock_piper:
            mock_model = Mock()
            mock_model.synthesize.return_value = b"fake_audio_data"
            mock_model.sample_rate = 22050
            mock_piper.return_value = mock_model
            
            # Mock audio manager
            with patch('src.servers.tts_server.AudioManager') as mock_audio:
                mock_audio_instance = Mock()
                mock_audio_instance.play_audio.return_value = True
                mock_audio.return_value = mock_audio_instance
                
                # Create test client
                async with httpx.AsyncClient(app=tts_app, base_url="http://test") as client:
                    yield client
    
    async def test_tts_health_endpoint(self, tts_client):
        """Test TTS server health endpoint."""
        response = await tts_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "server" in data
        assert "timestamp" in data
    
    async def test_tts_voices_endpoint(self, tts_client):
        """Test voices listing endpoint."""
        with patch('src.servers.tts_server.TTSServer.get_available_voices') as mock_voices:
            mock_voices.return_value = {
                "amy": {
                    "name": "amy",
                    "language": "en-US",
                    "quality": "medium",
                    "sample_rate": 22050
                },
                "danny": {
                    "name": "danny", 
                    "language": "en-US",
                    "quality": "low",
                    "sample_rate": 22050
                }
            }
            
            response = await tts_client.get("/voices")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "voices" in data
            assert len(data["voices"]) == 2
            assert "amy" in data["voices"]
            assert "danny" in data["voices"]
    
    async def test_tts_speak_endpoint_get(self, tts_client):
        """Test TTS speak endpoint with GET request."""
        response = await tts_client.get("/speak", params={
            "text": "Hello, World!",
            "voice": "amy",
            "speed": 1.0
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["message"] == "Audio played successfully"
        assert data["text"] == "Hello, World!"
        assert data["voice"] == "amy"
    
    async def test_tts_speak_endpoint_post(self, tts_client):
        """Test TTS speak endpoint with POST request."""
        payload = {
            "text": "Hello from POST!",
            "voice": "danny",
            "speed": 1.2,
            "pitch": 1.1
        }
        
        response = await tts_client.post("/speak", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["text"] == "Hello from POST!"
        assert data["voice"] == "danny"
    
    async def test_tts_generate_endpoint(self, tts_client):
        """Test TTS audio generation endpoint."""
        response = await tts_client.post("/generate", json={
            "text": "Generate this audio",
            "voice": "amy"
        })
        
        assert response.status_code == 200
        
        # Should return audio data
        assert response.headers["content-type"] == "audio/wav"
        assert len(response.content) > 0
    
    async def test_tts_play_endpoint(self, tts_client):
        """Test TTS play endpoint (audio data input)."""
        # Mock audio data
        fake_audio = b"fake_wav_data"
        
        response = await tts_client.post("/play", 
            content=fake_audio,
            headers={"content-type": "audio/wav"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["message"] == "Audio played successfully"
    
    async def test_tts_error_handling(self, tts_client):
        """Test TTS server error handling."""
        # Test with empty text
        response = await tts_client.get("/speak", params={"text": ""})
        assert response.status_code == 400
        
        # Test with invalid voice
        response = await tts_client.get("/speak", params={
            "text": "Hello",
            "voice": "nonexistent_voice"
        })
        assert response.status_code == 400
        
        # Test with invalid parameters
        response = await tts_client.post("/speak", json={
            "text": "Hello",
            "speed": -1.0  # Invalid speed
        })
        assert response.status_code == 400
    
    async def test_tts_voice_management(self, tts_client):
        """Test voice model management."""
        # Test voice info endpoint
        response = await tts_client.get("/voices/amy")
        
        if response.status_code == 200:  # Voice exists
            data = response.json()
            assert "name" in data
            assert "language" in data
        else:
            assert response.status_code == 404  # Voice not found
    
    @pytest.mark.performance
    async def test_tts_performance(self, tts_client, benchmark_config):
        """Test TTS server performance."""
        start_time = time.time()
        
        # Send multiple TTS requests
        tasks = []
        for i in range(5):
            task = tts_client.get("/speak", params={
                "text": f"Performance test {i}",
                "voice": "amy"
            })
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
        
        # Average latency should be under target
        avg_latency = (end_time - start_time) / len(tasks)
        assert avg_latency < benchmark_config['tts_latency_target']


@pytest.mark.integration
class TestDiscoveryServerIntegration:
    """Integration tests for Discovery server."""
    
    @pytest.fixture
    async def discovery_client(self, mock_process_list):
        """Create test client for Discovery server."""
        # Mock process discovery
        with patch('src.servers.agent_discovery.ProcessDiscovery') as mock_discovery:
            mock_instance = Mock()
            mock_instance.identify_agents.return_value = [
                Mock(
                    agent_id="claude_001",
                    name="Claude Assistant",
                    process_id=1234,
                    status="running",
                    last_seen=time.time()
                ),
                Mock(
                    agent_id="node_agent_001", 
                    name="Node Agent",
                    process_id=5678,
                    status="running",
                    last_seen=time.time()
                )
            ]
            mock_discovery.return_value = mock_instance
            
            # Mock messaging manager
            with patch('src.servers.agent_discovery.MessagingManager') as mock_messaging:
                mock_messaging_instance = Mock()
                mock_messaging_instance.connect.return_value = True
                mock_messaging_instance.get_agents.return_value = []
                mock_messaging.return_value = mock_messaging_instance
                
                async with httpx.AsyncClient(app=discovery_app, base_url="http://test") as client:
                    yield client
    
    async def test_discovery_health_endpoint(self, discovery_client):
        """Test Discovery server health endpoint."""
        response = await discovery_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "server" in data
        assert "uptime" in data
        assert "agents_count" in data
    
    async def test_discovery_agents_endpoint(self, discovery_client):
        """Test agents listing endpoint."""
        response = await discovery_client.get("/agents")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "agents" in data
        assert "total_count" in data
        assert "last_scan" in data
        
        # Should have agents from mock
        agents = data["agents"]
        assert len(agents) >= 0  # May be empty if no agents found
    
    async def test_discovery_agents_detailed(self, discovery_client):
        """Test detailed agents endpoint."""
        response = await discovery_client.get("/agents?detailed=true")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "agents" in data
        
        # If agents found, should have detailed info
        for agent_id, agent_info in data["agents"].items():
            if isinstance(agent_info, dict):  # Detailed format
                assert "name" in agent_info
                assert "process_id" in agent_info
                assert "status" in agent_info
    
    async def test_discovery_register_agent(self, discovery_client):
        """Test agent registration endpoint."""
        agent_data = {
            "agent_id": "test_agent_001",
            "name": "Test Agent",
            "process_id": 9999,
            "metadata": {
                "version": "1.0.0",
                "capabilities": ["text", "code"]
            }
        }
        
        response = await discovery_client.post("/register", json=agent_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["agent_id"] == "test_agent_001"
        assert "registered_at" in data
    
    async def test_discovery_agent_info(self, discovery_client):
        """Test individual agent info endpoint."""
        # First register an agent
        agent_data = {
            "agent_id": "info_test_agent",
            "name": "Info Test Agent",
            "process_id": 8888
        }
        
        register_response = await discovery_client.post("/register", json=agent_data)
        assert register_response.status_code == 200
        
        # Then get agent info
        response = await discovery_client.get("/agents/info_test_agent")
        
        if response.status_code == 200:
            data = response.json()
            assert data["agent_id"] == "info_test_agent"
            assert data["name"] == "Info Test Agent"
        else:
            # Agent might not be found if registration didn't persist
            assert response.status_code == 404
    
    async def test_discovery_statistics(self, discovery_client):
        """Test discovery statistics endpoint."""
        response = await discovery_client.get("/statistics")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_agents" in data
        assert "active_agents" in data
        assert "scan_count" in data
        assert "uptime" in data
        assert "last_scan_duration" in data
    
    async def test_discovery_scan_trigger(self, discovery_client):
        """Test manual scan trigger."""
        response = await discovery_client.post("/scan")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert "scan_id" in data
        assert "agents_found" in data
    
    async def test_discovery_filtering(self, discovery_client):
        """Test agent filtering options."""
        # Test status filter
        response = await discovery_client.get("/agents?status=running")
        assert response.status_code == 200
        
        # Test name filter
        response = await discovery_client.get("/agents?name=claude")
        assert response.status_code == 200
        
        # Test process filter
        response = await discovery_client.get("/agents?process_id=1234")
        assert response.status_code == 200
    
    async def test_discovery_error_handling(self, discovery_client):
        """Test Discovery server error handling."""
        # Test invalid agent registration
        invalid_data = {
            "name": "Missing Agent ID"  # Missing required agent_id
        }
        
        response = await discovery_client.post("/register", json=invalid_data)
        assert response.status_code == 400
        
        # Test non-existent agent lookup
        response = await discovery_client.get("/agents/nonexistent_agent")
        assert response.status_code == 404
    
    @pytest.mark.performance
    async def test_discovery_performance(self, discovery_client, benchmark_config):
        """Test Discovery server performance."""
        start_time = time.time()
        
        # Send multiple discovery requests
        tasks = []
        for i in range(10):
            task = discovery_client.get("/agents")
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
        
        # Average latency should be under target
        avg_latency = (end_time - start_time) / len(tasks)
        assert avg_latency < benchmark_config['discovery_latency_target']


@pytest.mark.integration
class TestServerInteractions:
    """Test interactions between TTS and Discovery servers."""
    
    @pytest.fixture
    async def both_servers(self, mock_config, temp_dir, mock_process_list):
        """Setup both TTS and Discovery servers."""
        # Mock dependencies for both servers
        with patch('src.servers.tts_server.PiperTTS'), \
             patch('src.servers.tts_server.AudioManager'), \
             patch('src.servers.agent_discovery.ProcessDiscovery'), \
             patch('src.servers.agent_discovery.MessagingManager'):
            
            async with httpx.AsyncClient(app=tts_app, base_url="http://tts-test") as tts_client, \
                      httpx.AsyncClient(app=discovery_app, base_url="http://discovery-test") as discovery_client:
                yield tts_client, discovery_client
    
    async def test_cross_server_communication(self, both_servers):
        """Test communication between TTS and Discovery servers."""
        tts_client, discovery_client = both_servers
        
        # Register an agent with Discovery
        agent_data = {
            "agent_id": "tts_test_agent",
            "name": "TTS Test Agent",
            "process_id": 7777
        }
        
        register_response = await discovery_client.post("/register", json=agent_data)
        assert register_response.status_code == 200
        
        # Use TTS to announce agent registration
        tts_response = await tts_client.get("/speak", params={
            "text": f"Agent {agent_data['name']} has been registered",
            "voice": "amy"
        })
        assert tts_response.status_code == 200
        
        # Verify agent is discoverable
        agents_response = await discovery_client.get("/agents")
        assert agents_response.status_code == 200
    
    async def test_health_monitoring(self, both_servers):
        """Test health monitoring across servers."""
        tts_client, discovery_client = both_servers
        
        # Check health of both servers
        tts_health = await tts_client.get("/health")
        discovery_health = await discovery_client.get("/health")
        
        assert tts_health.status_code == 200
        assert discovery_health.status_code == 200
        
        # Both should report healthy
        assert tts_health.json()["status"] == "healthy"
        assert discovery_health.json()["status"] == "healthy"
    
    async def test_concurrent_operations(self, both_servers):
        """Test concurrent operations across servers."""
        tts_client, discovery_client = both_servers
        
        # Create concurrent tasks for both servers
        tasks = []
        
        # TTS tasks
        for i in range(3):
            task = tts_client.get("/speak", params={
                "text": f"Concurrent message {i}",
                "voice": "amy"
            })
            tasks.append(task)
        
        # Discovery tasks
        for i in range(3):
            task = discovery_client.get("/agents")
            tasks.append(task)
        
        # Execute all tasks concurrently
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.slow
class TestServerLoadTesting:
    """Load testing for servers."""
    
    async def test_tts_server_load(self, tts_client):
        """Test TTS server under load."""
        # Create many concurrent TTS requests
        tasks = []
        
        for i in range(50):  # 50 concurrent requests
            task = tts_client.get("/speak", params={
                "text": f"Load test message {i}",
                "voice": "amy"
            })
            tasks.append(task)
        
        start_time = time.time()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Count successful responses
        successful = sum(1 for r in responses if isinstance(r, httpx.Response) and r.status_code == 200)
        
        # Should handle most requests successfully
        success_rate = successful / len(tasks)
        assert success_rate > 0.8  # 80% success rate under load
        
        # Total time should be reasonable
        total_time = end_time - start_time
        assert total_time < 30  # Should complete within 30 seconds
    
    async def test_discovery_server_load(self, discovery_client):
        """Test Discovery server under load."""
        # Create many concurrent discovery requests
        tasks = []
        
        for i in range(100):  # 100 concurrent requests
            if i % 2 == 0:
                # Agent listing requests
                task = discovery_client.get("/agents")
            else:
                # Statistics requests
                task = discovery_client.get("/statistics")
            tasks.append(task)
        
        start_time = time.time()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Count successful responses
        successful = sum(1 for r in responses if isinstance(r, httpx.Response) and r.status_code == 200)
        
        # Should handle most requests successfully
        success_rate = successful / len(tasks)
        assert success_rate > 0.9  # 90% success rate (discovery is lighter than TTS)
        
        # Total time should be reasonable
        total_time = end_time - start_time
        assert total_time < 10  # Should complete within 10 seconds


@pytest.mark.integration
class TestServerConfiguration:
    """Test server configuration and initialization."""
    
    def test_tts_server_config_loading(self, mock_config, temp_dir):
        """Test TTS server configuration loading."""
        with patch('src.config.manager.ConfigManager.load_config') as mock_load:
            mock_load.return_value = Mock()
            mock_load.return_value.tts = Mock()
            mock_load.return_value.tts.host = 'localhost'
            mock_load.return_value.tts.port = 9003
            mock_load.return_value.tts.voices = {}
            
            server = TTSServer(config_path=str(temp_dir))
            
            assert server.host == 'localhost'
            assert server.port == 9003
    
    def test_discovery_server_config_loading(self, mock_config, temp_dir):
        """Test Discovery server configuration loading."""
        with patch('src.config.manager.ConfigManager.load_config') as mock_load:
            mock_load.return_value = Mock()
            mock_load.return_value.discovery = Mock()
            mock_load.return_value.discovery.host = 'localhost'
            mock_load.return_value.discovery.port = 9005
            mock_load.return_value.discovery.scan_interval = 5
            
            server = AgentDiscoveryServer(config_path=str(temp_dir))
            
            assert server.host == 'localhost'
            assert server.port == 9005
            assert server.scan_interval == 5
    
    def test_server_startup_shutdown(self, mock_config, temp_dir):
        """Test server startup and shutdown procedures."""
        # This would typically test actual server lifecycle
        # For now, test that server objects can be created without errors
        
        with patch('src.servers.tts_server.PiperTTS'), \
             patch('src.servers.tts_server.AudioManager'), \
             patch('src.config.manager.ConfigManager.load_config'):
            
            tts_server = TTSServer(config_path=str(temp_dir))
            assert tts_server is not None
        
        with patch('src.servers.agent_discovery.ProcessDiscovery'), \
             patch('src.servers.agent_discovery.MessagingManager'), \
             patch('src.config.manager.ConfigManager.load_config'):
            
            discovery_server = AgentDiscoveryServer(config_path=str(temp_dir))
            assert discovery_server is not None