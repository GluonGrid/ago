#!/usr/bin/env python3
"""
MCP Server Registry - Load known MCP servers from mcp_servers.yaml config
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml


class MCPServerRegistry:
    """Registry that loads MCP server configurations from YAML"""
    
    def __init__(self):
        self.config_file = Path(__file__).parent.parent / "config" / "mcp_servers.yaml"
        self._config_cache = None
    
    def _load_config(self) -> Dict[str, Any]:
        """Load MCP servers configuration from YAML file"""
        if self._config_cache is not None:
            return self._config_cache
            
        if not self.config_file.exists():
            print(f"⚠️ Warning: MCP config file not found: {self.config_file}")
            return {"servers": {}, "global": {}}
        
        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f) or {}
                self._config_cache = config
                return config
        except Exception as e:
            print(f"❌ Error loading MCP config: {e}")
            return {"servers": {}, "global": {}}
    
    def get_known_servers(self) -> Dict[str, Dict[str, Any]]:
        """Get all known MCP servers from config"""
        config = self._load_config()
        return config.get("servers", {})
    
    def is_known_server(self, server_alias: str) -> bool:
        """Check if server alias exists in config"""
        servers = self.get_known_servers()
        return server_alias in servers
    
    def get_server_config(self, server_alias: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific server"""
        servers = self.get_known_servers()
        return servers.get(server_alias)
    
    def list_server_aliases(self) -> List[str]:
        """Get list of all configured server aliases"""
        servers = self.get_known_servers()
        return list(servers.keys())
    
    def get_server_by_command(self, command: str, args: List[str]) -> Optional[str]:
        """Find server alias by command and args match"""
        servers = self.get_known_servers()
        
        for alias, config in servers.items():
            if (config.get("command") == command and 
                config.get("args", []) == args):
                return alias
        
        return None
    
    def suggest_server_from_package(self, package_name: str) -> Optional[Dict[str, Any]]:
        """Suggest server configuration based on npm package name"""
        # For unknown packages, suggest generic npx installation
        if package_name.startswith("@"):
            return {
                "command": "npx",
                "args": ["-y", package_name],
                "description": f"MCP server: {package_name}",
                "env": {},
                "enabled": True
            }
        
        return None
    
    def get_global_config(self) -> Dict[str, Any]:
        """Get global MCP configuration settings"""
        config = self._load_config()
        return config.get("global", {})


# Global registry instance
registry = MCPServerRegistry()


def get_known_servers() -> Dict[str, Dict[str, Any]]:
    """Get all known MCP servers"""
    return registry.get_known_servers()


def is_known_server(server_alias: str) -> bool:
    """Check if server is known"""
    return registry.is_known_server(server_alias)


def get_server_config(server_alias: str) -> Optional[Dict[str, Any]]:
    """Get server configuration"""
    return registry.get_server_config(server_alias)


def suggest_mcp_config(server_identifier: str) -> Optional[Dict[str, Any]]:
    """Suggest MCP configuration for unknown server"""
    return registry.suggest_server_from_package(server_identifier)