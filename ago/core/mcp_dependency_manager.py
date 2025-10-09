#!/usr/bin/env python3
"""
MCP Dependency Manager - Auto-install missing MCP servers for templates
"""

from typing import Dict, List, Any, Optional

from .mcp_registry import registry, suggest_mcp_config
from ..cli.mcp_commands import config_manager


class MCPDependencyManager:
    """Manages MCP server dependencies for templates"""
    
    def __init__(self):
        pass
    
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
            return True
        
        print(f"🔍 Checking MCP dependencies for template: {template_name}")
        
        missing_servers = []
        existing_servers = []
        
        # Check which servers are missing
        for server_id in required_servers:
            if self._is_server_available(server_id):
                existing_servers.append(server_id)
            else:
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
        # Check by alias first
        if registry.is_known_server(server_identifier):
            return True
        
        # Check by command signature (for npm packages)
        if server_identifier.startswith("@"):
            # Look for existing server with matching npm package
            servers = registry.get_known_servers()
            for alias, config in servers.items():
                if (config.get("command") == "npx" and 
                    server_identifier in config.get("args", [])):
                    return True
        
        return False
    
    async def _install_missing_servers(self, missing_servers: List[str]) -> bool:
        """Install missing MCP servers"""
        all_success = True
        
        for server_id in missing_servers:
            self.console.print(f"\n🔧 Installing MCP server: [bold]{server_id}[/bold]")
            
            try:
                success = await self._install_single_server(server_id)
                if not success:
                    all_success = False
                    self.console.print(f"❌ Failed to install {server_id}")
            except Exception as e:
                all_success = False
                self.console.print(f"❌ Error installing {server_id}: {e}")
        
        return all_success
    
    async def _install_single_server(self, server_id: str) -> bool:
        """Install a single MCP server with user-provided configuration"""
        # Get suggested configuration
        suggested_config = suggest_mcp_config(server_id)
        
        if not suggested_config:
            self.console.print(f"❓ Unknown server: {server_id}")
            self.console.print("   Please add it manually with: [bold]ago mcp add[/bold]")
            return False
        
        self.console.print(f"📋 {suggested_config['description']}")
        
        command = suggested_config["command"]
        args = suggested_config["args"].copy()
        env_vars = {}
        description = suggested_config["description"]
        
        # Ask for additional command arguments
        if Confirm.ask("Add command arguments?", default=False):
            extra_args = Prompt.ask("Arguments (space-separated)", default="")
            if extra_args.strip():
                args.extend(extra_args.split())
        
        # Ask for environment variables
        if Confirm.ask("Add environment variables?", default=False):
            while True:
                env_name = Prompt.ask("Environment variable name (or press Enter to finish)", default="")
                if not env_name.strip():
                    break
                env_value = Prompt.ask(f"Value for {env_name}")
                env_vars[env_name] = env_value
        
        # Generate unique alias
        suggested_alias = server_id.split('/')[-1].replace('-', '_')
        alias = self._generate_unique_alias(suggested_alias)
        
        try:
            # Save configuration
            config_manager.add_server(alias, command, args, env_vars, description)
            self.console.print(f"✅ Installed as '[bold]{alias}[/bold]'")
            return True
            
        except Exception as e:
            self.console.print(f"❌ Installation failed: {e}")
            return False
    
    def _generate_unique_alias(self, suggested_alias: str) -> str:
        """Generate a unique alias for the server"""
        alias = suggested_alias
        counter = 1
        while registry.is_known_server(alias):
            alias = f"{suggested_alias}_{counter}"
            counter += 1
        return alias


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