"""
End-to-end integration tests for Slaygent Communication System
Tests complete workflows across all components
"""

import pytest
import asyncio
import time
import json
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock

from src.messaging.manager import MessagingManager
from src.audio.manager import AudioManager
from src.config.manager import ConfigManager


@pytest.mark.integration
@pytest.mark.slow
class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""
    
    @pytest.fixture
    async def e2e_environment(self, temp_dir, mock_config):
        """Setup complete end-to-end test environment."""
        # Create mock components
        components = {}
        
        # Mock Redis for messaging
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis.publish.return_value = 1
        mock_redis.keys.return_value = []
        
        # Mock audio system
        mock_audio = Mock()
        mock_audio.play_audio.return_value = True
        mock_audio.get_devices.return_value = [{'name': 'Test Device', 'index': 0}]
        
        # Mock TTS model
        mock_tts = Mock()
        mock_tts.synthesize.return_value = b"fake_audio_data"
        mock_tts.sample_rate = 22050
        
        with patch('redis.Redis', return_value=mock_redis), \
             patch('src.audio.manager.AudioManager', return_value=mock_audio), \
             patch('src.servers.tts_server.PiperTTS', return_value=mock_tts):
            
            # Create messaging manager
            messaging = MessagingManager(backend_type='redis')
            await messaging.connect()
            components['messaging'] = messaging
            
            # Create audio manager
            audio = AudioManager(backend_type='auto')
            components['audio'] = audio
            
            # Load configuration
            config = ConfigManager.load_config(str(temp_dir))
            components['config'] = config
            
            yield components
    
    async def test_message_to_tts_workflow(self, e2e_environment):
        """Test complete message-to-TTS workflow."""
        messaging = e2e_environment['messaging']
        audio = e2e_environment['audio']
        
        # Step 1: Send message to TTS agent
        success = await messaging.send_message(
            sender="user_agent",
            recipient="tts_agent",
            content="Hello, this is a test message for TTS"
        )
        assert success
        
        # Step 2: Simulate TTS processing and audio output
        test_audio_data = audio.generate_test_tone(frequency=440, duration=0.1, sample_rate=22050)
        playback_success = audio.play_audio(test_audio_data, sample_rate=22050)
        assert playback_success
        
        # Step 3: Send confirmation message
        confirmation_success = await messaging.send_message(
            sender="tts_agent",
            recipient="user_agent", 
            content="TTS playback completed successfully"
        )
        assert confirmation_success
    
    async def test_agent_discovery_to_messaging_workflow(self, e2e_environment):
        """Test agent discovery to messaging workflow."""
        messaging = e2e_environment['messaging']
        
        # Step 1: Simulate agent discovery
        from src.messaging.base import AgentInfo
        
        discovered_agent = AgentInfo(
            agent_id="claude_assistant",
            name="Claude Assistant",
            process_id=1234,
            status="running"
        )
        
        # Step 2: Register discovered agent
        registration_success = await messaging.register_agent(discovered_agent)
        assert registration_success
        
        # Step 3: Send message to discovered agent
        message_success = await messaging.send_message(
            sender="discovery_service",
            recipient="claude_assistant",
            content="You have been discovered and registered"
        )
        assert message_success
        
        # Step 4: Verify agent is in registry
        agents = await messaging.get_agents()
        agent_ids = [agent.agent_id for agent in agents]
        assert "claude_assistant" in agent_ids
    
    async def test_broadcast_notification_workflow(self, e2e_environment):
        """Test broadcast notification workflow."""
        messaging = e2e_environment['messaging']
        audio = e2e_environment['audio']
        
        # Step 1: Register multiple agents
        agents = [
            {"id": "agent_1", "name": "Agent One"},
            {"id": "agent_2", "name": "Agent Two"},
            {"id": "agent_3", "name": "Agent Three"}
        ]
        
        for agent_data in agents:
            from src.messaging.base import AgentInfo
            agent = AgentInfo(
                agent_id=agent_data["id"],
                name=agent_data["name"],
                process_id=1000 + int(agent_data["id"][-1])
            )
            await messaging.register_agent(agent)
        
        # Step 2: Send broadcast message
        broadcast_success = await messaging.broadcast_message(
            sender="system",
            content="System maintenance will begin in 5 minutes"
        )
        assert broadcast_success
        
        # Step 3: Play audio notification
        notification_tone = audio.generate_test_tone(
            frequency=880, duration=0.5, sample_rate=22050
        )
        audio_success = audio.play_audio(notification_tone, sample_rate=22050)
        assert audio_success
    
    async def test_error_recovery_workflow(self, e2e_environment):
        """Test error recovery workflows."""
        messaging = e2e_environment['messaging']
        audio = e2e_environment['audio']
        
        # Step 1: Simulate messaging failure
        with patch.object(messaging.backend, 'send_message', return_value=False):
            message_failed = await messaging.send_message(
                sender="test_agent",
                recipient="target_agent",
                content="This message should fail"
            )
            assert not message_failed
        
        # Step 2: Test automatic fallback (if configured)
        if messaging.fallback_enabled:
            # Should switch to fallback backend
            assert messaging.backend.backend_type in ['fallback', 'redis']
        
        # Step 3: Simulate audio failure and recovery
        with patch.object(audio.backend, 'play_audio', return_value=False):
            audio_failed = audio.play_audio(b"test_audio", sample_rate=22050)
            assert not audio_failed
        
        # Step 4: Switch to alternative audio backend
        switch_success = audio.switch_backend('none')
        assert switch_success
        
        # Should now succeed with none backend
        audio_success = audio.play_audio(b"test_audio", sample_rate=22050)
        assert audio_success


