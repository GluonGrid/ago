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
_config_path = Path.home() / ".ago" / "mcp_servers.yaml"


def _load_mcp_config():
    """Load MCP server configuration from global user config"""
    global _mcp_config

    if _mcp_config is not None:
        return _mcp_config

    load_dotenv()

    config_file = Path(_config_path)
    
    # Create empty config if it doesn't exist
    if not config_file.exists():
        config_file.parent.mkdir(exist_ok=True)
        empty_config = {
            "servers": {},
            "global": {
                "timeout": 30,
                "max_retries": 3,
                "connection_timeout": 10
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(empty_config, f, default_flow_style=False)
        _mcp_config = {}
        return _mcp_config

    try:
        with open(config_file, "r") as f:
            config_content = f.read()

        # Handle environment variable substitution
        from string import Template
        template = Template(config_content)
        substituted_content = template.substitute(os.environ)

        config = yaml.safe_load(substituted_content)

        _mcp_config = {}
        for server_name, server_config in config.get("servers", {}).items():
            if not server_config.get("enabled", True):
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
                                "name": f"{server_name}.{tool.name}",
                                "original_name": tool.name,  # Keep original for tool calls
                                "server": server_name,
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
    """Call a tool on MCP servers - handles both prefixed and non-prefixed tools"""
    config = _load_mcp_config()
    
    if not config:
        return f"Error: No MCP servers configured"
    
    # Handle prefixed tool names (e.g., "server_filesystem.read_file")
    if "." in tool_name:
        server_name, original_tool_name = tool_name.split(".", 1)
        
        if server_name in config:
            server_config = config[server_name]
            try:
                server_params = StdioServerParameters(
                    command=server_config["command"],
                    args=server_config["args"],
                    env=server_config.get("env", {}),
                )

                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(original_tool_name, parameters)
                        return result.content

            except Exception as e:
                raise Exception(f"Error calling tool {tool_name}: {e}")
        else:
            raise Exception(f"MCP server '{server_name}' not configured")
    
    # Handle non-prefixed tools - try all servers
    else:
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

