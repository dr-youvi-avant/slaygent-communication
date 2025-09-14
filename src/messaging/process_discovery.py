#!/usr/bin/env python3
"""
Cross-platform process-based agent discovery
Supports Windows (tasklist), Linux/macOS (ps), and tmux sessions
"""

import asyncio
import logging
import subprocess
import json
import re
from typing import Dict, List, Optional, Set
from datetime import datetime

import psutil

from .base import AgentDiscoveryBackend, AgentInfo, AgentDiscoveryError
from ..config.manager import SlaygentConfig
from ..utils.os_utils import get_os_detector, SupportedOS

logger = logging.getLogger(__name__)


class ProcessAgentDiscovery(AgentDiscoveryBackend):
    """Cross-platform process-based agent discovery"""
    
    # Common AI agent process names to look for
    AGENT_PATTERNS = [
        r"claude.*",
        r"openai.*",
        r"gpt.*",
        r"copilot.*",
        r"cursor.*", 
        r"codeium.*",
        r"tabnine.*",
        r"opencode.*",
        r"anthropic.*",
        r"assistant.*",
        r"chatgpt.*",
        r"bard.*",
        r"gemini.*",
        r"llama.*",
        r"ollama.*",
        r"mistral.*",
        r"python.*agent.*",
        r".*ai_agent.*",
        r".*slaygent.*"
    ]
    
    def __init__(self, config: SlaygentConfig):
        self.config = config
        self.os_detector = get_os_detector()
        self.discovered_agents: Dict[str, List[AgentInfo]] = {}
        self._last_scan_time: Optional[datetime] = None
        
    async def discover_agents(self) -> Dict[str, List[AgentInfo]]:
        """Discover agents from system processes and tmux sessions"""
        agents = {}
        
        # Discover from system processes
        process_agents = await self._discover_from_processes()
        agents.update(process_agents)
        
        # Discover from tmux if available (Unix systems)
        if not self.os_detector.is_windows:
            tmux_agents = await self._discover_from_tmux()
            # Merge tmux agents
            for name, agent_list in tmux_agents.items():
                if name in agents:
                    agents[name].extend(agent_list)
                else:
                    agents[name] = agent_list
        
        # Cache results
        self.discovered_agents = agents
        self._last_scan_time = datetime.now()
        
        return agents
    
    async def _discover_from_processes(self) -> Dict[str, List[AgentInfo]]:
        """Discover agents from system processes using psutil"""
        agents = {}
        
        try:
            # Use psutil for cross-platform process discovery
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd', 'status']):
                try:
                    info = proc.info
                    if not info or not info.get('name'):
                        continue
                    
                    process_name = info['name'].lower()
                    cmdline = ' '.join(info.get('cmdline') or []).lower()
                    
                    # Check if this looks like an AI agent
                    agent_name = self._identify_agent(process_name, cmdline)
                    if agent_name:
                        # Get working directory
                        cwd = info.get('cwd', 'unknown')
                        if cwd is None:
                            cwd = 'unknown'
                        
                        # Create agent info
                        agent_info = AgentInfo(
                            name=agent_name,
                            location=cwd,
                            type="process",
                            status=info.get('status', 'unknown'),
                            metadata={
                                'pid': info['pid'],
                                'process_name': info['name'],
                                'cmdline': info.get('cmdline', []),
                                'discovery_method': 'psutil'
                            }
                        )
                        
                        if agent_name not in agents:
                            agents[agent_name] = []
                        agents[agent_name].append(agent_info)
                
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    # These are normal when processes disappear or we don't have access
                    continue
                except Exception as e:
                    logger.debug(f"Error processing process info: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error discovering processes with psutil: {e}")
        
        # Fallback to OS-specific commands if psutil fails
        if not agents:
            if self.os_detector.is_windows:
                agents = await self._discover_windows_processes()
            else:
                agents = await self._discover_unix_processes()
        
        return agents
    
    def _identify_agent(self, process_name: str, cmdline: str) -> Optional[str]:
        """Identify if a process is an AI agent and return agent name"""
        combined_text = f"{process_name} {cmdline}"
        
        for pattern in self.AGENT_PATTERNS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                # Try to extract a meaningful name
                
                # Check for specific agent names in order of preference
                if 'claude' in combined_text:
                    return 'claude'
                elif 'openai' in combined_text or 'gpt' in combined_text:
                    return 'openai'
                elif 'copilot' in combined_text:
                    return 'copilot'
                elif 'cursor' in combined_text:
                    return 'cursor'
                elif 'codeium' in combined_text:
                    return 'codeium'
                elif 'tabnine' in combined_text:
                    return 'tabnine'
                elif 'opencode' in combined_text:
                    return 'opencode'
                elif 'anthropic' in combined_text:
                    return 'anthropic'
                elif 'ollama' in combined_text:
                    return 'ollama'
                elif 'slaygent' in combined_text:
                    return 'slaygent'
                elif 'agent' in combined_text:
                    # Try to extract agent name before or after 'agent'
                    words = combined_text.split()
                    for i, word in enumerate(words):
                        if 'agent' in word:
                            if i > 0:
                                return words[i-1]
                            elif i < len(words) - 1:
                                return words[i+1]
                    return 'agent'
                else:
                    # Use first word of process name as fallback
                    return process_name.split()[0] if process_name else 'unknown'
        
        return None
    
    async def _discover_windows_processes(self) -> Dict[str, List[AgentInfo]]:
        """Discover agents on Windows using tasklist"""
        agents = {}
        
        try:
            # Use tasklist command
            result = await asyncio.create_subprocess_exec(
                'tasklist', '/FO', 'CSV', '/V',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                logger.error(f"tasklist command failed: {stderr.decode()}")
                return agents
            
            # Parse CSV output
            lines = stdout.decode('utf-8', errors='ignore').strip().split('\n')
            if len(lines) < 2:
                return agents
            
            # Skip header line
            for line in lines[1:]:
                try:
                    # Parse CSV (handle quoted fields)
                    fields = self._parse_csv_line(line)
                    if len(fields) < 8:
                        continue
                    
                    process_name = fields[0].strip('"').lower()
                    pid = fields[1].strip('"')
                    window_title = fields[8].strip('"') if len(fields) > 8 else ""
                    
                    # Check if this is an AI agent
                    agent_name = self._identify_agent(process_name, window_title)
                    if agent_name:
                        agent_info = AgentInfo(
                            name=agent_name,
                            location=f"PID:{pid}",
                            type="windows_process",
                            status="running",
                            metadata={
                                'pid': int(pid),
                                'process_name': fields[0].strip('"'),
                                'window_title': window_title,
                                'discovery_method': 'tasklist'
                            }
                        )
                        
                        if agent_name not in agents:
                            agents[agent_name] = []
                        agents[agent_name].append(agent_info)
                
                except Exception as e:
                    logger.debug(f"Error parsing tasklist line: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error running tasklist: {e}")
        
        return agents
    
    def _parse_csv_line(self, line: str) -> List[str]:
        """Parse CSV line handling quoted fields"""
        fields = []
        current_field = ""
        in_quotes = False
        
        for char in line:
            if char == '"':
                in_quotes = not in_quotes
                current_field += char
            elif char == ',' and not in_quotes:
                fields.append(current_field)
                current_field = ""
            else:
                current_field += char
        
        if current_field:
            fields.append(current_field)
        
        return fields
    
    async def _discover_unix_processes(self) -> Dict[str, List[AgentInfo]]:
        """Discover agents on Unix systems using ps"""
        agents = {}
        
        try:
            # Use ps command with detailed output
            result = await asyncio.create_subprocess_exec(
                'ps', 'axo', 'pid,ppid,comm,args',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                logger.error(f"ps command failed: {stderr.decode()}")
                return agents
            
            # Parse output
            lines = stdout.decode('utf-8', errors='ignore').strip().split('\n')
            if len(lines) < 2:
                return agents
            
            # Skip header line
            for line in lines[1:]:
                try:
                    # Split into fields (PID, PPID, COMM, ARGS)
                    parts = line.strip().split(None, 3)
                    if len(parts) < 4:
                        continue
                    
                    pid, ppid, comm, args = parts
                    
                    # Check if this is an AI agent
                    agent_name = self._identify_agent(comm, args)
                    if agent_name:
                        agent_info = AgentInfo(
                            name=agent_name,
                            location=f"PID:{pid}",
                            type="unix_process",
                            status="running",
                            metadata={
                                'pid': int(pid),
                                'ppid': int(ppid),
                                'comm': comm,
                                'args': args,
                                'discovery_method': 'ps'
                            }
                        )
                        
                        if agent_name not in agents:
                            agents[agent_name] = []
                        agents[agent_name].append(agent_info)
                
                except Exception as e:
                    logger.debug(f"Error parsing ps line: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error running ps: {e}")
        
        return agents
    
    async def _discover_from_tmux(self) -> Dict[str, List[AgentInfo]]:
        """Discover agents from tmux sessions (Unix only)"""
        agents = {}
        
        try:
            # Check if tmux is available
            result = await asyncio.create_subprocess_exec(
                'tmux', 'list-panes', '-a', '-F',
                '#{pane_id}:#{pane_current_command}:#{pane_current_path}',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                logger.debug(f"tmux not available or no sessions: {stderr.decode()}")
                return agents
            
            # Parse tmux output
            lines = stdout.decode('utf-8', errors='ignore').strip().split('\n')
            
            for line in lines:
                if not line.strip():
                    continue
                
                try:
                    parts = line.split(':', 2)
                    if len(parts) != 3:
                        continue
                    
                    pane_id, command, path = parts
                    
                    # Check if command looks like an AI agent
                    agent_name = self._identify_agent(command, "")
                    if agent_name:
                        agent_info = AgentInfo(
                            name=agent_name,
                            location=path.strip(),
                            type="tmux_pane",
                            status="active",
                            metadata={
                                'pane_id': pane_id,
                                'command': command,
                                'path': path.strip(),
                                'discovery_method': 'tmux'
                            }
                        )
                        
                        if agent_name not in agents:
                            agents[agent_name] = []
                        agents[agent_name].append(agent_info)
                
                except Exception as e:
                    logger.debug(f"Error parsing tmux line: {e}")
                    continue
        
        except FileNotFoundError:
            logger.debug("tmux not installed")
        except Exception as e:
            logger.error(f"Error discovering tmux agents: {e}")
        
        return agents
    
    async def register_agent(self, agent_info: AgentInfo) -> bool:
        """Register agent (no-op for process discovery)"""
        # Process discovery doesn't support registration
        return True
    
    async def unregister_agent(self, agent_name: str, location: str = None) -> bool:
        """Unregister agent (no-op for process discovery)"""
        # Process discovery doesn't support unregistration
        return True
    
    async def get_agent_info(self, agent_name: str) -> List[AgentInfo]:
        """Get information about specific agent"""
        if agent_name in self.discovered_agents:
            return self.discovered_agents[agent_name]
        
        # Perform fresh discovery
        agents = await self.discover_agents()
        return agents.get(agent_name, [])
    
    async def health_check(self) -> Dict[str, Any]:
        """Check process discovery health"""
        try:
            # Test process access
            process_count = len(list(psutil.process_iter()))
            
            return {
                "status": "healthy",
                "process_count": process_count,
                "last_scan": self._last_scan_time.isoformat() if self._last_scan_time else None,
                "os": self.os_detector.os_type.value,
                "agents_found": len(self.discovered_agents)
            }
        
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "os": self.os_detector.os_type.value
            }