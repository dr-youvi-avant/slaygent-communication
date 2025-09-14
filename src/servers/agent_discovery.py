#!/usr/bin/env python3
"""
Enhanced Cross-Platform Agent Discovery Server for Slaygent Communication System
Supports Windows, Linux, and macOS with Redis integration and process detection
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
import uvicorn

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime

from ..config.manager import get_config, SlaygentConfig
from ..messaging.manager import get_messaging_manager, MessagingManager
from ..messaging.base import AgentInfo
from ..utils.os_utils import get_os_detector

logger = logging.getLogger(__name__)


class AgentDiscoveryServer:
    """Enhanced agent discovery server with cross-platform support"""
    
    def __init__(self):
        self.config = get_config()
        self.messaging_manager: Optional[MessagingManager] = None
        self.os_detector = get_os_detector()
        self._last_scan_time: Optional[datetime] = None
        self._cached_agents: Dict[str, List[AgentInfo]] = {}
        self._scan_task: Optional[asyncio.Task] = None
    
    async def initialize(self) -> bool:
        """Initialize agent discovery server"""
        try:
            # Initialize messaging system
            self.messaging_manager = await get_messaging_manager()
            
            if not self.messaging_manager.is_connected:
                logger.warning("Messaging system not connected - discovery will work with reduced functionality")
            else:
                logger.info(f"Messaging system ready with {self.messaging_manager.get_backend_type()} backend")
            
            # Start periodic agent scanning
            self._start_periodic_scan()
            
            logger.info("Agent Discovery Server initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Agent Discovery Server initialization failed: {e}")
            return False
    
    def _start_periodic_scan(self):
        """Start background task for periodic agent scanning"""
        async def scan_periodically():
            while True:
                try:
                    await self._scan_agents()
                    await asyncio.sleep(self.config.agent.refresh_interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in periodic agent scan: {e}")
                    await asyncio.sleep(self.config.agent.refresh_interval)
        
        self._scan_task = asyncio.create_task(scan_periodically())
        logger.info(f"Started periodic agent scanning (every {self.config.agent.refresh_interval}s)")
    
    async def _scan_agents(self):
        """Perform agent discovery scan"""
        if not self.messaging_manager:
            return
        
        try:
            agents = await self.messaging_manager.discover_agents()
            self._cached_agents = agents
            self._last_scan_time = datetime.now()
            
            logger.debug(f"Agent scan completed: {len(agents)} agent types found")
            
        except Exception as e:
            logger.error(f"Agent scan failed: {e}")
    
    async def get_agents(self, fresh_scan: bool = False) -> Dict[str, List[Dict[str, Any]]]:
        """Get discovered agents"""
        if fresh_scan or not self._cached_agents:
            await self._scan_agents()
        
        # Convert AgentInfo objects to dictionaries
        result = {}
        for name, agent_list in self._cached_agents.items():
            result[name] = [self._agent_info_to_dict(agent) for agent in agent_list]
        
        return result
    
    def _agent_info_to_dict(self, agent: AgentInfo) -> Dict[str, Any]:
        """Convert AgentInfo to dictionary"""
        return {
            "name": agent.name,
            "location": agent.location,
            "type": agent.type,
            "status": agent.status,
            "metadata": agent.metadata
        }
    
    async def get_agent_details(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get detailed information about a specific agent"""
        if not self.messaging_manager:
            return []
        
        try:
            agents = await self.messaging_manager.get_agent_info(agent_name)
            return [self._agent_info_to_dict(agent) for agent in agents]
            
        except Exception as e:
            logger.error(f"Failed to get agent details for {agent_name}: {e}")
            return []
    
    async def register_agent(self, name: str, location: str, agent_type: str = "manual", 
                           status: str = "active", metadata: Dict[str, Any] = None) -> bool:
        """Register a new agent"""
        if not self.messaging_manager:
            logger.warning("Cannot register agent - messaging system not available")
            return False
        
        try:
            success = await self.messaging_manager.register_agent(
                name=name,
                location=location,
                agent_type=agent_type,
                status=status,
                metadata=metadata or {}
            )
            
            if success:
                logger.info(f"Agent registered: {name} at {location}")
                # Trigger fresh scan to update cache
                await self._scan_agents()
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to register agent {name}: {e}")
            return False
    
    async def unregister_agent(self, agent_name: str, location: str = None) -> bool:
        """Unregister an agent"""
        if not self.messaging_manager:
            logger.warning("Cannot unregister agent - messaging system not available")
            return False
        
        try:
            success = await self.messaging_manager.unregister_agent(agent_name, location)
            
            if success:
                logger.info(f"Agent unregistered: {agent_name}")
                # Trigger fresh scan to update cache
                await self._scan_agents()
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to unregister agent {agent_name}: {e}")
            return False
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get discovery statistics"""
        agents = self._cached_agents
        
        total_agents = sum(len(agent_list) for agent_list in agents.values())
        
        # Count by type
        type_counts = {}
        status_counts = {}
        
        for agent_list in agents.values():
            for agent in agent_list:
                agent_type = agent.type
                agent_status = agent.status
                
                type_counts[agent_type] = type_counts.get(agent_type, 0) + 1
                status_counts[agent_status] = status_counts.get(agent_status, 0) + 1
        
        return {
            "total_agent_instances": total_agents,
            "unique_agent_names": len(agents),
            "types": type_counts,
            "statuses": status_counts,
            "last_scan": self._last_scan_time.isoformat() if self._last_scan_time else None,
            "scan_interval": self.config.agent.refresh_interval
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Get discovery server health"""
        health = {
            "service": "Agent Discovery Server",
            "status": "unknown",
            "os": self.os_detector.os_type.value,
            "scan_interval": self.config.agent.refresh_interval
        }
        
        try:
            # Check messaging system
            if self.messaging_manager:
                messaging_health = await self.messaging_manager.health_check()
                health["messaging"] = messaging_health
                
                messaging_ok = messaging_health.get("messaging", {}).get("connected", False)
                discovery_ok = any(
                    backend and backend.get("status") == "healthy"
                    for backend in messaging_health.get("discovery", {}).values()
                    if isinstance(backend, dict)
                )
                
                if messaging_ok and discovery_ok:
                    health["status"] = "healthy"
                elif discovery_ok:
                    health["status"] = "discovery_only"
                else:
                    health["status"] = "limited"
            else:
                health["messaging"] = {"error": "Messaging manager not initialized"}
                health["status"] = "no_messaging"
            
            # Add scan statistics
            stats = await self.get_statistics()
            health["statistics"] = stats
            
            # Check if scanning is active
            health["scanning_active"] = self._scan_task and not self._scan_task.done()
            
        except Exception as e:
            health["status"] = "error"
            health["error"] = str(e)
        
        return health
    
    async def shutdown(self):
        """Shutdown discovery server"""
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Agent Discovery Server shutdown")


