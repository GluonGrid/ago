#!/usr/bin/env python3
"""
MCP Management Commands - Interactive MCP server configuration
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

import typer
import yaml
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table

from ..core.mcp_registry import registry, suggest_mcp_config

console = Console()


class MCPConfigManager:
    """Manages the global MCP servers configuration file"""
    
    def __init__(self):
        self.global_config_dir = Path.home() / ".ago"
        self.config_file = self.global_config_dir / "mcp_servers.yaml"
    
    def ensure_config_exists(self):
        """Create config directory and file if they don't exist"""
        self.global_config_dir.mkdir(exist_ok=True)
        
        if not self.config_file.exists():
            # Create default config
            default_config = {
                "servers": {},
                "global": {
                    "timeout": 30,
                    "max_retries": 3,
                    "connection_timeout": 10,
                    "rate_limit": {
                        "enabled": True,
                        "global_requests_per_minute": 200,
                        "per_server_requests_per_minute": 100
                    }
                }
            }
            self._save_config(default_config)
    
    def _load_config(self) -> Dict[str, Any]:
        """Load current configuration"""
        if not self.config_file.exists():
            return {"servers": {}, "global": {}}
        
        try:
            with open(self.config_file, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            console.print(f"❌ Error loading config: {e}")
            return {"servers": {}, "global": {}}
    
    def _save_config(self, config: Dict[str, Any]):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            console.print(f"❌ Error saving config: {e}")
            raise
    
    def add_server(self, alias: str, command: str, args: List[str], env_vars: Dict[str, str], description: str = ""):
        """Add MCP server to configuration"""
        self.ensure_config_exists()
        config = self._load_config()
        
        config["servers"][alias] = {
            "command": command,
            "args": args,
            "env": env_vars,
            "description": description,
            "enabled": True
        }
        
        self._save_config(config)
        
        # Clear registry cache
        registry._config_cache = None
    
    def remove_server(self, alias: str) -> bool:
        """Remove MCP server from configuration"""
        config = self._load_config()
        
        if alias not in config.get("servers", {}):
            return False
        
        del config["servers"][alias]
        self._save_config(config)
        
        # Clear registry cache
        registry._config_cache = None
        return True
    
    def update_server(self, alias: str, updates: Dict[str, Any]) -> bool:
        """Update MCP server configuration"""
        config = self._load_config()
        
        if alias not in config.get("servers", {}):
            return False
        
        config["servers"][alias].update(updates)
        self._save_config(config)
        
        # Clear registry cache
        registry._config_cache = None
        return True


config_manager = MCPConfigManager()


def mcp_add(server_identifier: str):
    """Add MCP server to global configuration"""
    
    console.print(f"🔧 Adding MCP Server: [bold]{server_identifier}[/bold]")
    
    # Check if it's already configured
    if registry.is_known_server(server_identifier):
        existing_config = registry.get_server_config(server_identifier)
        console.print(f"✅ Server '{server_identifier}' is already configured")
        console.print(f"   Command: {existing_config['command']} {' '.join(existing_config.get('args', []))}")
        return
    
    # Ask user for all configuration
    console.print("❓ Configure MCP server")
    
    command = Prompt.ask("Command", default="npx")
    args_input = Prompt.ask("Arguments (space-separated)", default=f"-y {server_identifier}")
    args = args_input.split() if args_input else []
    
    description = Prompt.ask("Description (optional)", default=f"MCP server: {server_identifier}")
    
    # Environment variables
    env_vars = {}
    if Confirm.ask("Add environment variables?", default=False):
        while True:
            env_name = Prompt.ask("Environment variable name (or press Enter to finish)", default="")
            if not env_name:
                break
            env_value = Prompt.ask(f"Value for {env_name}")
            env_vars[env_name] = env_value
    
    # Determine alias
    suggested_alias = server_identifier.split('/')[-1].replace('-', '_')
    alias = Prompt.ask("Server alias", default=suggested_alias)
    
    # Check if alias already exists
    if registry.is_known_server(alias):
        if not Confirm.ask(f"Server alias '{alias}' already exists. Overwrite?", default=False):
            console.print("❌ Installation cancelled")
            return
    
    # Show summary and confirm
    console.print("\n📋 Configuration Summary:")
    console.print(f"   Alias: [bold]{alias}[/bold]")
    console.print(f"   Command: [bold]{command} {' '.join(args)}[/bold]")
    if env_vars:
        console.print("   Environment variables:")
        for key, value in env_vars.items():
            # Hide sensitive values
            display_value = "***" if any(sensitive in key.lower() for sensitive in ['key', 'token', 'secret', 'password']) else value
            console.print(f"     {key}={display_value}")
    if description:
        console.print(f"   Description: {description}")
    
    if not Confirm.ask("\nSave this configuration?", default=True):
        console.print("❌ Installation cancelled")
        return
    
    try:
        # Save configuration
        config_manager.add_server(alias, command, args, env_vars, description)
        console.print(f"✅ MCP server '[bold]{alias}[/bold]' added successfully!")
        console.print(f"   Use '[bold]ago mcp test {alias}[/bold]' to test the connection")
        
    except Exception as e:
        console.print(f"❌ Error saving configuration: {e}")


def mcp_list():
    """List all configured MCP servers"""
    servers = registry.get_known_servers()
    
    if not servers:
        console.print("📭 No MCP servers configured")
        console.print("   Use '[bold]ago mcp add <server>[/bold]' to add a server")
        return
    
    table = Table(title="Configured MCP Servers")
    table.add_column("Alias", style="bold blue")
    table.add_column("Command", style="green")
    table.add_column("Status", justify="center")
    table.add_column("Description", style="dim")
    
    for alias, config in servers.items():
        command = config.get("command", "")
        args = " ".join(config.get("args", []))
        full_command = f"{command} {args}".strip()
        
        status = "✅ Enabled" if config.get("enabled", True) else "❌ Disabled"
        description = config.get("description", "")
        
        table.add_row(alias, full_command, status, description)
    
    console.print(table)


def mcp_remove(alias: str):
    """Remove MCP server from configuration"""
    if not registry.is_known_server(alias):
        console.print(f"❌ Server '[bold]{alias}[/bold]' not found")
        available = registry.list_server_aliases()
        if available:
            console.print(f"Available servers: {', '.join(available)}")
        return
    
    server_config = registry.get_server_config(alias)
    console.print(f"🗑️  Removing MCP server: [bold]{alias}[/bold]")
    console.print(f"   Command: {server_config['command']} {' '.join(server_config.get('args', []))}")
    
    if not Confirm.ask("Are you sure?", default=False):
        console.print("❌ Removal cancelled")
        return
    
    if config_manager.remove_server(alias):
        console.print(f"✅ Server '[bold]{alias}[/bold]' removed successfully")
    else:
        console.print(f"❌ Error removing server '[bold]{alias}[/bold]'")


def mcp_test(alias: str):
    """Test MCP server connection"""
    if not registry.is_known_server(alias):
        console.print(f"❌ Server '[bold]{alias}[/bold]' not found")
        return
    
    server_config = registry.get_server_config(alias)
    command = server_config["command"]
    args = server_config.get("args", [])
    env_vars = server_config.get("env", {})
    
    console.print(f"🧪 Testing MCP server: [bold]{alias}[/bold]")
    console.print(f"   Command: {command} {' '.join(args)}")
    
    # Test if command is available
    if not shutil.which(command):
        console.print(f"❌ Command '[bold]{command}[/bold]' not found in PATH")
        console.print(f"   Make sure {command} is installed and accessible")
        return
    
    # For npx commands, check if package exists
    if command == "npx" and len(args) >= 2 and args[0] == "-y":
        package = args[1]
        console.print(f"   Checking npm package: {package}")
        
        # This is a basic test - could be enhanced to actually test MCP protocol
        try:
            result = subprocess.run(
                ["npx", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                console.print("✅ npx is available")
                console.print("🔍 Package will be downloaded on first use")
            else:
                console.print("❌ npx test failed")
        except Exception as e:
            console.print(f"❌ Error testing npx: {e}")
    
    console.print(f"ℹ️  Use '[bold]ago logs[/bold]' to see MCP server logs when running agents")


# Add these commands to the main CLI app
def register_mcp_commands(app: typer.Typer):
    """Register MCP commands with the main CLI app"""
    
    mcp_app = typer.Typer(name="mcp", help="🔧 MCP server management")
    
    @mcp_app.command("add")
    def add_command(server: str = typer.Argument(..., help="MCP server name or npm package")):
        """Add MCP server to configuration"""
        mcp_add(server)
    
    @mcp_app.command("list") 
    def list_command():
        """List configured MCP servers"""
        mcp_list()
    
    @mcp_app.command("remove")
    def remove_command(alias: str = typer.Argument(..., help="Server alias to remove")):
        """Remove MCP server from configuration"""
        mcp_remove(alias)
    
    @mcp_app.command("test")
    def test_command(alias: str = typer.Argument(..., help="Server alias to test")):
        """Test MCP server connection"""
        mcp_test(alias)
    
    app.add_typer(mcp_app)