#!/usr/bin/env python3
"""
Cross-platform agent search tool for Slaygent Communication System
Discovers AI agents on Windows, Linux, and macOS
"""

import sys
import argparse
import asyncio
import logging
import requests
from pathlib import Path
from typing import Optional, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.messaging.manager import get_messaging_manager
from src.config.manager import get_config
from src.utils.os_utils import get_os_detector


def get_agents_from_server(host: str = "localhost", port: int = 9005) -> Dict[str, Any]:
    """Get agents from discovery server via HTTP"""
    try:
        url = f"http://{host}:{port}/agents"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}"}
            
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to discovery server"}
    except Exception as e:
        return {"error": str(e)}


def get_server_statistics(host: str = "localhost", port: int = 9005) -> Dict[str, Any]:
    """Get statistics from discovery server"""
    try:
        url = f"http://{host}:{port}/statistics"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}"}
            
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to discovery server"}
    except Exception as e:
        return {"error": str(e)}


def check_discovery_server(host: str = "localhost", port: int = 9005) -> Dict[str, Any]:
    """Check discovery server status"""
    try:
        url = f"http://{host}:{port}/health"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "error", "code": response.status_code}
            
    except requests.exceptions.ConnectionError:
        return {"status": "not_running", "error": "Connection refused"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def search_agents_direct() -> Dict[str, Any]:
    """Search agents directly using messaging manager"""
    try:
        messaging_manager = await get_messaging_manager()
        agents = await messaging_manager.discover_agents()
        
        # Convert AgentInfo objects to dictionaries for display
        result = {}
        for name, agent_list in agents.items():
            result[name] = []
            for agent in agent_list:
                result[name].append({
                    "name": agent.name,
                    "location": agent.location,
                    "type": agent.type,
                    "status": agent.status,
                    "metadata": agent.metadata
                })
        
        return {"agents": result, "source": "direct"}
        
    except Exception as e:
        return {"error": f"Direct discovery failed: {e}"}


def format_agent_location(location: str, max_length: int = 50) -> str:
    """Format agent location for display"""
    if len(location) <= max_length:
        return location
    
    # Try to show meaningful part
    if location.startswith("PID:"):
        return location  # Keep PID info short
    elif "/" in location or "\\\\" in location:
        # Path - show last part
        parts = location.replace("\\\\", "/").split("/")
        if len(parts) > 1:
            return f".../{parts[-1]}"
    
    return location[:max_length-3] + "..."


def display_agents(agents_data: Dict[str, Any], verbose: bool = False, format_output: str = "table"):
    """Display agents in various formats"""
    if "error" in agents_data:
        print(f"✗ Error: {agents_data['error']}")
        return
    
    agents = agents_data.get("agents", {})
    source = agents_data.get("source", "server")
    
    if not agents:
        print("No agents found")
        return
    
    if format_output == "json":
        import json
        print(json.dumps(agents, indent=2))
        return
    
    # Table format
    print(f"Discovered Agents ({source}):")
    print(f"Platform: {get_os_detector().os_type.value}")
    print()
    
    # Count totals
    total_instances = sum(len(agent_list) for agent_list in agents.values())
    
    if verbose:
        # Detailed view
        for name, agent_list in agents.items():
            print(f"Agent: {name}")
            for i, agent in enumerate(agent_list):
                location = agent.get("location", "unknown")
                agent_type = agent.get("type", "unknown")
                status = agent.get("status", "unknown")
                
                print(f"  [{i+1}] Type: {agent_type}")
                print(f"      Location: {location}")
                print(f"      Status: {status}")
                
                if agent.get("metadata"):
                    metadata = agent["metadata"]
                    if "pid" in metadata:
                        print(f"      PID: {metadata['pid']}")
                    if "discovery_method" in metadata:
                        print(f"      Discovery: {metadata['discovery_method']}")
                print()
    else:
        # Compact table view
        print(f"{'Name':<15} {'Type':<12} {'Status':<10} {'Location'}")
        print("-" * 70)
        
        for name, agent_list in agents.items():
            for agent in agent_list:
                location = format_agent_location(agent.get("location", "unknown"))
                agent_type = agent.get("type", "unknown")[:11]
                status = agent.get("status", "unknown")[:9]
                
                print(f"{name:<15} {agent_type:<12} {status:<10} {location}")
    
    print(f"\\nTotal: {len(agents)} agent types, {total_instances} instances")


def display_statistics(stats: Dict[str, Any]):
    """Display discovery statistics"""
    if "error" in stats:
        print(f"✗ Error getting statistics: {stats['error']}")
        return
    
    print("Discovery Statistics:")
    print(f"  Total Instances: {stats.get('total_agent_instances', 0)}")
    print(f"  Unique Names: {stats.get('unique_agent_names', 0)}")
    
    # Type breakdown
    types = stats.get("types", {})
    if types:
        print("  By Type:")
        for agent_type, count in types.items():
            print(f"    {agent_type}: {count}")
    
    # Status breakdown
    statuses = stats.get("statuses", {})
    if statuses:
        print("  By Status:")
        for status, count in statuses.items():
            print(f"    {status}: {count}")
    
    # Timing info
    last_scan = stats.get("last_scan")
    if last_scan:
        print(f"  Last Scan: {last_scan}")
    
    interval = stats.get("scan_interval")
    if interval:
        print(f"  Scan Interval: {interval}s")


def show_status(host: str = "localhost", port: int = 9005):
    """Show discovery server status"""
    health = check_discovery_server(host, port)
    
    print(f"Agent Discovery Status ({host}:{port})")
    print(f"Platform: {get_os_detector().os_type.value}")
    
    if health.get("status") == "not_running":
        print("Status: ✗ Not running")
        print("\\nTo start discovery server:")
        print("  python -m src.servers.agent_discovery")
        return
    
    status = health.get("status", "unknown")
    if status == "healthy":
        print("Status: ✓ Healthy")
    elif status == "limited":
        print("Status: ⚠ Limited functionality")
    else:
        print(f"Status: ✗ {status}")
    
    # Messaging info
    messaging = health.get("messaging", {})
    if messaging:
        backend = messaging.get("messaging", {}).get("backend", "unknown")
        connected = messaging.get("messaging", {}).get("connected", False)
        print(f"Messaging: {backend} {'✓' if connected else '✗'}")
    
    # Discovery backends
    discovery = health.get("messaging", {}).get("discovery", {})
    if discovery:
        for backend_name, backend_info in discovery.items():
            if isinstance(backend_info, dict):
                backend_status = backend_info.get("status", "unknown")
                print(f"{backend_name.title()} Discovery: {backend_status}")
    
    # Statistics
    stats = health.get("statistics", {})
    if stats:
        instances = stats.get("total_agent_instances", 0)
        unique = stats.get("unique_agent_names", 0)
        print(f"Agents Found: {instances} instances, {unique} unique")


async def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="Slaygent Communication System - Agent Discovery Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --verbose
  %(prog)s --fresh
  %(prog)s --statistics
  %(prog)s --status
  %(prog)s --format json
        """
    )
    
    # Search options
    parser.add_argument(
        "--fresh", "-f",
        action="store_true",
        help="Force fresh scan (bypass cache)"
    )
    
    parser.add_argument(
        "--direct", "-d",
        action="store_true",
        help="Use direct discovery (bypass server)"
    )
    
    # Display options
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output with details"
    )
    
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)"
    )
    
    # Information commands
    parser.add_argument(
        "--statistics", "--stats",
        action="store_true",
        help="Show discovery statistics"
    )
    
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show discovery server status"
    )
    
    # Server options
    parser.add_argument(
        "--host",
        default="localhost",
        help="Discovery server host (default: localhost)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Discovery server port (default from config)"
    )
    
    # Output options
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Quiet mode"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose and not args.quiet:
        logging.basicConfig(level=logging.DEBUG)
    elif args.quiet:
        logging.basicConfig(level=logging.ERROR)
    else:
        logging.basicConfig(level=logging.WARNING)
    
    # Get configuration
    try:
        config = get_config()
        port = args.port or config.discovery_server.port
    except Exception as e:
        if not args.quiet:
            print(f"Configuration error: {e}")
        port = args.port or 9005
    
    try:
        # Handle status command
        if args.status:
            show_status(args.host, port)
            return 0
        
        # Handle statistics command
        if args.statistics:
            stats = get_server_statistics(args.host, port)
            display_statistics(stats)
            return 0
        
        # Discover agents
        if args.direct:
            # Use direct discovery
            agents_data = await search_agents_direct()
        else:
            # Use server-based discovery
            server_data = get_agents_from_server(args.host, port)
            
            if "error" in server_data:
                # Fallback to direct discovery
                if not args.quiet:
                    print(f"Server discovery failed: {server_data['error']}")
                    print("Falling back to direct discovery...")
                agents_data = await search_agents_direct()
            else:
                agents_data = server_data
                agents_data["source"] = "server"
        
        # Display results
        display_agents(agents_data, args.verbose, args.format)
        
        # Return appropriate exit code
        if "error" in agents_data:
            return 1
        
        agents = agents_data.get("agents", {})
        return 0 if agents else 2  # 2 = no agents found
        
    except KeyboardInterrupt:
        if not args.quiet:
            print("\\nOperation cancelled")
        return 130
    except Exception as e:
        if not args.quiet:
            print(f"✗ Error: {e}")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.exit(130)