# Global discovery server instance
discovery_server: Optional[AgentDiscoveryServer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan management"""
    global discovery_server
    
    # Startup
    logger.info("Starting Agent Discovery Server...")
    discovery_server = AgentDiscoveryServer()
    
    if not await discovery_server.initialize():
        logger.error("Failed to initialize Agent Discovery Server")
        raise RuntimeError("Agent Discovery Server initialization failed")
    
    logger.info("Agent Discovery Server ready")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Agent Discovery Server...")
    if discovery_server:
        await discovery_server.shutdown()
    discovery_server = None


# Create FastAPI app
app = FastAPI(
    title="Slaygent Communication System - Agent Discovery Server",
    description="Cross-platform AI Agent Discovery API with Redis integration",
    version="2.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Service information and quick status"""
    if not discovery_server:
        raise HTTPException(status_code=503, detail="Discovery Server not ready")
    
    try:
        stats = await discovery_server.get_statistics()
        
        return {
            "service": "Slaygent Communication System - Agent Discovery Server",
            "version": "2.0.0",
            "status": "running",
            "platform": discovery_server.os_detector.os_type.value,
            "endpoints": {
                "agents": "/agents - List all discovered agents",
                "agent": "/agent/{name} - Get specific agent details",
                "register": "/register - Register new agent (POST)",
                "unregister": "/unregister - Unregister agent (DELETE)",
                "statistics": "/statistics - Discovery statistics",
                "health": "/health - Detailed health check"
            },
            "summary": {
                "agents_found": stats.get("total_agent_instances", 0),
                "unique_agents": stats.get("unique_agent_names", 0),
                "last_scan": stats.get("last_scan")
            }
        }
        
    except Exception as e:
        logger.error(f"Error in root endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {e}")


@app.get("/agents")
async def list_agents(fresh: bool = Query(False, description="Force fresh scan")):
    """List all discovered agents"""
    if not discovery_server:
        raise HTTPException(status_code=503, detail="Discovery Server not ready")
    
    try:
        agents = await discovery_server.get_agents(fresh_scan=fresh)
        
        return {
            "agents": agents,
            "timestamp": datetime.now().isoformat(),
            "fresh_scan": fresh,
            "total_instances": sum(len(agent_list) for agent_list in agents.values()),
            "unique_agents": len(agents)
        }
        
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {e}")


@app.get("/agent/{agent_name}")
async def get_agent(agent_name: str):
    """Get detailed information about a specific agent"""
    if not discovery_server:
        raise HTTPException(status_code=503, detail="Discovery Server not ready")
    
    try:
        agent_details = await discovery_server.get_agent_details(agent_name)
        
        if not agent_details:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        
        return {
            "agent_name": agent_name,
            "instances": agent_details,
            "count": len(agent_details),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent {agent_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get agent details: {e}")


@app.post("/register")
async def register_agent(
    name: str = Query(..., description="Agent name"),
    location: str = Query(..., description="Agent location"),
    agent_type: str = Query("manual", description="Agent type"),
    status: str = Query("active", description="Agent status"),
    metadata: Optional[str] = Query(None, description="Additional metadata (JSON)")
):
    """Register a new agent"""
    if not discovery_server:
        raise HTTPException(status_code=503, detail="Discovery Server not ready")
    
    try:
        # Parse metadata if provided
        parsed_metadata = {}
        if metadata:
            import json
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON in metadata")
        
        success = await discovery_server.register_agent(
            name=name,
            location=location,
            agent_type=agent_type,
            status=status,
            metadata=parsed_metadata
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to register agent")
        
        return {
            "success": True,
            "message": f"Agent '{name}' registered successfully",
            "agent": {
                "name": name,
                "location": location,
                "type": agent_type,
                "status": status,
                "metadata": parsed_metadata
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to register agent: {e}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {e}")


@app.delete("/unregister")
async def unregister_agent(
    name: str = Query(..., description="Agent name"),
    location: Optional[str] = Query(None, description="Specific location (optional)")
):
    """Unregister an agent"""
    if not discovery_server:
        raise HTTPException(status_code=503, detail="Discovery Server not ready")
    
    try:
        success = await discovery_server.unregister_agent(name, location)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found or could not be unregistered")
        
        return {
            "success": True,
            "message": f"Agent '{name}' unregistered successfully",
            "name": name,
            "location": location
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unregister agent: {e}")
        raise HTTPException(status_code=500, detail=f"Unregistration failed: {e}")


@app.get("/statistics")
async def get_statistics():
    """Get discovery statistics"""
    if not discovery_server:
        raise HTTPException(status_code=503, detail="Discovery Server not ready")
    
    try:
        stats = await discovery_server.get_statistics()
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {e}")


@app.get("/health")
async def health_check():
    """Detailed health check"""
    if not discovery_server:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": "Discovery Server not initialized"}
        )
    
    try:
        health = await discovery_server.health_check()
        
        status_code = 200
        if health.get("status") == "error":
            status_code = 500
        elif health.get("status") in ["no_messaging", "limited"]:
            status_code = 206  # Partial Content
        
        return JSONResponse(status_code=status_code, content=health)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


def main():
    """Run Agent Discovery server"""
    config = get_config()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO if not config.debug else logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run server
    uvicorn.run(
        "src.servers.agent_discovery:app",
        host=config.discovery_server.host,
        port=config.discovery_server.port,
        workers=config.discovery_server.workers,
        log_level="info" if not config.debug else "debug"
    )


if __name__ == "__main__":
    main()