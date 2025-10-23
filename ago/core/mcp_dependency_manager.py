#!/usr/bin/env python3
"""
MCP Dependency Manager - Auto-install missing MCP servers for templates
"""

import logging
from typing import Dict, List, Any, Optional

from .mcp_registry import registry, suggest_mcp_config
from ..cli.mcp_commands import config_manager


class MCPDependencyManager:
    """Manages MCP server dependencies for templates"""
    
    def __init__(self):
        self.logger = logging.getLogger("ago.mcp_dependency_manager")
    
    def extract_mcp_requirements(self, template_data: Dict[str, Any]) -> List[str]:
        """Extract MCP server requirements from template data"""
        return template_data.get("mcp_servers", [])
    
    async def check_and_install_dependencies(
        self, 
        template_name: str, 
        template_data: Dict[str, Any],
        interactive: bool = True
    ) -> bool:
        """
        Check template MCP dependencies and install missing ones
        
        Args:
            template_name: Name of the template
            template_data: Template configuration data
            interactive: Whether to prompt user for confirmation
            
        Returns:
            True if all dependencies are satisfied, False if installation failed
        """
        required_servers = self.extract_mcp_requirements(template_data)
        
        if not required_servers:
            # No MCP dependencies
            self.logger.info(f"Template {template_name} has no MCP dependencies")
            return True
        
        self.logger.info(f"Checking MCP dependencies for template: {template_name}")
        self.logger.info(f"Required servers: {required_servers}")
        
        print(f"🔍 Checking MCP dependencies for template: {template_name}")
        
        missing_servers = []
        existing_servers = []
        
        # Check which servers are missing
        for server_id in required_servers:
            self.logger.info(f"Checking server: {server_id}")
            if self._is_server_available(server_id):
                self.logger.info(f"Server {server_id} is available")
                existing_servers.append(server_id)
            else:
                self.logger.info(f"Server {server_id} is missing")
                missing_servers.append(server_id)
        
        if existing_servers:
            print(f"✅ Found existing servers: {', '.join(existing_servers)}")
        
        if not missing_servers:
            print("✅ All MCP dependencies satisfied")
            return True
        
        # Some servers are missing
        print(f"❌ Missing MCP servers: {', '.join(missing_servers)}")
        
        if not interactive:
            print("❌ Cannot install MCP servers in non-interactive mode")
            return False
        
        # Ask user if they want to install missing servers
        print(f"Install {len(missing_servers)} missing MCP server(s)? [Y/n] ", end="")
        try:
            response = input().strip().lower()
            if response and not response.startswith('y'):
                print("❌ Template requires MCP servers that are not installed")
                return False
        except (EOFError, KeyboardInterrupt):
            print("❌ Installation cancelled")
            return False
        
        # Install missing servers
        success = await self._install_missing_servers(missing_servers)
        
        if success:
            print("✅ All MCP dependencies installed successfully")
            return True
        else:
            print("❌ Failed to install some MCP dependencies")
            return False
    
    async def _install_missing_servers(self, missing_servers: List[str]) -> bool:
        """Install missing MCP servers using simple prompts"""
        all_success = True
        
        for server_id in missing_servers:
            print(f"\n🔧 Installing MCP server: {server_id}")
            
            try:
                success = await self._install_single_server(server_id)
                if not success:
                    all_success = False
                    print(f"❌ Failed to install {server_id}")
            except Exception as e:
                all_success = False
                print(f"❌ Error installing {server_id}: {e}")
        
        return all_success
    
    async def _install_single_server(self, server_id: str) -> bool:
        """Install a single MCP server with simple prompts"""
        # Get suggested configuration
        suggested_config = suggest_mcp_config(server_id)
        
        if not suggested_config:
            print(f"❓ Unknown server: {server_id}")
            print("   Please add it manually with: ago mcp add")
            return False
        
        print(f"📋 {suggested_config['description']}")
        
        # Ask for command
        default_cmd = suggested_config["command"]
        print(f"Command ({default_cmd}): ", end="")
        command = input().strip() or default_cmd
        
        # Ask for arguments
        default_args = " ".join(suggested_config["args"])
        print(f"Arguments ({default_args}): ", end="")
        args_input = input().strip() or default_args
        args = args_input.split() if args_input else []
        
        # Ask for environment variables
        env_vars = {}
        print("Add environment variables? [y/N] ", end="")
        if input().strip().lower().startswith('y'):
            while True:
                print("Environment variable name (or press Enter to finish): ", end="")
                env_name = input().strip()
                if not env_name:
                    break
                print(f"Value for {env_name}: ", end="")
                env_value = input().strip()
                env_vars[env_name] = env_value
        
        # Generate unique alias
        suggested_alias = server_id.split('/')[-1].replace('-', '_')
        alias = self._generate_unique_alias(suggested_alias)
        print(f"Server alias ({alias}): ", end="")
        user_alias = input().strip()
        if user_alias:
            alias = user_alias
        
        try:
            # Save configuration
            config_manager.add_server(alias, command, args, env_vars, suggested_config["description"])
            print(f"✅ Installed as '{alias}'")
            return True
            
        except Exception as e:
            print(f"❌ Installation failed: {e}")
            return False
    
    def _generate_unique_alias(self, suggested_alias: str) -> str:
        """Generate a unique alias for the server"""
        alias = suggested_alias
        counter = 1
        while registry.is_known_server(alias):
            alias = f"{suggested_alias}_{counter}"
            counter += 1
        return alias

    def _is_server_available(self, server_identifier: str) -> bool:
        """Check if MCP server is already configured"""
        self.logger.info(f"Checking if server {server_identifier} is available")
        
        # Check by alias first
        if registry.is_known_server(server_identifier):
            self.logger.info(f"Found server {server_identifier} by alias")
            return True
        
        servers = registry.get_known_servers()
        self.logger.info(f"Available servers: {list(servers.keys())}")
        
        # Check by command signature (for npm packages)
        if server_identifier.startswith("@"):
            self.logger.info(f"Checking npm package: {server_identifier}")
            # Look for existing server with matching npm package
            for alias, config in servers.items():
                self.logger.info(f"Checking server {alias}: command={config.get('command')}, args={config.get('args', [])}")
                if (config.get("command") == "npx" and 
                    server_identifier in config.get("args", [])):
                    self.logger.info(f"Found npm package {server_identifier} in server {alias}")
                    return True
        
        # Check for Python script paths
        elif server_identifier.endswith(".py"):
            self.logger.info(f"Checking Python script: {server_identifier}")
            # Look for existing server with matching Python script path
            for alias, config in servers.items():
                if (config.get("command") == "python" and 
                    server_identifier in config.get("args", [])):
                    self.logger.info(f"Found Python script {server_identifier} in server {alias}")
                    return True
            
            # Also check for absolute path matches
            import os
            abs_path = os.path.abspath(server_identifier)
            self.logger.info(f"Checking absolute path: {abs_path}")
            for alias, config in servers.items():
                if config.get("command") == "python":
                    for arg in config.get("args", []):
                        if os.path.abspath(arg) == abs_path:
                            self.logger.info(f"Found Python script {server_identifier} (abs path) in server {alias}")
                            return True
        
        # Enhanced matching: check if the template requirement corresponds to a configured server
        # This handles cases where template requires "@modelcontextprotocol/server-filesystem" 
        # but server is configured as alias "server_filesystem"
        else:
            self.logger.info(f"Checking enhanced matching for: {server_identifier}")
            # Check if any configured server matches this identifier
            for alias, config in servers.items():
                # For npm packages, check if the configured args contain the server_identifier
                if config.get("command") == "npx":
                    args = config.get("args", [])
                    self.logger.info(f"Checking npx server {alias} with args: {args}")
                    # Check exact match in args
                    if server_identifier in args:
                        self.logger.info(f"Found exact match for {server_identifier} in {alias}")
                        return True
                    # Check if any arg contains the identifier (for version-specific packages)
                    for arg in args:
                        if server_identifier in arg or arg in server_identifier:
                            self.logger.info(f"Found partial match: {server_identifier} <-> {arg} in {alias}")
                            return True
        
        self.logger.info(f"Server {server_identifier} is not available")
        return False
    


# Global dependency manager instance
dependency_manager = MCPDependencyManager()


async def check_template_mcp_dependencies(
    template_name: str, 
    template_data: Dict[str, Any],
    interactive: bool = True
) -> bool:
    """
    Check and install MCP dependencies for a template
    
    Args:
        template_name: Name of the template  
        template_data: Template configuration data
        interactive: Whether to prompt user for installation
        
    Returns:
        True if dependencies are satisfied, False otherwise
    """
    return await dependency_manager.check_and_install_dependencies(
        template_name, template_data, interactive
    )