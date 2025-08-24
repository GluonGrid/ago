#!/usr/bin/env python3
"""
Base AsyncNode with logging and error handling for the nator multi-agent system.
Keeps it simple - no unnecessary abstractions, just core functionality.
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from pocketflow import AsyncNode


# Simple logging setup - no complex logger classes needed
def setup_logging():
    """Simple logging setup for the nator system"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger('nator')


class BaseAgentNode(AsyncNode):
    """
    Base node for all agents in the nator system.
    Simple, focused, no unnecessary complexity.
    """
    
    def __init__(self, agent_name: str, max_iterations: int = 10):
        super().__init__(max_retries=1)
        self.agent_name = agent_name
        self.max_iterations = max_iterations
        self.iteration = 0
        self.logger = logging.getLogger(f'nator.{agent_name}')
        
        # Simple inbox - just an asyncio.Queue
        self.inbox = asyncio.Queue()
    
    async def send_message(self, target_agent: 'BaseAgentNode', message: Dict[str, Any]):
        """Send message to another agent's inbox"""
        self.logger.info(f"Sending message to {target_agent.agent_name}: {message}")
        await target_agent.inbox.put(message)
    
    async def get_message(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Get message from inbox with optional timeout"""
        try:
            if timeout:
                return await asyncio.wait_for(self.inbox.get(), timeout=timeout)
            else:
                return await self.inbox.get()
        except asyncio.TimeoutError:
            return None