@pytest.mark.integration
class TestCrossplatformCompatibility:
    """Test cross-platform compatibility scenarios."""
    
    def test_windows_specific_workflow(self, test_env, temp_dir):
        """Test Windows-specific workflow elements."""
        if not test_env.is_windows():
            pytest.skip("Windows-only test")
        
        # Test Windows Terminal integration
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            # Simulate Windows Terminal pane creation
            from src.messaging.process_discovery import ProcessDiscovery
            discovery = ProcessDiscovery()
            
            # Should handle Windows processes
            processes = asyncio.run(discovery.scan_windows_processes())
            assert isinstance(processes, list)
    
    @pytest.mark.unix_only
    def test_unix_specific_workflow(self, test_env, temp_dir):
        """Test Unix-specific workflow elements."""
        if test_env.is_windows():
            pytest.skip("Unix-only test")
        
        # Test tmux integration
        if test_env.has_tmux():
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.stdout = "session1: 1 windows"
                mock_run.return_value.returncode = 0
                
                from src.messaging.process_discovery import ProcessDiscovery
                discovery = ProcessDiscovery()
                
                sessions = asyncio.run(discovery.scan_tmux_sessions())
                assert isinstance(sessions, list)
    
    def test_audio_backend_selection_workflow(self, test_env):
        """Test audio backend selection across platforms."""
        from src.audio.manager import AudioManager
        
        # Test automatic backend selection
        manager = AudioManager(backend_type='auto')
        
        # Should select appropriate backend for platform
        if test_env.is_windows():
            expected_backends = ['sounddevice', 'none']
        elif test_env.is_linux():
            expected_backends = ['pulse', 'sounddevice', 'none']
        elif test_env.is_macos():
            expected_backends = ['sounddevice', 'none']
        else:
            expected_backends = ['none']
        
        assert manager.backend.backend_name in expected_backends
    
    def test_configuration_loading_workflow(self, temp_dir):
        """Test configuration loading across platforms."""
        # Create platform-specific config
        config_data = {
            'tts': {'host': 'localhost', 'port': 9003},
            'audio': {'backend': 'auto'}
        }
        
        config_file = temp_dir / 'config.yaml'
        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Load configuration
        config = ConfigManager.load_config(str(temp_dir))
        
        # Should load successfully on any platform
        assert config.tts.host == 'localhost'
        assert config.tts.port == 9003


