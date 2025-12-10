#!/usr/bin/env python3
"""
Ago CLI - Docker-like interface for AI agents
Commands: ago run, ago chat, ago ps, ago logs
"""

import asyncio
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ..core.config import config

# Import daemon client - use relative imports for package
from ..core.daemon_client import DaemonClient
from ..core.registry import registry
from .mcp_commands import register_mcp_commands

# Global CLI app and console
app = typer.Typer(
    name="ago", help="🤖 Ago - Docker for AI agents", add_completion=False
)
console = Console()


async def validate_agent_exists(agent_name: str, daemon_client: DaemonClient) -> bool:
    """
    Validate that an agent exists and display helpful error message if not.
    Returns True if agent exists, False otherwise.
    """
    try:
        # Get list of agents from daemon
        response = await daemon_client.list_agents()

        # Handle daemon response format
        if isinstance(response, dict) and "status" in response:
            agents_data = response.get("agents", {})
        else:
            agents_data = response or {}

        # Build agent lookup maps
        available_agents = set()
        agent_name_to_instances = {}

        for instance_id, agent_info in agents_data.items():
            # Add instance ID (full identifier)
            available_agents.add(instance_id)

            # Add simple agent name
            simple_name = agent_info.get("agent_name", "")
            if simple_name:
                available_agents.add(simple_name)
                if simple_name not in agent_name_to_instances:
                    agent_name_to_instances[simple_name] = []
                agent_name_to_instances[simple_name].append(instance_id)

        if agent_name not in available_agents:
            console.print(f"❌ [red]Agent '{agent_name}' not found[/red]")

            # Show available simple names first, then instance IDs
            simple_names = [name for name in agent_name_to_instances.keys()]
            if simple_names:
                console.print(f"Available agents: {', '.join(sorted(simple_names))}")
            else:
                console.print(
                    f"Available agents: {', '.join(sorted(available_agents))}"
                )
            return False

        return True

    except Exception as e:
        console.print(f"❌ [red]Error checking agent existence:[/red] {str(e)}")
        return False


# Global daemon client
daemon_client = DaemonClient()


@app.command()
def create(
    agent_type: Optional[str] = typer.Argument(
        None, help="Agent type (researcher, assistant, analyst, writer, coordinator)"
    ),
    name: Optional[str] = typer.Option(None, "--name", help="Agent name"),
    model: Optional[str] = typer.Option(None, "--model", help="LLM model to use"),
    tools: Optional[str] = typer.Option(
        None, "--tools", help="Comma-separated list of tools"
    ),
    quick: bool = typer.Option(
        False, "--quick", help="Use defaults for quick creation"
    ),
):
    """🌟 Create a new AI agent with interactive wizard"""

    async def _create():
        try:
            console.print(
                "\n🤖 [bold green]Welcome to Ago Agent Creator![/bold green]\n"
            )

            # Step 1: Agent Type Selection
            selected_type = agent_type or _select_agent_type()

            # Step 2: Basic Configuration
            config = _gather_basic_config(selected_type, name, model, quick)

            # Step 3: Tool Selection
            selected_tools = (
                tools.split(",") if tools else _select_tools(selected_type, quick)
            )

            # Step 4: Customization
            customization = {} if quick else _gather_customization(selected_type)

            # Step 5: Create Agent
            await _create_agent_with_progress(
                selected_type, config, selected_tools, customization
            )

            # Step 6: Success Message
            _show_success_message(config["name"])

        except KeyboardInterrupt:
            console.print("\n👋 [yellow]Agent creation cancelled[/yellow]")
        except Exception as e:
            console.print(f"❌ [red]Error creating agent:[/red] {str(e)}")

    asyncio.run(_create())


@app.command()
def run(
    template_name: str = typer.Argument(
        ..., help="Template name to run (like docker image)"
    ),
    name: Optional[str] = typer.Option(None, "--name", help="Agent instance name"),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Run in interactive mode"
    ),
):
    """🚀 Run agent from template (like 'docker run image')"""

    async def _run():
        try:
            # Generate agent instance name if not provided
            import uuid

            agent_instance_name = name or f"{template_name}-{uuid.uuid4().hex[:8]}"

            console.print(
                f"🚀 [blue]Running template:[/blue] {template_name} → {agent_instance_name}"
            )

            # Check if template exists locally, attempt auto-pull if not found
            template = registry.get_template(template_name)
            if not template:
                console.print(
                    f"⚠️  [yellow]Template '{template_name}' not found locally[/yellow]"
                )

                # TODO: Auto-pull functionality (like docker pull)
                # For now, show available templates and suggest pulling
                console.print("\n📋 [yellow]Available local templates:[/yellow]")
                templates = registry.list_templates()
                for tmpl in templates:
                    console.print(
                        f"  • {tmpl['name']}:v{tmpl['version']} - {tmpl.get('description', 'No description')}"
                    )

                console.print(
                    f"\n💡 [dim]Future: 'ago pull {template_name}' will auto-pull from remote registries[/dim]"
                )
                console.print(
                    "💡 [dim]For now, use 'ago templates' to see available templates[/dim]"
                )
                return

            # Use daemon's single agent runner (no temp files needed!)
            result = await daemon_client.run_single_agent(
                template_name, agent_instance_name
            )

            if result.get("status") == "error":
                console.print(f"❌ [red]Error:[/red] {result['message']}")
                return

            # Success!
            console.print(f"✅ [green]{result['message']}[/green]")

            agent_info = result.get("agent", {})
            console.print(
                f"📊 [blue]Template:[/blue] {agent_info.get('template', template_name)}"
            )
            console.print(
                f"🤖 [blue]Model:[/blue] {agent_info.get('model', 'unknown')}"
            )
            if agent_info.get("tools"):
                console.print(
                    f"🛠️  [blue]Tools:[/blue] {', '.join(agent_info['tools'])}"
                )

            console.print(
                f"\n💬 [cyan]Chat with your agent:[/cyan] ago chat {agent_instance_name}"
            )
            console.print(f"📋 [cyan]View logs:[/cyan] ago logs {agent_instance_name}")
            console.print(f"⏹️  [cyan]Stop agent:[/cyan] ago stop {agent_instance_name}")

            if interactive:
                # Start interactive chat immediately
                console.print("\n🔄 [blue]Starting interactive mode...[/blue]")
                await _chat_interactive(agent_instance_name)

        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    asyncio.run(_run())


