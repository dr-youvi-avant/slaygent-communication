#!/usr/bin/env python3
"""
Cross-platform messaging tool for Slaygent Communication System
Supports Redis messaging and fallback modes on Windows, Linux, and macOS
"""

import sys
import argparse
import asyncio
import logging
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.messaging.manager import get_messaging_manager
from src.config.manager import get_config
from src.utils.os_utils import get_os_detector


async def send_message(sender: str, recipient: str, message: str) -> bool:
    """Send a message to an agent"""
    try:
        messaging_manager = await get_messaging_manager()
        
        success = await messaging_manager.send_message(
            sender=sender,
            recipient=recipient,
            content=message
        )
        
        if success:
            print(f"✓ Message sent to {recipient}")
            return True
        else:
            print(f"✗ Failed to send message to {recipient}")
            return False
            
    except Exception as e:
        print(f"✗ Error sending message: {e}")
        return False


async def broadcast_message(sender: str, message: str, recipients: Optional[list] = None) -> int:
    """Broadcast message to multiple agents"""
    try:
        messaging_manager = await get_messaging_manager()
        
        sent_count = await messaging_manager.broadcast_message(
            sender=sender,
            content=message,
            recipients=recipients
        )
        
        if recipients:
            print(f"✓ Broadcast sent to {sent_count}/{len(recipients)} agents")
        else:
            print(f"✓ Broadcast sent to {sent_count} agents")
        
        return sent_count
        
    except Exception as e:
        print(f"✗ Error broadcasting message: {e}")
        return 0


async def list_agents():
    """List available agents"""
    try:
        messaging_manager = await get_messaging_manager()
        agents = await messaging_manager.discover_agents()
        
        if not agents:
            print("No agents found")
            return
        
        print("Available agents:")
        for name, agent_list in agents.items():
            for agent in agent_list:
                location_info = agent.location
                if len(location_info) > 50:
                    location_info = location_info[:47] + "..."
                
                print(f"  {name:<15} {agent.type:<12} {location_info}")
        
        total_instances = sum(len(agent_list) for agent_list in agents.values())
        print(f"\\nTotal: {len(agents)} agent types, {total_instances} instances")
        
    except Exception as e:
        print(f"✗ Error listing agents: {e}")


async def show_status():
    """Show messaging system status"""
    try:
        messaging_manager = await get_messaging_manager()
        health = await messaging_manager.health_check()
        
        print(f"Messaging System Status")
        print(f"Platform: {get_os_detector().os_type.value}")
        print(f"Backend: {messaging_manager.get_backend_type()}")
        print(f"Connected: {messaging_manager.is_connected}")
        
        messaging_status = health.get("messaging", {})
        print(f"Status: {messaging_status.get('status', 'unknown')}")
        
        if messaging_manager.is_redis_available():
            print("✓ Redis messaging active")
        else:
            print("⚠ Using fallback messaging")
        
        # Show discovery status
        discovery = health.get("discovery", {})
        if discovery.get("redis"):
            redis_disc = discovery["redis"]
            print(f"Redis Discovery: {redis_disc.get('status', 'unknown')}")
        
        if discovery.get("process"):
            proc_disc = discovery["process"]
            print(f"Process Discovery: {proc_disc.get('status', 'unknown')}")
            if "agents_found" in proc_disc:
                print(f"Agents Found: {proc_disc['agents_found']}")
        
    except Exception as e:
        print(f"✗ Error getting status: {e}")


def get_sender_name() -> str:
    """Get sender name from environment or default"""
    import os
    
    # Try various environment variables
    for env_var in ["USER", "USERNAME", "LOGNAME"]:
        if env_var in os.environ:
            return os.environ[env_var]
    
    return "cli"


async def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="Slaygent Communication System - Cross-platform Messaging Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s claude "Hello from terminal"
  %(prog)s --all "System alert: Build complete"
  %(prog)s --list
  %(prog)s --status
  %(prog)s --broadcast "Deployment finished" claude opencode
        """
    )
    
    # Message arguments
    parser.add_argument(
        "recipient",
        nargs="?",
        help="Agent name to send message to"
    )
    
    parser.add_argument(
        "message",
        nargs="?",
        help="Message content"
    )
    
    # Action arguments
    parser.add_argument(
        "--all", "--broadcast",
        metavar="MESSAGE",
        help="Broadcast message to all agents"
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available agents"
    )
    
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show messaging system status"
    )
    
    # Sender options
    parser.add_argument(
        "--sender",
        default=get_sender_name(),
        help="Sender name (default: current user)"
    )
    
    # Output options
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Quiet mode"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    elif args.quiet:
        logging.basicConfig(level=logging.ERROR)
    else:
        logging.basicConfig(level=logging.WARNING)
    
    try:
        # Handle different modes
        if args.list:
            await list_agents()
            return 0
        
        if args.status:
            await show_status()
            return 0
        
        if args.all:
            sent_count = await broadcast_message(args.sender, args.all)
            return 0 if sent_count > 0 else 1
        
        # Normal message sending
        if not args.recipient or not args.message:
            if not args.quiet:
                print("Error: Recipient and message are required")
                print("Use --help for usage information")
            return 1
        
        success = await send_message(args.sender, args.recipient, args.message)
        return 0 if success else 1
        
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