@pytest.mark.integration
@pytest.mark.performance
class TestPerformanceWorkflows:
    """Test performance-critical workflows."""
    
    async def test_message_latency_workflow(self, benchmark_config, temp_dir):
        """Test message latency in realistic workflow."""
        # Setup lightweight messaging for performance testing
        messaging = MessagingManager(backend_type='fallback', fallback_path=str(temp_dir))
        await messaging.connect()
        
        # Measure round-trip messaging latency
        latencies = []
        
        for i in range(10):
            start_time = time.time()
            
            # Send message
            await messaging.send_message(
                sender="perf_sender",
                recipient="perf_receiver",
                content=f"Performance test message {i}"
            )
            
            end_time = time.time()
            latency = end_time - start_time
            latencies.append(latency)
        
        # Calculate average latency
        avg_latency = sum(latencies) / len(latencies)
        
        # Should meet performance target
        assert avg_latency < benchmark_config['messaging_latency_target']
    
    def test_audio_latency_workflow(self, benchmark_config):
        """Test audio latency in realistic workflow."""
        from src.audio.manager import AudioManager
        
        # Use None backend for consistent performance measurement
        audio = AudioManager(backend_type='none')
        
        # Generate test audio
        test_audio = audio.generate_test_tone(frequency=440, duration=0.1, sample_rate=22050)
        
        # Measure audio playback initiation latency
        latencies = []
        
        for i in range(10):
            start_time = time.time()
            
            success = audio.play_audio(test_audio, sample_rate=22050)
            assert success
            
            end_time = time.time()
            latency = end_time - start_time
            latencies.append(latency)
        
        # Calculate average latency
        avg_latency = sum(latencies) / len(latencies)
        
        # Should be very fast with None backend
        assert avg_latency < 0.01  # 10ms
    
    async def test_concurrent_operations_workflow(self, temp_dir, benchmark_config):
        """Test concurrent operations performance."""
        # Setup components
        messaging = MessagingManager(backend_type='fallback', fallback_path=str(temp_dir))
        await messaging.connect()
        
        audio = AudioManager(backend_type='none')
        
        # Create concurrent tasks
        tasks = []
        
        # Messaging tasks
        for i in range(5):
            task = messaging.send_message(
                sender=f"concurrent_sender_{i}",
                recipient=f"concurrent_receiver_{i}",
                content=f"Concurrent message {i}"
            )
            tasks.append(task)
        
        # Audio tasks
        test_audio = audio.generate_test_tone(frequency=440, duration=0.05, sample_rate=22050)
        for i in range(5):
            # Convert to coroutine for asyncio.gather
            async def play_audio_async():
                return audio.play_audio(test_audio, sample_rate=22050)
            
            tasks.append(play_audio_async())
        
        # Execute all tasks concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # All tasks should succeed
        assert all(results)
        
        # Total time should be reasonable
        total_time = end_time - start_time
        assert total_time < 5.0  # Should complete within 5 seconds
    
    def test_memory_usage_workflow(self, temp_dir):
        """Test memory usage in realistic workflow."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create and use components
        messaging = MessagingManager(backend_type='fallback', fallback_path=str(temp_dir))
        audio = AudioManager(backend_type='none')
        
        # Simulate workload
        for i in range(100):
            # Generate audio data
            test_audio = audio.generate_test_tone(frequency=440, duration=0.1, sample_rate=22050)
            
            # Process audio (no actual playback to avoid memory growth)
            audio.normalize_audio(test_audio)
        
        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory
        
        # Memory growth should be reasonable (less than 100MB)
        assert memory_growth < 100 * 1024 * 1024


@pytest.mark.integration
class TestRealWorldScenarios:
    """Test real-world usage scenarios."""
    
    async def test_development_workflow_scenario(self, temp_dir):
        """Test typical development workflow scenario."""
        # Setup environment
        messaging = MessagingManager(backend_type='fallback', fallback_path=str(temp_dir))
        await messaging.connect()
        
        audio = AudioManager(backend_type='none')
        
        # Scenario: Developer receives build completion notification
        
        # Step 1: Build system sends message
        build_message = await messaging.send_message(
            sender="build_system",
            recipient="developer_agent",
            content="Build completed successfully - 42 tests passed"
        )
        assert build_message
        
        # Step 2: Play success sound
        success_tone = audio.generate_test_tone(frequency=523, duration=0.2, sample_rate=22050)  # C note
        audio_success = audio.play_audio(success_tone, sample_rate=22050)
        assert audio_success
        
        # Step 3: Log the event
        log_message = await messaging.send_message(
            sender="developer_agent",
            recipient="logging_service",
            content="Build notification received and processed"
        )
        assert log_message
    
    async def test_team_collaboration_scenario(self, temp_dir):
        """Test team collaboration scenario."""
        messaging = MessagingManager(backend_type='fallback', fallback_path=str(temp_dir))
        await messaging.connect()
        
        # Scenario: Team lead broadcasts standup reminder
        
        # Step 1: Register team members
        team_members = ["alice_agent", "bob_agent", "charlie_agent", "diana_agent"]
        
        for member in team_members:
            from src.messaging.base import AgentInfo
            agent = AgentInfo(
                agent_id=member,
                name=member.replace("_", " ").title(),
                process_id=1000 + len(member)
            )
            await messaging.register_agent(agent)
        
        # Step 2: Broadcast standup reminder
        broadcast_success = await messaging.broadcast_message(
            sender="team_lead_agent",
            content="Daily standup starting in 10 minutes - please join the meeting room"
        )
        assert broadcast_success
        
        # Step 3: Team members acknowledge
        for member in team_members[:2]:  # Simulate 2 responses
            ack_success = await messaging.send_message(
                sender=member,
                recipient="team_lead_agent",
                content=f"Acknowledged - {member} will join shortly"
            )
            assert ack_success
    
    async def test_ci_cd_pipeline_scenario(self, temp_dir):
        """Test CI/CD pipeline integration scenario."""
        messaging = MessagingManager(backend_type='fallback', fallback_path=str(temp_dir))
        await messaging.connect()
        
        audio = AudioManager(backend_type='none')
        
        # Scenario: Complete CI/CD pipeline with notifications
        
        pipeline_stages = [
            ("code_commit", "Code committed to main branch"),
            ("tests_running", "Running automated tests..."),
            ("tests_passed", "All tests passed ✓"),
            ("build_started", "Starting production build..."),
            ("build_completed", "Production build completed ✓"),
            ("deployment_started", "Deploying to production..."),
            ("deployment_completed", "Successfully deployed to production ✓")
        ]
        
        for stage, message in pipeline_stages:
            # Send status update
            success = await messaging.send_message(
                sender="ci_cd_system",
                recipient="dev_team",
                content=f"[{stage.upper()}] {message}"
            )
            assert success
            
            # Play different tones for different stages
            if "completed" in stage or "passed" in stage:
                # Success tone - higher frequency
                tone = audio.generate_test_tone(frequency=659, duration=0.1, sample_rate=22050)
            else:
                # Progress tone - lower frequency
                tone = audio.generate_test_tone(frequency=440, duration=0.1, sample_rate=22050)
            
            audio_success = audio.play_audio(tone, sample_rate=22050)
            assert audio_success
            
            # Small delay to simulate real pipeline timing
            await asyncio.sleep(0.1)
    
    def test_debugging_scenario(self, temp_dir):
        """Test debugging and troubleshooting scenario."""
        # Scenario: System health monitoring and issue detection
        
        config = ConfigManager.load_config(str(temp_dir))
        
        # Step 1: Check configuration validity
        assert config is not None
        assert config.tts.host == 'localhost'
        
        # Step 2: Test component initialization
        messaging = MessagingManager(backend_type='fallback', fallback_path=str(temp_dir))
        audio = AudioManager(backend_type='none')
        
        # Step 3: Verify basic functionality
        asyncio.run(messaging.connect())
        assert messaging.is_connected
        
        devices = audio.get_devices()
        assert isinstance(devices, list)
        
        # Step 4: Test error scenarios
        # Invalid backend switch should be handled gracefully
        switch_result = audio.switch_backend('nonexistent_backend')
        assert not switch_result
        
        # Should still be functional after failed switch
        test_audio = audio.generate_test_tone(frequency=440, duration=0.05, sample_rate=22050)
        playback_success = audio.play_audio(test_audio, sample_rate=22050)
        assert playback_success


@pytest.mark.integration
@pytest.mark.slow
class TestStressScenarios:
    """Test system under stress conditions."""
    
    async def test_high_message_volume_scenario(self, temp_dir):
        """Test system under high message volume."""
        messaging = MessagingManager(backend_type='fallback', fallback_path=str(temp_dir))
        await messaging.connect()
        
        # Send many messages rapidly
        tasks = []
        message_count = 100
        
        for i in range(message_count):
            task = messaging.send_message(
                sender=f"sender_{i % 10}",  # 10 different senders
                recipient=f"receiver_{i % 5}",  # 5 different receivers
                content=f"High volume test message {i}"
            )
            tasks.append(task)
        
        # Execute all tasks
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Count successful messages
        successful = sum(1 for r in results if r is True)
        success_rate = successful / message_count
        
        # Should handle most messages successfully
        assert success_rate > 0.8  # 80% success rate under stress
        
        # Should complete in reasonable time
        total_time = end_time - start_time
        assert total_time < 60  # Should complete within 1 minute
    
    def test_continuous_audio_scenario(self):
        """Test continuous audio processing."""
        audio = AudioManager(backend_type='none')
        
        # Generate and process many audio clips
        for i in range(50):
            # Generate different frequency tones
            frequency = 220 + (i * 10)  # Varying frequencies
            test_audio = audio.generate_test_tone(
                frequency=frequency, 
                duration=0.05, 
                sample_rate=22050
            )
            
            # Process audio
            normalized = audio.normalize_audio(test_audio)
            assert len(normalized) == len(test_audio)
            
            # Simulate playback
            success = audio.play_audio(test_audio, sample_rate=22050)
            assert success
    
    async def test_long_running_scenario(self, temp_dir):
        """Test long-running system scenario."""
        messaging = MessagingManager(backend_type='fallback', fallback_path=str(temp_dir))
        await messaging.connect()
        
        audio = AudioManager(backend_type='none')
        
        # Simulate system running for extended period
        start_time = time.time()
        message_count = 0
        audio_count = 0
        
        # Run for 10 seconds (simulating longer operation)
        while time.time() - start_time < 10:
            # Send periodic messages
            if message_count % 10 == 0:
                await messaging.send_message(
                    sender="system_monitor",
                    recipient="health_checker",
                    content=f"System heartbeat - {message_count} messages processed"
                )
            message_count += 1
            
            # Play periodic audio
            if audio_count % 20 == 0:
                tone = audio.generate_test_tone(frequency=440, duration=0.02, sample_rate=22050)
                audio.play_audio(tone, sample_rate=22050)
            audio_count += 1
            
            # Small delay to prevent overwhelming the system
            await asyncio.sleep(0.01)
        
        # System should still be responsive
        final_message = await messaging.send_message(
            sender="test_controller",
            recipient="system_monitor",
            content="Long running test completed successfully"
        )
        assert final_message
        
        assert message_count > 900  # Should have processed many messages
        assert audio_count > 900  # Should have processed many audio operations