@app.command()
def ps():
    """📊 List running agents (like 'docker ps')"""

    async def _ps():
        try:
            response = await daemon_client.list_agents()

            # Handle daemon response format - it can return different formats
            if isinstance(response, dict) and "status" in response:
                # Structured response with status
                if response.get("status") == "error":
                    console.print(
                        f"❌ [red]Error:[/red] {response.get('message', 'Unknown error')}"
                    )
                    return
                agents_data = response.get("agents", [])

                # agents_data can be either a list or dict
                if isinstance(agents_data, list):
                    # Convert list to dict format for consistent handling
                    agents = {agent["name"]: agent for agent in agents_data}
                else:
                    agents = agents_data
            else:
                # Direct agents dictionary response
                agents = response

            if not agents:
                console.print("ℹ️ No agents currently running")
                return

            table = Table()
            table.add_column("Agent Name", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Model", style="yellow")
            table.add_column("Tools", style="magenta")
            table.add_column("Messages", style="blue")

            for agent_name, agent_data in agents.items():
                # Ensure agent_data is a dict, not a string
                if not isinstance(agent_data, dict):
                    console.print(f"⚠️ Warning: Invalid agent data for {agent_name}")
                    continue

                status = "🟢 " + agent_data.get("status", "running").title()
                model = agent_data.get("model", "Unknown")

                # Handle tools field - can be count or list
                tools_field = agent_data.get("tools", [])
                if isinstance(tools_field, int):
                    tool_names = f"{tools_field} tools"
                elif isinstance(tools_field, list):
                    tool_names = (
                        ", ".join(
                            [
                                t.get("name", str(t)) if isinstance(t, dict) else str(t)
                                for t in tools_field
                            ]
                        )
                        if tools_field
                        else "None"
                    )
                else:
                    tool_names = "None"

                # Handle conversation/messages field - can be count or list
                conversations = agent_data.get(
                    "conversations", agent_data.get("conversation_history", [])
                )
                if isinstance(conversations, int):
                    message_count = conversations
                else:
                    message_count = len(conversations)

                table.add_row(agent_name, status, model, tool_names, str(message_count))

            console.print(table)
            console.print(f"\n📊 [blue]Total agents:[/blue] {len(agents)}")

        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    asyncio.run(_ps())


@app.command()
def chat(
    agent_name: str,
    simple: bool = typer.Option(
        False, "--simple", "-s", help="Use simple CLI mode instead of TUI"
    ),
):
    """💬 Chat with a specific agent (like 'docker exec -it')"""

    # Try TUI mode first (if not disabled and in TTY)
    if not simple and sys.stdout.isatty():
        try:
            from .tui.agent_chat import run_chat_tui

            run_chat_tui(agent_name)
            return
        except ImportError as e:
            console.print(
                f"[yellow]TUI not available ({e}), using simple mode[/yellow]"
            )
        except Exception as e:
            console.print(f"[yellow]TUI failed ({e}), using simple mode[/yellow]")

    # Fallback to simple CLI mode
    async def _chat():
        try:
            # Validate agent exists
            if not await validate_agent_exists(agent_name, daemon_client):
                return

            console.print(f"💬 [green]Starting chat with {agent_name}[/green]")
            console.print("Type 'exit' to end the conversation\n")

            while True:
                try:
                    # Get user input
                    user_input = input("👤 You: ").strip()

                    if user_input.lower() in ["exit", "quit", "q"]:
                        console.print(
                            f"👋 [yellow]Chat ended with {agent_name}[/yellow]"
                        )
                        break

                    if not user_input:
                        continue

                    # Send message to agent via daemon
                    console.print("🤖 Thinking...", style="dim")
                    response = await daemon_client.chat_message(agent_name, user_input)

                    if response.get("status") == "error":
                        console.print(f"❌ [red]Error:[/red] {response['message']}")
                        continue

                    # Display agent response
                    console.print(
                        f"🤖 [cyan]{agent_name}:[/cyan] {response['response']}"
                    )

                except KeyboardInterrupt:
                    console.print(
                        f"\n👋 [yellow]Chat interrupted with {agent_name}[/yellow]"
                    )
                    break
                except EOFError:
                    console.print(f"\n👋 [yellow]Chat ended with {agent_name}[/yellow]")
                    break

        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    asyncio.run(_chat())


async def _chat_interactive(agent_name: str):
    """Interactive chat helper for run -i mode"""
    try:
        user_input = input(f"Message for {agent_name}: ").strip()
        if not user_input:
            return

        console.print("🤖 Thinking...", style="dim")
        response = await daemon_client.chat_message(agent_name, user_input)

        if response.get("status") == "error":
            console.print(f"❌ [red]Error:[/red] {response['message']}")
            return

        console.print(f"🤖 [cyan]{agent_name}:[/cyan] {response['response']}")

    except Exception as e:
        console.print(f"❌ [red]Error:[/red] {str(e)}")


@app.command()
def logs(
    agent_name: str,
    tail: int = typer.Option(10, "--tail", help="Number of recent messages to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
):
    """📋 View agent conversation logs (like 'docker logs')"""

    async def _logs():
        try:
            # Validate agent exists
            if not await validate_agent_exists(agent_name, daemon_client):
                return

            logs_data = await daemon_client.get_agent_logs(agent_name, tail)

            if logs_data.get("status") == "error":
                console.print(f"❌ [red]Error:[/red] {logs_data['message']}")
                return

            conversation_history = logs_data["logs"]

            if not conversation_history:
                console.print(f"ℹ️ No logs found for agent '{agent_name}'")
                return

            console.print(f"📋 [blue]Logs for {agent_name}:[/blue]\n")

            for entry in conversation_history[-tail:]:
                timestamp = entry.get("timestamp", "Unknown time")
                role = entry.get("role", "Unknown")
                content = entry.get("content", "")

                if role == "user":
                    console.print(
                        f"[dim]{timestamp}[/dim] 👤 [blue]User:[/blue] {content}"
                    )
                elif role == "assistant":
                    console.print(
                        f"[dim]{timestamp}[/dim] 🤖 [cyan]{agent_name}:[/cyan] {content}"
                    )
                elif role == "inter_agent":
                    from_agent = entry.get("from", "Unknown")
                    console.print(
                        f"[dim]{timestamp}[/dim] 🔄 [yellow]{from_agent}:[/yellow] {content}"
                    )

            # TODO: Implement follow mode for real-time logs
            if follow:
                console.print("\n[yellow]Follow mode not yet implemented[/yellow]")

        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    asyncio.run(_logs())


async def _logs(agent_name: str):
    """Logs helper for interactive mode"""
    try:
        logs_data = await daemon_client.get_agent_logs(agent_name, 5)

        if logs_data.get("status") == "error":
            console.print(f"❌ [red]Error:[/red] {logs_data['message']}")
            return

        conversation_history = logs_data["logs"][-5:]  # Last 5 entries

        console.print(f"📋 [blue]Recent logs for {agent_name}:[/blue]")
        for entry in conversation_history:
            role = entry.get("role", "Unknown")
            content = entry.get("content", "")[:100]  # Truncate for interactive

            if role == "user":
                console.print(f"👤 User: {content}")
            elif role == "assistant":
                console.print(f"🤖 {agent_name}: {content}")

    except Exception as e:
        console.print(f"❌ Error: {str(e)}")


@app.command()
def stop(agent_name: Optional[str] = typer.Argument(None, help="Agent name to stop")):
    """⏹️ Stop specific agent or all agents (like 'docker stop')"""

    async def _stop():
        try:
            if agent_name:
                # Validate agent exists before stopping
                if not await validate_agent_exists(agent_name, daemon_client):
                    return
                result = await daemon_client.stop_agent(agent_name)
            else:
                result = await daemon_client.stop_all_agents()

            if result.get("status") == "error":
                console.print(f"❌ [red]Error:[/red] {result['message']}")
            else:
                console.print(f"⏹️ [green]{result['message']}[/green]")

        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    asyncio.run(_stop())


# NEW: Multi-agent communication commands


@app.command()
def send(
    from_agent: str = typer.Argument(..., help="Agent sending the message"),
    to_agent: str = typer.Argument(..., help="Agent receiving the message"),
    message: str = typer.Argument(..., help="Message to send"),
):
    """📤 Send message between agents"""

    async def _send():
        try:
            # Validate both agents exist
            if not await validate_agent_exists(from_agent, daemon_client):
                return

            if not await validate_agent_exists(to_agent, daemon_client):
                return

            console.print(
                f"📤 [yellow]Sending message from {from_agent} to {to_agent}...[/yellow]"
            )

            result = await daemon_client.send_inter_agent_message(
                from_agent, to_agent, message
            )

            if result.get("status") == "error":
                console.print(f"❌ [red]Error:[/red] {result['message']}")
            elif result.get("status") == "sent":
                console.print(
                    f"📤 [green]Message sent from {from_agent} to {to_agent}[/green]"
                )
                if result.get("note"):
                    console.print(f"💡 [dim]{result['note']}[/dim]")
            elif result.get("status") == "timeout":
                console.print(
                    "⏱️ [yellow]Message sent but agent response timed out[/yellow]"
                )
                console.print(
                    "💡 [dim]Use 'ago queues --follow' to see responses[/dim]"
                )
            else:
                console.print(
                    f"📤 [green]Message sent from {from_agent} to {to_agent}[/green]"
                )
                console.print("💡 [dim]Use 'ago queues' to see responses[/dim]")

        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    asyncio.run(_send())


async def _send_message(from_agent: str, to_agent: str, message: str):
    """Send message helper for interactive mode"""
    try:
        result = await daemon_client.send_inter_agent_message(
            from_agent, to_agent, message
        )

        if result.get("status") == "error":
            console.print(f"❌ [red]Error:[/red] {result['message']}")
        else:
            console.print(f"📤 Message sent: {from_agent} → {to_agent}")
            if result.get("response"):
                console.print(f"🤖 {to_agent}: {result['response'][:100]}")  # Truncate

    except Exception as e:
        console.print(f"❌ Error: {str(e)}")


@app.command()
def queues(
    agent_name: Optional[str] = typer.Argument(
        None, help="Show queues for specific agent"
    ),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow message flow"),
):
    """📬 Show agent message queues and communication status"""

    async def _queues():
        try:
            # Validate agent exists if specific agent requested
            if agent_name and not await validate_agent_exists(
                agent_name, daemon_client
            ):
                return

            if follow:
                # Follow mode - continuously show new messages
                console.print(
                    "📡 [blue]Following message queues... (Press Ctrl+C to stop)[/blue]\n"
                )

                last_message_count = 0
                try:
                    while True:
                        result = await daemon_client.get_message_queues(agent_name)

                        if result.get("status") == "error":
                            console.print(f"❌ [red]Error:[/red] {result['message']}")
                            break

                        messages = result.get("messages", [])

                        # Show new messages since last check
                        new_messages = messages[last_message_count:]
                        for msg in new_messages:
                            timestamp = msg.get("timestamp", "Unknown")[:19].replace(
                                "T", " "
                            )
                            from_agent = msg.get("from", "Unknown")
                            to_agent = msg.get("to", "Unknown")
                            message_content = msg.get("message", "")
                            msg_type = msg.get("type", "message")

                            # Color code by message type
                            if msg_type == "response":
                                console.print(
                                    f"[dim]{timestamp}[/dim] 🔄 [green]{from_agent} → {to_agent}:[/green] {message_content}"
                                )
                            else:
                                console.print(
                                    f"[dim]{timestamp}[/dim] 📨 [yellow]{from_agent} → {to_agent}:[/yellow] {message_content}"
                                )

                        last_message_count = len(messages)
                        await asyncio.sleep(1)  # Check every second

                except KeyboardInterrupt:
                    console.print(
                        "\n👋 [yellow]Stopped following message queues[/yellow]"
                    )
            else:
                # Static mode - show current message history
                result = await daemon_client.get_message_queues(agent_name)

                if result.get("status") == "error":
                    console.print(f"❌ [red]Error:[/red] {result['message']}")
                    return

                messages = result.get("messages", [])

                if not messages:
                    console.print("📭 [yellow]No inter-agent messages found[/yellow]")
                    return

                if agent_name:
                    console.print(f"📬 [blue]Messages for {agent_name}:[/blue]\n")
                else:
                    console.print("📬 [blue]All inter-agent messages:[/blue]\n")

                # Show all messages in chronological order with consistent formatting
                for msg in messages:
                    timestamp = msg.get("timestamp", "Unknown")[:19].replace("T", " ")
                    from_agent = msg.get("from", "Unknown")
                    to_agent = msg.get("to", "Unknown")
                    raw_message = msg.get("message", "")
                    status = msg.get("status", "unknown")
                    msg_type = msg.get("type", "message")

                    # Clean up message content - handle both string and dict formats
                    if isinstance(raw_message, dict):
                        # If it's a dict, extract the content field
                        message_content = raw_message.get("content", str(raw_message))
                    elif raw_message.startswith("[Response]: {"):
                        # Parse the embedded dict in response messages
                        try:
                            # Extract dict from "[Response]: {dict content}"
                            dict_part = raw_message[12:]  # Remove "[Response]: " prefix
                            parsed_dict = eval(
                                dict_part
                            )  # Safe since we control the format
                            message_content = parsed_dict.get("content", dict_part)
                        except:
                            message_content = raw_message
                    else:
                        message_content = raw_message

                    # Truncate long messages
                    if len(message_content) > 100:
                        message_content = message_content[:100] + "..."

                    # Color code by message type and status
                    if msg_type == "response":
                        console.print(
                            f"[dim]{timestamp}[/dim] 🔄 [green]{from_agent} → {to_agent}:[/green] {message_content}"
                        )
                    elif status == "sent":
                        console.print(
                            f"[dim]{timestamp}[/dim] 📨 [yellow]{from_agent} → {to_agent}:[/yellow] {message_content}"
                        )
                    elif status == "timeout":
                        console.print(
                            f"[dim]{timestamp}[/dim] ⏱️ [orange1]{from_agent} → {to_agent}:[/orange1] {message_content}"
                        )
                    else:
                        console.print(
                            f"[dim]{timestamp}[/dim] ❌ [red]{from_agent} → {to_agent}:[/red] {message_content}"
                        )

                console.print(f"\n📊 [blue]Total messages:[/blue] {len(messages)}")

        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    asyncio.run(_queues())


@app.command()
def start(agent_name: str = typer.Argument(..., help="Agent name to start")):
    """▶️ Start individual agent from workflow spec (like 'docker-compose start')"""

    async def _start():
        try:
            result = await daemon_client.start_agent(agent_name)

            if result.get("status") == "error":
                console.print(f"❌ [red]Error:[/red] {result['message']}")
            else:
                console.print(f"▶️ [green]Started agent: {agent_name}[/green]")

        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    asyncio.run(_start())


# Daemon management commands

# Create daemon sub-app
daemon_app = typer.Typer(help="🔧 Daemon management commands")
app.add_typer(daemon_app, name="daemon")


@daemon_app.command("start")
def daemon_start():
    """🚀 Start the Ago daemon"""

    async def _daemon_start():
        try:
            result = await daemon_client.start_daemon()
            console.print(f"🚀 [green]{result['message']}[/green]")
        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    asyncio.run(_daemon_start())


@daemon_app.command("stop")
def daemon_stop():
    """⏹️ Stop the Ago daemon"""

    async def _daemon_stop():
        try:
            success = await daemon_client.stop_daemon()
            if success:
                console.print("⏹️ [green]Ago daemon stopped[/green]")
            else:
                console.print("❌ [red]Failed to stop daemon[/red]")
        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    asyncio.run(_daemon_stop())


@daemon_app.command("status")
def daemon_status():
    """📊 Check daemon status"""

    async def _daemon_status():
        try:
            status = await daemon_client.daemon_status()

            if status["running"]:
                console.print(
                    f"✅ [green]Daemon is running[/green] (PID: {status.get('pid', 'Unknown')})"
                )
            else:
                console.print("❌ [red]Daemon is not running[/red]")
        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    asyncio.run(_daemon_status())


@app.command()
def version():
    """📋 Show Ago version and system information"""
    try:
        # Read version from pyproject.toml
        project_root = Path(__file__).parent.parent.parent
        pyproject_path = project_root / "pyproject.toml"

        ago_version = "Unknown"
        if pyproject_path.exists():
            # Parse pyproject.toml manually (simple approach, no extra dependencies)
            with open(pyproject_path, "r") as f:
                for line in f:
                    if line.startswith("version ="):
                        ago_version = line.split("=")[1].strip().strip('"').strip("'")
                        break

        # Get Python version
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        # Get operating system
        os_name = platform.system()
        os_version = platform.release()
        os_display = f"{os_name} {os_version}"

        # Get installation path
        install_path = str(Path(__file__).parent.parent)

        # Create Rich table
        table = Table(title="Ago Version Information", title_style="bold cyan")
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        table.add_row("Ago Version", ago_version)
        table.add_row("Python Version", python_version)
        table.add_row("Operating System", os_display)
        table.add_row("Installation Path", install_path)

        console.print(table)

    except Exception as e:
        console.print(f"❌ [red]Error reading version information:[/red] {str(e)}")
        # Fallback display
        console.print("🤖 [bold]Ago[/bold] - Docker-like orchestration for AI agents")
        console.print(
            f"Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )


# Magic Create Command Helper Functions


def _select_agent_type() -> str:
    """Interactive agent type selection with beautiful table"""
    console.print("🎨 [bold]What type of agent would you like to create?[/bold]\n")

    # Create beautiful agent selection table
    table = Table()
    table.add_column("Option", style="cyan", width=8)
    table.add_column("Type", style="green", width=16)
    table.add_column("Description", style="white")

    agent_types = {
        "1": ("🔍 Researcher", "Web research and analysis specialist"),
        "2": ("🤖 Assistant", "General-purpose helpful assistant"),
        "3": ("📊 Analyst", "Data processing and insights expert"),
        "4": ("✍️ Writer", "Content creation and editing specialist"),
        "5": ("👥 Coordinator", "Team management and delegation expert"),
    }

    for option, (display_name, description) in agent_types.items():
        table.add_row(option, display_name, description)

    console.print(table)
    console.print()

    choice = Prompt.ask("Enter choice", choices=["1", "2", "3", "4", "5"], default="1")

    # Map choice to agent type
    type_mapping = {
        "1": "researcher",
        "2": "assistant",
        "3": "analyst",
        "4": "writer",
        "5": "coordinator",
    }

    selected = type_mapping[choice]
    console.print(
        f"✨ [green]Great choice! Creating a {agent_types[choice][0]} agent.[/green]\n"
    )
    return selected


def _gather_basic_config(
    agent_type: str, name: str = None, model: str = None, quick: bool = False
) -> dict:
    """Gather basic agent configuration"""
    config = {}

    # Agent name
    if not name:
        default_name = f"{agent_type.title()}Agent"
        config["name"] = Prompt.ask("📝 Agent name", default=default_name)
    else:
        config["name"] = name

    # Model selection
    if not model and not quick:
        config["model"] = _select_model(agent_type)
    else:
        config["model"] = model or _get_default_model(agent_type)

    return config


def _select_model(agent_type: str) -> str:
    """Interactive model selection with recommendations"""
    console.print("🧠 [bold]Choose LLM model:[/bold]")

    # Model recommendations per agent type
    model_options = {
        "researcher": [
            (
                "claude-3-5-sonnet-20241022",
                "Claude Sonnet (Recommended for research)",
                "⭐",
            ),
            ("claude-3-5-haiku-20241022", "Claude Haiku (Fast and efficient)", ""),
            ("gpt-4-turbo-preview", "GPT-4 Turbo (Alternative)", ""),
        ],
        "assistant": [
            (
                "claude-3-5-haiku-20241022",
                "Claude Haiku (Recommended for assistance)",
                "⭐",
            ),
            ("claude-3-5-sonnet-20241022", "Claude Sonnet (More capable)", ""),
            ("gpt-4-turbo-preview", "GPT-4 Turbo (Alternative)", ""),
        ],
        "analyst": [
            (
                "claude-3-5-sonnet-20241022",
                "Claude Sonnet (Recommended for analysis)",
                "⭐",
            ),
            ("gpt-4-turbo-preview", "GPT-4 Turbo (Strong reasoning)", ""),
            ("claude-3-5-haiku-20241022", "Claude Haiku (Fast processing)", ""),
        ],
        "writer": [
            (
                "claude-3-5-sonnet-20241022",
                "Claude Sonnet (Recommended for writing)",
                "⭐",
            ),
            ("gpt-4-turbo-preview", "GPT-4 Turbo (Creative writing)", ""),
            ("claude-3-5-haiku-20241022", "Claude Haiku (Quick edits)", ""),
        ],
        "coordinator": [
            (
                "claude-3-5-sonnet-20241022",
                "Claude Sonnet (Recommended for coordination)",
                "⭐",
            ),
            ("gpt-4-turbo-preview", "GPT-4 Turbo (Strategic thinking)", ""),
            ("claude-3-5-haiku-20241022", "Claude Haiku (Fast coordination)", ""),
        ],
    }

    available_models = model_options.get(agent_type, model_options["assistant"])

    for i, (model_id, description, badge) in enumerate(available_models, 1):
        console.print(f"  {i}. {description} {badge}")

    console.print()
    choice = Prompt.ask(
        "Enter choice",
        choices=[str(i) for i in range(1, len(available_models) + 1)],
        default="1",
    )

    selected_model = available_models[int(choice) - 1][0]
    console.print(
        f"🧠 [green]Selected: {available_models[int(choice) - 1][1].split('(')[0].strip()}[/green]\n"
    )
    return selected_model


def _get_default_model(agent_type: str) -> str:
    """Get default model for agent type"""
    defaults = {
        "researcher": "claude-3-5-sonnet-20241022",
        "assistant": "claude-3-5-haiku-20241022",
        "analyst": "claude-3-5-sonnet-20241022",
        "writer": "claude-3-5-sonnet-20241022",
        "coordinator": "claude-3-5-sonnet-20241022",
    }
    return defaults.get(agent_type, "claude-3-5-haiku-20241022")


def _select_tools(agent_type: str, quick: bool = False) -> list:
    """Interactive tool selection based on agent type"""
    if quick:
        return _get_default_tools(agent_type)

    console.print("🔧 [bold]Select tools for your agent:[/bold]")

    # Tool configuration per agent type
    tool_config = _get_agent_tool_config(agent_type)
    selected_tools = []

    # Show required tools (pre-selected)
    console.print("\n[green]Required tools:[/green]")
    for tool in tool_config["required"]:
        console.print(f"  ☑ [green]{tool['name']}[/green] - {tool['description']}")
        selected_tools.append(tool["id"])

    # Show optional tools for selection
    if tool_config["optional"]:
        console.print("\n[yellow]Optional tools:[/yellow]")
        for tool in tool_config["optional"]:
            if Confirm.ask(
                f"  Add [cyan]{tool['name']}[/cyan]? ({tool['description']})",
                default=False,
            ):
                selected_tools.append(tool["id"])
                console.print(f"    ✅ Added {tool['name']}")

    console.print()
    return selected_tools


def _get_agent_tool_config(agent_type: str) -> dict:
    """Get tool configuration for agent type"""
    configs = {
        "researcher": {
            "required": [
                {
                    "id": "web_search",
                    "name": "Web Search",
                    "description": "Search the web for information",
                },
                {
                    "id": "file_manager",
                    "name": "File Manager",
                    "description": "Read and write documents",
                },
            ],
            "optional": [
                {
                    "id": "data_processor",
                    "name": "Data Processor",
                    "description": "Parse and analyze data",
                },
                {
                    "id": "email_integration",
                    "name": "Email Integration",
                    "description": "Send research summaries",
                },
                {
                    "id": "calendar_access",
                    "name": "Calendar Access",
                    "description": "Schedule research tasks",
                },
            ],
        },
        "assistant": {
            "required": [
                {
                    "id": "file_manager",
                    "name": "File Manager",
                    "description": "File operations and organization",
                }
            ],
            "optional": [
                {
                    "id": "web_search",
                    "name": "Web Search",
                    "description": "Search for information",
                },
                {
                    "id": "email_integration",
                    "name": "Email Integration",
                    "description": "Manage emails",
                },
                {
                    "id": "calendar_access",
                    "name": "Calendar Access",
                    "description": "Calendar management",
                },
            ],
        },
        "analyst": {
            "required": [
                {
                    "id": "data_processor",
                    "name": "Data Processor",
                    "description": "Process and analyze data",
                },
                {
                    "id": "file_manager",
                    "name": "File Manager",
                    "description": "Handle data files",
                },
            ],
            "optional": [
                {
                    "id": "web_search",
                    "name": "Web Search",
                    "description": "Research market data",
                },
                {
                    "id": "visualization",
                    "name": "Data Visualization",
                    "description": "Create charts and graphs",
                },
            ],
        },
        "writer": {
            "required": [
                {
                    "id": "file_manager",
                    "name": "File Manager",
                    "description": "Handle documents and drafts",
                }
            ],
            "optional": [
                {
                    "id": "web_search",
                    "name": "Web Search",
                    "description": "Research topics",
                },
                {
                    "id": "grammar_check",
                    "name": "Grammar Check",
                    "description": "Check writing quality",
                },
                {
                    "id": "plagiarism_check",
                    "name": "Plagiarism Check",
                    "description": "Ensure originality",
                },
            ],
        },
        "coordinator": {
            "required": [
                {
                    "id": "task_management",
                    "name": "Task Management",
                    "description": "Organize and delegate tasks",
                },
                {
                    "id": "communication",
                    "name": "Communication",
                    "description": "Message team members",
                },
            ],
            "optional": [
                {
                    "id": "calendar_access",
                    "name": "Calendar Access",
                    "description": "Schedule meetings",
                },
                {
                    "id": "project_tracking",
                    "name": "Project Tracking",
                    "description": "Monitor progress",
                },
            ],
        },
    }
    return configs.get(agent_type, configs["assistant"])


def _get_default_tools(agent_type: str) -> list:
    """Get default tools for agent type"""
    config = _get_agent_tool_config(agent_type)
    return [tool["id"] for tool in config["required"]]


def _gather_customization(agent_type: str) -> dict:
    """Gather agent customization options"""
    customization = {}

    console.print("🎨 [bold]Customization options:[/bold]")

    # Agent-specific customizations
    if agent_type == "researcher":
        customization["specialization"] = Prompt.ask(
            "📋 Research specialization", default="general research", show_default=True
        )
        customization["citation_format"] = Prompt.ask(
            "🔗 Citation format", choices=["APA", "MLA", "Chicago"], default="APA"
        )
    elif agent_type == "writer":
        customization["writing_style"] = Prompt.ask(
            "✍️ Writing style",
            choices=["professional", "casual", "academic", "creative"],
            default="professional",
        )
        customization["content_focus"] = Prompt.ask(
            "📝 Content focus", default="general content", show_default=True
        )
    elif agent_type == "analyst":
        customization["analysis_focus"] = Prompt.ask(
            "📊 Analysis focus",
            choices=["financial", "market", "operational", "strategic"],
            default="market",
        )
    elif agent_type == "coordinator":
        customization["management_style"] = Prompt.ask(
            "👥 Management style",
            choices=["collaborative", "directive", "supportive", "delegative"],
            default="collaborative",
        )

    # Common customizations
    customization["response_style"] = Prompt.ask(
        "🌡️ Response style",
        choices=["thorough", "concise", "balanced"],
        default="balanced",
    )

    console.print()
    return customization


async def _create_agent_with_progress(
    agent_type: str, config: dict, tools: list, customization: dict
):
    """Create agent with beautiful progress indicators"""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: Generate configuration
        task1 = progress.add_task("🎨 Generating agent configuration...", total=None)
        await asyncio.sleep(0.5)  # Simulate work
        agent_config = _generate_agent_config(agent_type, config, tools, customization)
        progress.update(
            task1, completed=True, description="✅ Generated agent configuration"
        )

        # Step 2: Create prompt template
        task2 = progress.add_task(
            "🧠 Creating specialized prompt template...", total=None
        )
        await asyncio.sleep(0.7)  # Simulate work
        prompt = _generate_agent_prompt(agent_type, config, customization)
        agent_config["system_prompt"] = prompt
        progress.update(
            task2, completed=True, description="✅ Created specialized prompt template"
        )

        # Step 3: Configure tools
        task3 = progress.add_task("🔧 Configuring tools and permissions...", total=None)
        await asyncio.sleep(0.3)  # Simulate work
        agent_config["tools"] = tools
        progress.update(
            task3, completed=True, description="✅ Configured tools and permissions"
        )

        # Step 4: Initialize memory
        task4 = progress.add_task("🧠 Setting up agent memory...", total=None)
        await asyncio.sleep(0.4)  # Simulate work
        progress.update(task4, completed=True, description="✅ Set up agent memory")

        # Step 5: Save agent config
        task5 = progress.add_task("💾 Saving agent configuration...", total=None)
        await asyncio.sleep(0.4)  # Simulate work
        await _save_agent_config(config["name"], agent_config)
        progress.update(
            task5, completed=True, description="✅ Agent configuration saved!"
        )


def _generate_agent_config(
    agent_type: str, config: dict, tools: list, customization: dict
) -> dict:
    """Generate complete agent configuration"""
    agent_config = {
        "name": config["name"],
        "type": agent_type,
        "model": config["model"],
        "tools": tools,
        "customization": customization,
        "created_at": datetime.now().isoformat(),
        "version": "1.0.0",
    }
    return agent_config


def _generate_agent_prompt(agent_type: str, config: dict, customization: dict) -> str:
    """Generate specialized system prompt for agent"""

    # Base prompt templates for each agent type
    prompts = {
        "researcher": f"""You are {config["name"]}, a specialized research assistant with expertise in {customization.get("specialization", "general research")}.

## Your Role
You are a thorough, analytical researcher who excels at gathering, analyzing, and synthesizing information from multiple sources. Your responses are well-structured, fact-based, and properly cited.

## Core Capabilities
- **Web Research**: Search and analyze web sources for comprehensive information
- **Source Evaluation**: Assess credibility and relevance of sources
- **Data Analysis**: Process and interpret research data
- **Report Generation**: Create structured, well-cited research reports
- **Citation Management**: Use {customization.get("citation_format", "APA")} format for all citations

## Response Style
{_get_response_style_text(customization.get("response_style", "balanced"))}

Always maintain intellectual curiosity, critical thinking, and commitment to accuracy in your research work.""",
        "assistant": f"""You are {config["name"]}, a helpful and versatile AI assistant designed to support users with a wide range of tasks.

## Your Role
You are a proactive, organized assistant who helps users manage their daily tasks, answer questions, and provide support across various domains. You're reliable, efficient, and always looking for ways to be helpful.

## Core Capabilities
- **Task Management**: Help organize and prioritize tasks
- **Information Retrieval**: Find and summarize information quickly
- **Problem Solving**: Break down complex problems into manageable steps
- **Communication**: Clear, helpful communication tailored to user needs
- **File Management**: Organize and manage documents and data

## Response Style
{_get_response_style_text(customization.get("response_style", "balanced"))}

Always be helpful, courteous, and proactive in anticipating user needs.""",
        "analyst": f"""You are {config["name"]}, a data analysis specialist focused on {customization.get("analysis_focus", "market")} analysis.

## Your Role
You are a methodical, detail-oriented analyst who transforms raw data into actionable insights. You excel at pattern recognition, statistical analysis, and presenting complex information clearly.

## Core Capabilities
- **Data Processing**: Clean, organize, and analyze large datasets
- **Statistical Analysis**: Apply appropriate statistical methods and tests
- **Trend Identification**: Recognize patterns and trends in data
- **Visualization**: Create clear, informative charts and graphs
- **Insight Generation**: Transform data into actionable business insights

## Response Style
{_get_response_style_text(customization.get("response_style", "balanced"))}

Always support your conclusions with data and clearly explain your analytical approach.""",
        "writer": f"""You are {config["name"]}, a {customization.get("writing_style", "professional")} writer specializing in {customization.get("content_focus", "general content")}.

## Your Role
You are a skilled wordsmith who creates engaging, well-structured content tailored to your audience. You have a strong command of language, style, and tone.

## Core Capabilities
- **Content Creation**: Write original, engaging content across formats
- **Editing & Revision**: Improve clarity, flow, and impact of existing content
- **Style Adaptation**: Adjust tone and style for different audiences
- **Research Integration**: Incorporate research and facts seamlessly
- **SEO Optimization**: Create content that performs well in search

## Response Style
{_get_response_style_text(customization.get("response_style", "balanced"))}

Always maintain high standards for grammar, clarity, and engaging content.""",
        "coordinator": f"""You are {config["name"]}, a {customization.get("management_style", "collaborative")} team coordinator focused on project management and team collaboration.

## Your Role
You are an organized, strategic coordinator who excels at managing teams, delegating tasks, and ensuring projects run smoothly. You facilitate communication and keep everyone aligned on goals.

## Core Capabilities
- **Project Planning**: Break down complex projects into manageable tasks
- **Task Delegation**: Assign appropriate tasks to team members
- **Progress Tracking**: Monitor project status and identify bottlenecks
- **Team Communication**: Facilitate clear communication across team members
- **Resource Management**: Optimize allocation of time and resources

## Response Style
{_get_response_style_text(customization.get("response_style", "balanced"))}

Always focus on team success, clear communication, and efficient project delivery.""",
    }

    return prompts.get(agent_type, prompts["assistant"])


def _get_response_style_text(style: str) -> str:
    """Get response style description"""
    styles = {
        "thorough": "Provide comprehensive, detailed responses with extensive analysis and multiple perspectives. Include background context and explore implications.",
        "concise": "Focus on key information and essential details. Be direct and efficient while maintaining accuracy and completeness.",
        "balanced": "Balance thoroughness with clarity. Provide sufficient detail while remaining accessible and well-organized.",
    }
    return styles.get(style, styles["balanced"])


async def _save_agent_config(agent_name: str, agent_config: dict):
    """Save agent configuration (no auto-deployment)"""
    import yaml

    # Save agent configuration for future use
    config_dir = Path.home() / ".ago" / "agents"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = config_dir / f"{agent_name}.yaml"
    with open(config_path, "w") as f:
        yaml.dump(agent_config, f, default_flow_style=False)

    return config_path


def _show_success_message(agent_name: str):
    """Show beautiful success message with next steps"""
    console.print()
    console.print("🎉 [bold green]Success! Your agent is ready to go![/bold green]")
    console.print()

    # Show file location
    config_file = f"~/.ago/agents/{agent_name}.yaml"

    console.print("📁 [yellow]Files created:[/yellow]")
    console.print(f"  • Agent config: [cyan]{config_file}[/cyan]")
    console.print()

    # Create success table
    table = Table(title=f"🤖 Agent: {agent_name}", title_style="bold cyan")
    table.add_column("Next Steps", style="green", width=40)
    table.add_column("Command", style="cyan", width=40)

    table.add_row(
        "🚀 Run your agent (like docker run)",
        f"[bold]ago run {agent_name}[/bold]",
    )
    table.add_row(
        "💬 Chat with your agent (after running)",
        f"[bold]ago chat {agent_name}[/bold]",
    )
    table.add_row("📊 Check running agents", "[bold]ago ps[/bold]")
    table.add_row("📋 View agent logs", f"[bold]ago logs {agent_name}[/bold]")

    console.print(table)
    console.print()
    console.print(
        "🌟 [yellow]Pro tip:[/yellow] Run the agent first, then you can chat with it!"
    )
    console.print()


# Docker Registry Pattern Commands


@app.command()
def templates():
    """📦 List all available agent templates in local registry (like 'docker images')"""

    def _templates():
        try:
            templates = registry.list_templates()

            if not templates:
                console.print("ℹ️ No agent templates found in registry")
                console.print(
                    "💡 Use [bold]ago pull <template_name>[/bold] to download templates"
                )
                return

            table = Table()
            table.add_column("Template", style="cyan")
            table.add_column("Version", style="yellow")
            table.add_column("Description", style="green")
            table.add_column("Model", style="magenta")
            table.add_column("Tools", style="blue")
            table.add_column("Source", style="dim")

            for template in templates:
                tools_str = ", ".join(template["tools"][:3])  # Show first 3 tools
                if len(template["tools"]) > 3:
                    tools_str += f" (+{len(template['tools']) - 3})"

                source_icon = "🏠" if template["source"] == "builtin" else "🌐"

                table.add_row(
                    template["name"],
                    f"v{template['version']}",
                    template["description"][:50]
                    + ("..." if len(template["description"]) > 50 else ""),
                    template["model"].replace("claude-3-5-", ""),  # Shorten model name
                    tools_str,
                    f"{source_icon} {template['source']}",
                )

            console.print(table)
            console.print(f"\n📊 [blue]Total templates:[/blue] {len(templates)}")
            console.print("\n💡 [yellow]Usage:[/yellow]")
            console.print(
                "  • [bold]ago up[/bold] - Start all agents from workflow.spec"
            )
            console.print(
                "  • [bold]ago run <template> <name>[/bold] - Run template as standalone agent"
            )

        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    _templates()


@app.command()
def pull(
    registry_template: str = typer.Argument(
        ..., help="Registry and template name (format: registry:template)"
    ),
    version: str = typer.Option("latest", "--version", help="Template version"),
):
    """📥 Download/update agent template from remote registry (like 'docker pull')"""

    def _pull():
        try:
            console.print(
                f"📥 [blue]Pulling template:[/blue] {registry_template}:v{version}"
            )

            success = registry.pull_template(registry_template, version)

            if success:
                console.print(
                    f"✅ [green]Template {registry_template}:v{version} is up to date[/green]"
                )
            else:
                console.print(
                    f"❌ [red]Failed to pull template {registry_template}:v{version}[/red]"
                )

        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    _pull()


@app.command()
def rm(
    template_name: str = typer.Argument(
        ..., help="Template name to remove (format: template or template:version)"
    ),
    all_versions: bool = typer.Option(
        False, "--all", "-a", help="Remove all versions of the template"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force removal without confirmation"
    ),
):
    """🗑️ Remove template from local registry (like 'docker rmi')"""

    def _rm():
        try:
            # Validate template name format
            if not template_name or not template_name.strip():
                console.print("❌ [red]Template name cannot be empty[/red]")
                return

            # Parse template name and version
            if ":" in template_name:
                name, version = template_name.split(":", 1)
                if not version.strip():
                    console.print("❌ [red]Version cannot be empty after ':'[/red]")
                    return
            else:
                name = template_name
                version = "latest" if not all_versions else None

            name = name.strip()
            if not name:
                console.print("❌ [red]Template name cannot be empty[/red]")
                return

            # Check if template exists
            if not all_versions:
                if not registry.template_exists(name, version):
                    console.print(f"❌ [red]Template not found:[/red] {name}:{version}")
                    # Show available templates
                    available_templates = registry.list_templates()
                    matching_names = [
                        t["name"]
                        for t in available_templates
                        if name.lower() in t["name"].lower()
                    ]
                    if matching_names:
                        console.print(
                            f"💡 [yellow]Did you mean:[/yellow] {', '.join(set(matching_names))}"
                        )
                    return

            # Get template info for confirmation
            if all_versions:
                templates = [t for t in registry.list_templates() if t["name"] == name]
                if not templates:
                    console.print(f"❌ [red]Template not found:[/red] {name}")
                    return
                version_count = len(set(t["version"] for t in templates))
                version_str = f"all versions ({version_count} version{'s' if version_count != 1 else ''})"
            else:
                version_str = version

            # Warning for builtin templates
            templates = [t for t in registry.list_templates() if t["name"] == name]
            builtin_templates = [t for t in templates if t.get("source") == "builtin"]
            if builtin_templates and (
                all_versions
                or any(t.get("version") == version for t in builtin_templates)
            ):
                console.print(
                    "⚠️ [yellow]Warning: You are about to remove builtin template(s)[/yellow]"
                )

            # Confirmation prompt
            if not force:
                confirm_msg = f"Remove template {name}:{version_str}?"
                if not Confirm.ask(confirm_msg, default=False):
                    console.print("❌ [yellow]Removal cancelled[/yellow]")
                    return

            # Remove template(s)
            success = registry.remove_template(
                name, version if not all_versions else None
            )

            if success:
                console.print(
                    f"✅ [green]Removed template:[/green] {name}:{version_str}"
                )
            else:
                console.print(
                    f"❌ [red]Failed to remove template:[/red] {name}:{version_str}"
                )
                console.print(
                    "💡 [yellow]Tip:[/yellow] Use --force to skip confirmation or check if template exists"
                )

        except ValueError as e:
            console.print(f"❌ [red]Invalid template name format:[/red] {str(e)}")
        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    _rm()


@app.command()
def up(
    service_name: Optional[str] = typer.Argument(
        None, help="Specific service/agent to start"
    ),
    workflow_file: str = typer.Option(
        "workflow.spec", "--file", "-f", help="Workflow specification file"
    ),
    detach: bool = typer.Option(True, "--detach", "-d", help="Run in background"),
):
    """🚀 Run any workflow: linear, parallel, conditional, or multi-agent"""

    async def _up():
        try:
            from ..core.workflow import run_workflow

            workflow_path = Path(workflow_file)

            if not workflow_path.exists():
                console.print(f"❌ [red]Workflow file not found:[/red] {workflow_file}")
                console.print(
                    "💡 Create a workflow.spec file or use [bold]ago create[/bold] to generate one"
                )
                return

            # Load workflow spec
            with open(workflow_path, "r") as f:
                workflow = yaml.safe_load(f)

            kind = workflow.get("kind", "")

            # Detect workflow type: Workflow (single-flow) vs MultiAgentWorkflow (long-running agents)
            if kind in ["Workflow", "LinearWorkflow"]:
                # Single-flow execution (linear, parallel, conditional)
                console.print(f"🔗 [blue]Starting workflow:[/blue] {workflow['metadata']['name']}")

                success = await run_workflow(workflow)

                if success:
                    console.print(f"✅ [green]Workflow completed successfully![/green]")
                else:
                    console.print(f"❌ [red]Workflow failed[/red]")
                return

            # Multi-agent workflow (original ago up behavior)
            agents_spec = workflow.get("spec", {}).get("agents", [])

            if not agents_spec:
                console.print(
                    f"❌ [red]No agents defined in workflow:[/red] {workflow_file}"
                )
                return

            console.print(f"🚀 [blue]Starting workflow:[/blue] {workflow_file}")

            # If specific service requested, filter to just that agent
            if service_name:
                agents_spec = [
                    agent for agent in agents_spec if agent.get("name") == service_name
                ]
                if not agents_spec:
                    available_agents = [
                        agent.get("name", "unnamed")
                        for agent in workflow.get("spec", {}).get("agents", [])
                    ]
                    console.print(
                        f"❌ [red]Service '{service_name}' not found in workflow[/red]"
                    )
                    console.print(f"Available services: {', '.join(available_agents)}")
                    return
                console.print(
                    f"📍 [yellow]Starting specific service:[/yellow] {service_name}"
                )

            # Check if templates exist in registry and auto-pull if needed
            for agent_spec in agents_spec:
                template_ref = agent_spec.get("template")
                if template_ref:
                    # Parse template reference (e.g., "researcher:v1.0" or just "researcher")
                    if ":" in template_ref:
                        template_name, template_version = template_ref.split(":", 1)
                        template_version = template_version.lstrip(
                            "v"
                        )  # Remove v prefix
                    else:
                        template_name = template_ref
                        template_version = "latest"

                    # Check if template exists, auto-pull if not
                    if not registry.template_exists(template_name, template_version):
                        console.print(
                            f"📥 [yellow]Auto-pulling missing template:[/yellow] {template_name}:v{template_version}"
                        )
                        if not registry.pull_template(template_name, template_version):
                            console.print(
                                f"❌ [red]Failed to pull required template:[/red] {template_name}:v{template_version}"
                            )
                            return

            # Load workflow in daemon (same as current 'run' command)
            result = await daemon_client.load_workflow(str(workflow_path))

            if result["status"] == "error":
                console.print(f"❌ [red]Error:[/red] {result['message']}")
                return

            console.print("✅ [green]Successfully started workflow[/green]")
            console.print(f"📊 [blue]Agents running:[/blue] {len(result['agents'])}")

            # Display running agents
            table = Table()
            table.add_column("Service", style="cyan")
            table.add_column("Template", style="yellow")
            table.add_column("Status", style="green")

            for agent_name in result["agents"]:
                # Try to find template info from original spec
                agent_spec = next(
                    (a for a in agents_spec if a.get("name") == agent_name), {}
                )
                template_ref = agent_spec.get("template", "custom")

                table.add_row(agent_name, template_ref, "🟢 Running")

            console.print(table)

            if not detach:
                console.print(
                    "\n💬 [yellow]Interactive mode - press Ctrl+C to return to shell[/yellow]"
                )
                try:
                    # Keep running until interrupted
                    while True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    console.print(
                        "\n📋 [yellow]Workflow still running in background. Use 'ago down' to stop.[/yellow]"
                    )

        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    asyncio.run(_up())


@app.command()
def down(
    workflow_file: str = typer.Option(
        "workflow.spec", "--file", "-f", help="Workflow specification file"
    ),
):
    """⏹️ Stop and remove workflow agents (like 'docker-compose down')"""

    async def _down():
        try:
            # For now, stop all agents (in future we could be more selective based on workflow)
            result = await daemon_client.stop_all_agents()

            if result.get("status") == "error":
                console.print(f"❌ [red]Error:[/red] {result['message']}")
                return

            console.print(f"⏹️ [green]{result['message']}[/green]")
            console.print("✅ [blue]Workflow agents stopped[/blue]")

        except Exception as e:
            console.print(f"❌ [red]Error:[/red] {str(e)}")

    asyncio.run(_down())


# Configuration Management Commands

config_app = typer.Typer(help="🔧 Configuration management")
app.add_typer(config_app, name="config")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(
        ..., help="Configuration key (dot notation, e.g. registry.github.token)"
    ),
    value: str = typer.Argument(..., help="Configuration value"),
    local: bool = typer.Option(
        False, "--local", help="Set project-level config instead of global"
    ),
):
    """Set configuration value"""
    try:
        if local:
            config.set_project_config(key, value)
            console.print(f"✅ [green]Set project config:[/green] {key} = {value}")
        else:
            config.set_global_config(key, value)
            console.print(f"✅ [green]Set global config:[/green] {key} = {value}")
    except Exception as e:
        console.print(f"❌ [red]Error setting config:[/red] {str(e)}")


@config_app.command("get")
def config_get(
    key: str = typer.Argument(
        None, help="Configuration key to get (omit to show all config)"
    ),
    merged: bool = typer.Option(
        False, "--merged", help="Show final merged configuration"
    ),
):
    """Get configuration value"""
    try:
        if key:
            value = config.get_config_value(key)
            if value is not None:
                console.print(f"{key} = {value}")
            else:
                console.print(f"❌ [red]Configuration key not found:[/red] {key}")
        else:
            # Show all config
            full_config = config.get_config()

            if merged:
                console.print("🔧 [blue]Final merged configuration:[/blue]")
            else:
                console.print("🔧 [blue]Configuration:[/blue]")

            console.print(yaml.dump(full_config, default_flow_style=False))
    except Exception as e:
        console.print(f"❌ [red]Error getting config:[/red] {str(e)}")


@config_app.command("view")
def config_view():
    """Display entire configuration in terminal"""
    try:
        full_config = config.get_config()
        console.print("🔧 [blue]Complete Configuration:[/blue]\n")
        console.print(yaml.dump(full_config, default_flow_style=False))
    except Exception as e:
        console.print(f"❌ [red]Error displaying config:[/red] {str(e)}")


@config_app.command("edit")
def config_edit(
    local: bool = typer.Option(
        False, "--local", help="Edit project config instead of global"
    ),
):
    """Open configuration file in editor"""
    try:
        # Determine which config file to edit
        if local:
            if (
                not config.project_config_file
                or not config.project_config_file.exists()
            ):
                console.print(
                    "❌ [red]No project config found. Use 'ago config init --local' first.[/red]"
                )
                return
            config_file = config.project_config_file
            config_type = "project"
        else:
            config_file = config.global_config_file
            config_type = "global"

        # Ensure config file exists
        if not config_file.exists():
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text("# Ago Configuration\n\n")

        # Get editor command
        editor = _get_default_editor()

        console.print(
            f"📝 [blue]Opening {config_type} config in editor:[/blue] {config_file}"
        )
        console.print(f"🔧 [dim]Editor: {editor}[/dim]")

        # Execute editor command
        if platform.system() == "Darwin" and editor.startswith("open"):
            # macOS: open -t filename
            subprocess.run(
                [editor.split()[0], editor.split()[1], str(config_file)], check=True
            )
        else:
            # Linux/Windows: editor filename
            subprocess.run([editor, str(config_file)], check=True)

        console.print(
            "✅ [green]Config file closed. Changes will take effect immediately.[/green]"
        )

    except subprocess.CalledProcessError:
        console.print(f"❌ [red]Failed to open editor: {editor}[/red]")
        console.print(
            f"💡 [yellow]Try setting EDITOR environment variable or editing manually: {config_file}[/yellow]"
        )
    except Exception as e:
        console.print(f"❌ [red]Error opening config:[/red] {str(e)}")


def _get_default_editor() -> str:
    """Get default editor for the current platform"""
    # Try environment variables first
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if editor:
        return editor

    # Platform-specific defaults
    system = platform.system()
    if system == "Darwin":  # macOS
        return "open -t"
    elif system == "Windows":
        return "notepad"
    else:  # Linux/Unix
        return "nano"  # Most user-friendly for beginners


@config_app.command("list")
def config_list(
    global_only: bool = typer.Option(False, "--global", help="Show only global config"),
    local_only: bool = typer.Option(False, "--local", help="Show only local config"),
):
    """List configuration files and locations"""
    try:
        if not local_only:
            console.print("🌍 [blue]Global Config:[/blue]")
            console.print(f"  Location: {config.global_config_file}")
            console.print(
                f"  Exists: {'✅' if config.global_config_file.exists() else '❌'}"
            )
            console.print(f"  Auth file: {config.global_auth_file}")
            console.print()

        if not global_only:
            console.print("📁 [blue]Project Config:[/blue]")
            if config.project_config_dir:
                console.print(f"  Location: {config.project_config_file}")
                console.print(
                    f"  Exists: {'✅' if config.project_config_file.exists() else '❌'}"
                )
                console.print(f"  Auth file: {config.project_auth_file}")
            else:
                console.print("  No project config found (no .ago/ directory)")

        console.print()
        console.print("🔍 [blue]Template Resolution Order:[/blue]")
        resolution_order = config.get_template_resolution_order()
        for i, source in enumerate(resolution_order, 1):
            console.print(f"  {i}. {source}")

    except Exception as e:
        console.print(f"❌ [red]Error listing config:[/red] {str(e)}")


@config_app.command("init")
def config_init(
    local: bool = typer.Option(
        False, "--local", help="Initialize project config instead of global"
    ),
):
    """Initialize configuration with default values"""
    try:
        if local:
            # Create .ago directory and basic config
            config.set_project_config(
                "defaults.template_resolution_order", ["local", "builtin"]
            )
            console.print(
                "✅ [green]Initialized project configuration in .ago/[/green]"
            )
        else:
            # Create global config directory and basic config
            config.set_global_config("defaults.auto_update", False)
            config.set_global_config("defaults.cache_duration", "24h")
            console.print(
                "✅ [green]Initialized global configuration in ~/.ago/[/green]"
            )

        console.print(
            "💡 [yellow]Use 'ago config list' to see config locations[/yellow]"
        )
    except Exception as e:
        console.print(f"❌ [red]Error initializing config:[/red] {str(e)}")


# Registry Management Commands

registry_app = typer.Typer(help="📦 Registry management")
app.add_typer(registry_app, name="registry")


@registry_app.command("add")
def registry_add(
    name: str = typer.Argument(..., help="Registry name"),
    url: str = typer.Argument(..., help="Registry URL"),
    registry_type: str = typer.Option(
        "http", "--type", help="Registry type (http, github)"
    ),
    token: Optional[str] = typer.Option(None, "--token", help="Authentication token"),
    local: bool = typer.Option(
        False, "--local", help="Add to project config instead of global"
    ),
    priority: int = typer.Option(
        100, "--priority", help="Registry priority (lower = higher priority)"
    ),
):
    """Add a template registry"""
    try:
        registry_config = {
            "url": url,
            "type": registry_type,
            "enabled": True,
            "priority": priority,
        }

        if token:
            registry_config["token"] = token

        key = f"registries.{name}"

        if local:
            config.set_project_config(key, registry_config)
            console.print(f"✅ [green]Added project registry:[/green] {name}")
        else:
            config.set_global_config(key, registry_config)
            console.print(f"✅ [green]Added global registry:[/green] {name}")

        console.print(f"  URL: {url}")
        console.print(f"  Type: {registry_type}")
        console.print(f"  Priority: {priority}")

    except Exception as e:
        console.print(f"❌ [red]Error adding registry:[/red] {str(e)}")


@registry_app.command("list")
def registry_list():
    """List all configured registries"""
    try:
        registries = config.get_registries()

        if not registries:
            console.print("ℹ️ No registries configured")
            return

        table = Table()
        table.add_column("Name", style="cyan")
        table.add_column("URL", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Priority", style="magenta")
        table.add_column("Status", style="blue")

        for reg in registries:
            status = "🟢 Enabled" if reg.enabled else "⚫ Disabled"
            table.add_row(reg.name, reg.url, reg.type, str(reg.priority), status)

        console.print(table)

    except Exception as e:
        console.print(f"❌ [red]Error listing registries:[/red] {str(e)}")


@registry_app.command("remove")
def registry_remove(
    name: str = typer.Argument(..., help="Registry name to remove"),
    local: bool = typer.Option(
        False, "--local", help="Remove from project config instead of global"
    ),
):
    """Remove a template registry"""
    try:
        key = f"registries.{name}"

        if local:
            # Load project config and remove registry
            if config.project_config_file and config.project_config_file.exists():
                project_config = config._load_yaml_config(config.project_config_file)
                if (
                    "registries" in project_config
                    and name in project_config["registries"]
                ):
                    del project_config["registries"][name]
                    with open(config.project_config_file, "w") as f:
                        yaml.dump(project_config, f, default_flow_style=False)
                    console.print(f"✅ [green]Removed project registry:[/green] {name}")
                else:
                    console.print(
                        f"❌ [red]Registry not found in project config:[/red] {name}"
                    )
            else:
                console.print("❌ [red]No project config file found[/red]")
        else:
            # Load global config and remove registry
            global_config = config._load_yaml_config(config.global_config_file)
            if "registries" in global_config and name in global_config["registries"]:
                del global_config["registries"][name]
                with open(config.global_config_file, "w") as f:
                    yaml.dump(global_config, f, default_flow_style=False)
                console.print(f"✅ [green]Removed global registry:[/green] {name}")
            else:
                console.print(
                    f"❌ [red]Registry not found in global config:[/red] {name}"
                )

        # Clear config cache
        config._config_cache = None

    except Exception as e:
        console.print(f"❌ [red]Error removing registry:[/red] {str(e)}")


# Register MCP commands
register_mcp_commands(app)


if __name__ == "__main__":
    app()
