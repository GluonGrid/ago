#!/usr/bin/env python3
"""
Simple MCP tools integration - refactored from ai_agent_cli/utils/mcp_tools_clean.py
Keeps the working patterns but removes unnecessary complexity.
"""

import os
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class ToolPermissionManager:
    """Simple tool permission system - supervisor gets all, subagents get read-only"""

    def __init__(self, agent_type: str):
        self.agent_type = agent_type
        self.write_tool_blacklist = [
            "write",
            "edit",
            "create",
            "modify",
            "delete",
            "update",
            "execute",
            "run",
            "save",
            "insert",
            "remove",
            "replace",
        ]

    def filter_tools_for_agent(self, tools: List[Dict]) -> List[Dict]:
        """Filter tools based on agent permissions"""
        if self.agent_type == "supervisor":
            # Supervisor gets all tools
            return tools

        # Subagents only get read-only tools
        filtered_tools = []
        for tool in tools:
            tool_name = tool.get("name", "").lower()
            tool_desc = tool.get("description", "").lower()

            # Check if it's a write operation
            is_write_tool = any(
                pattern in tool_name or pattern in tool_desc
                for pattern in self.write_tool_blacklist
            )

            if not is_write_tool:
                filtered_tools.append(tool)

        return filtered_tools


# Global MCP config - keep it simple
_mcp_config = None
_config_path = "config/mcp_servers.yaml"


def _load_mcp_config():
    """Load MCP server configuration - copied from working implementation"""
    global _mcp_config

    if _mcp_config is not None:
        return _mcp_config

    load_dotenv()

    config_file = Path(_config_path)
    if not config_file.exists():
        _mcp_config = {}
        return _mcp_config

    try:
        with open(config_file, "r") as f:
            config_content = f.read()

        from string import Template

        template = Template(config_content)
        substituted_content = template.substitute(os.environ)

        config = yaml.safe_load(substituted_content)

        _mcp_config = {}
        for server_name, server_config in config.get("servers", {}).items():
            if not server_config.get("enabled", True):
                continue

            if server_name == "brave_search" and not os.environ.get(
                "BRAVE_API_KEY"
            ):
                continue

            _mcp_config[server_name] = {
                "command": server_config["command"],
                "args": server_config["args"],
                "env": server_config.get("env", {}),
            }

        return _mcp_config

    except Exception as e:
        print(f"❌ Error loading MCP config: {e}")
        _mcp_config = {}
        return _mcp_config


async def get_tools_async() -> List[Dict]:
    """Get available tools from MCP servers - copied from working implementation"""
    config = _load_mcp_config()

    all_tools = []

    for server_name, server_config in config.items():
        try:
            server_params = StdioServerParameters(
                command=server_config["command"],
                args=server_config["args"],
                env=server_config.get("env", {}),
            )

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_response = await session.list_tools()

                    for tool in tools_response.tools:
                        all_tools.append(
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": getattr(
                                    tool, "inputSchema", {}
                                ).get("properties", {})
                                if hasattr(tool, "inputSchema")
                                else {},
                            }
                        )

        except Exception as e:
            print(f"❌ Error getting tools from {server_name}: {e}")
            continue

    return all_tools


async def call_tool_async(tool_name: str, parameters: Dict[str, Any]) -> Any:
    """Call a tool on MCP servers - copied from working implementation"""
    config = _load_mcp_config()
    if not config:
        # Fallback for basic read_file
        if tool_name == "read_file":
            path = parameters.get("path", "")
            if not path:
                return "Error: Missing required parameter 'path'"
            try:
                with open(path, "r") as f:
                    return f.read()
            except Exception as e:
                return f"Error reading file: {str(e)}"
        return f"Error: Tool {tool_name} not available"

    # Try each server until we find one that has the tool
    for server_name, server_config in config.items():
        try:
            server_params = StdioServerParameters(
                command=server_config["command"],
                args=server_config["args"],
                env=server_config.get("env", {}),
            )

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    tools_response = await session.list_tools()
                    tool_names = [tool.name for tool in tools_response.tools]

                    if tool_name in tool_names:
                        result = await session.call_tool(tool_name, parameters)
                        return result.content

        except Exception as e:
            print(f"❌ Error calling tool {tool_name} on {server_name}: {e}")
            continue

    raise Exception(f"Tool {tool_name} not found on any MCP server")

