#!/usr/bin/env python3
"""
Ago CLI - Docker-like interface for AI agents
Commands: ago run, ago chat, ago ps, ago logs
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
import yaml

# Import daemon client
from daemon_client import DaemonClient
from rich.console import Console
from rich.table import Table

# Global CLI app and console
app = typer.Typer(
    name="ago", help="🤖 Ago - Docker for AI agents", add_completion=False
)
console = Console()

# Global daemon client
daemon_client = DaemonClient()


@app.command()
def run(
    workflow_spec: str = typer.Argument(
        "workflow.spec", help="Path to workflow specification file"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Run in interactive mode"
    ),
):
    """🚀 Run agents from workflow specification (like 'docker run')"""

    async def _run():
        try:
            # Load workflow in daemon (starts daemon if needed)
            result = await daemon_client.load_workflow(workflow_spec)

            if result["status"] == "error":
                console.print(f"❌ {result['message']}", style="red")
                raise typer.Exit(1)

            # Background mode (default)
            if not interactive:
                console.print("🚀 Workflow started (running in background)")
                console.print("Use [bold]ago ps[/bold] to see running agents")
                console.print("Use [bold]ago chat <agent_name>[/bold] to interact")
                console.print(
                    f"Started agents: [bold cyan]{', '.join(result['agents'])}[/bold cyan]"
                )
                return

            # Interactive mode: start chat immediately
            agents = result["agents"]
            if len(agents) == 1:
                agent_name = agents[0]
                console.print(
                    f"🚀 Interactive mode: Starting chat with [bold cyan]{agent_name}[/bold cyan]..."
                )
                await _interactive_chat(agent_name)
            else:
                console.print("🚀 Multi-agent workflow loaded in interactive mode.")
                console.print(f"Available agents: [bold]{agents}[/bold]")

                agent_name = typer.prompt("Which agent would you like to chat with?")
                if agent_name in agents:
                    await _interactive_chat(agent_name)
                else:
                    console.print(f"❌ Agent '{agent_name}' not found", style="red")

        except Exception as e:
            console.print(f"❌ Failed to run workflow: {e}", style="red")
            raise typer.Exit(1)

    asyncio.run(_run())


async def _interactive_chat(agent_name: str):
    """Interactive chat with daemon-managed agent"""
    console.print(
        f"💬 Chatting with [bold cyan]{agent_name}[/bold cyan]. Type 'exit' to quit.\\n"
    )

    try:
        while True:
            try:
                user_input = typer.prompt("👤 You").strip()

                if user_input.lower() in ["exit", "quit", "bye"]:
                    console.print("👋 Goodbye!", style="green")
                    break

                if not user_input:
                    continue

                # Send message to daemon
                result = await daemon_client.chat_message(agent_name, user_input)

                if result["status"] == "error":
                    console.print(f"❌ {result['message']}", style="red")
                    continue

                response = result["response"]
                console.print(f"🤖 [bold cyan]{agent_name}[/bold cyan]: {response}")

            except KeyboardInterrupt:
                console.print("\\n👋 Chat interrupted. Goodbye!", style="green")
                break
            except Exception as e:
                console.print(f"❌ Error: {e}", style="red")

    except Exception as e:
        console.print(f"❌ Chat error: {e}", style="red")


@app.command()
def chat(agent_name: str = typer.Argument(..., help="Name of the agent to chat with")):
    """💬 Chat with a specific agent (like 'docker exec -it')"""

    async def _chat():
        try:
            await _interactive_chat(agent_name)
        except Exception as e:
            console.print(f"❌ Chat failed: {e}", style="red")
            raise typer.Exit(1)

    asyncio.run(_chat())


@app.command()
def ps():
    """📋 List running agents (like 'docker ps')"""

    async def _ps():
        try:
            result = await daemon_client.list_agents()

            if result["status"] == "error":
                console.print(f"❌ {result['message']}", style="red")
                return

            agents = result["agents"]

            if not agents:
                console.print(
                    "No agents running. Use [bold]ago run workflow.spec[/bold] to start agents."
                )
                return

            # Create a beautiful table
            table = Table(title="🤖 Ago - Running Agents")
            table.add_column("AGENT NAME", style="cyan", no_wrap=True)
            table.add_column("STATUS", style="green")
            table.add_column("MODEL", style="yellow")
            table.add_column("TOOLS", justify="center")
            table.add_column("CREATED", style="blue")
            table.add_column("CONVERSATIONS", justify="center")

            for agent in agents:
                model = agent.get("model", "unknown")
                created_at = datetime.fromisoformat(agent["created_at"])
                created_ago = datetime.now() - created_at
                created_str = (
                    f"{created_ago.seconds // 60}m ago"
                    if created_ago.seconds > 60
                    else f"{created_ago.seconds}s ago"
                )

                table.add_row(
                    agent["name"],
                    agent["status"],
                    model.split("-")[-1]
                    if "-" in model
                    else model,  # Shorter model name
                    str(agent["tools"]),
                    created_str,
                    str(agent["conversations"]),
                )

            console.print(table)

        except Exception as e:
            console.print(f"❌ Failed to list agents: {e}", style="red")

    asyncio.run(_ps())


@app.command()
def logs(
    agent_name: str = typer.Argument(..., help="Name of the agent to show logs for"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    tail: int = typer.Option(
        10, "--tail", help="Number of lines to show from end of logs"
    ),
):
    """📜 Show agent logs (like 'docker logs')"""

    async def _logs():
        try:
            result = await daemon_client.get_agent_logs(agent_name, tail)

            if result["status"] == "error":
                console.print(f"❌ {result['message']}", style="red")
                return

            logs = result["logs"]

            console.print(f"📜 Logs for [bold cyan]{agent_name}[/bold cyan]")
            console.print("=" * 50)

            if not logs:
                console.print("No conversation history yet.")
                return

            # Show conversation history as "logs"
            for entry in logs:
                timestamp = entry.get("timestamp", "unknown")
                console.print(f"🕐 {timestamp}")
                console.print(f"👤 User: {entry['user']}")
                console.print(f"🤖 {agent_name}: {entry['assistant']}")
                console.print("-" * 30)

        except Exception as e:
            console.print(f"❌ Failed to get logs: {e}", style="red")

    asyncio.run(_logs())


@app.command()
def queues(
    agent_name: Optional[str] = typer.Argument(
        None, help="Name of specific agent to show queues for (optional)"
    ),
    follow: bool = typer.Option(
        False, "--follow", "-f", help="Follow queue messages in real-time"
    ),
    tail: int = typer.Option(
        10, "--tail", help="Number of recent messages to show initially"
    ),
):
    """📨 Show message queues between agents (like 'docker network ls')"""

    async def _queues():
        try:
            if follow:
                await _follow_queue_messages(agent_name, tail)
            else:
                await _show_queue_status(agent_name, tail)

        except Exception as e:
            console.print(f"❌ Failed to get queues: {e}", style="red")

    async def _show_queue_status(agent_name, tail):
        """Show static queue status"""
        result = await daemon_client.get_message_queues(agent_name)

        if result["status"] == "error":
            console.print(f"❌ {result['message']}", style="red")
            return

        queues = result["queues"]

        if not queues:
            console.print("No message queues found.")
            return

        # Create a table for agent inbox status
        table = Table(title="📨 Agent Inboxes")
        table.add_column("AGENT NAME", style="cyan", no_wrap=True)
        table.add_column("INBOX SIZE", justify="center")
        table.add_column("TOTAL RECEIVED", justify="center")
        table.add_column("LAST MESSAGE", style="yellow")
        table.add_column("STATUS", style="blue")

        for queue_info in queues:
            last_msg = queue_info.get("last_message", "No messages")

            table.add_row(
                queue_info["agent_name"],
                str(queue_info["inbox_size"]),
                str(queue_info["total_received"]),
                last_msg,
                queue_info["status"],
            )

        console.print(table)

        # Show detailed messages if specific agent requested
        if agent_name and result.get("messages"):
            console.print(
                f"\n📋 Recent Messages for [bold cyan]{agent_name}[/bold cyan]:"
            )
            console.print("=" * 60)

            for msg in result["messages"][-tail:]:
                timestamp = msg.get("timestamp", "unknown")
                from_agent = msg.get("from", "unknown")
                to_agent = msg.get("to", "unknown")
                content = msg.get("content", "")

                console.print(f"🕐 {timestamp}")
                console.print(
                    f"📤 From: [cyan]{from_agent}[/cyan] → To: [green]{to_agent}[/green]"
                )
                console.print(f"📝 Content: {content}")
                console.print("-" * 40)

    async def _follow_queue_messages(agent_name, tail):
        """Follow queue messages in real-time like 'docker logs -f'"""
        console.print("📨 Following inter-agent messages in real-time...")
        console.print("Press Ctrl+C to stop\n")

        # Show initial messages
        result = await daemon_client.get_message_queues(agent_name)
        if result["status"] == "success" and result.get("messages"):
            console.print("🔙 Recent messages:")
            console.print("-" * 50)

            for msg in result["messages"][-tail:]:
                _print_live_message(msg)

        console.print("\n🔴 Live messages:")
        console.print("-" * 50)

        # Track last seen message to avoid duplicates
        last_message_count = (
            len(result.get("messages", [])) if result["status"] == "success" else 0
        )

        try:
            while True:
                await asyncio.sleep(1)  # Poll every second

                result = await daemon_client.get_message_queues(agent_name)
                if result["status"] == "success" and result.get("messages"):
                    messages = result["messages"]

                    # Show only new messages
                    if len(messages) > last_message_count:
                        for msg in messages[last_message_count:]:
                            _print_live_message(msg)
                        last_message_count = len(messages)

        except KeyboardInterrupt:
            console.print("\n👋 Stopped following messages")

    asyncio.run(_queues())


def _print_live_message(msg):
    """Print a single message in live format"""
    timestamp = msg.get("timestamp", "unknown")
    from_agent = msg.get("from", "unknown")
    to_agent = msg.get("to", "unknown")
    content = msg.get("content", "")
    msg_type = msg.get("type", "unknown")

    # Color code by message type
    if msg_type == "inter_agent":
        icon = "🤖"
        style = "green"
    else:
        icon = "📨"
        style = "blue"

    console.print(
        f"{icon} [{style}]{timestamp}[/{style}] [cyan]{from_agent}[/cyan] → [yellow]{to_agent}[/yellow]: {content}"
    )


@app.command()
def send(
    from_agent: str = typer.Argument(..., help="Name of the sending agent"),
    to_agent: str = typer.Argument(..., help="Name of the receiving agent"),
    message: str = typer.Argument(..., help="Message content to send"),
):
    """📤 Send a message between agents (for testing)"""

    async def _send():
        try:
            result = await daemon_client.send_inter_agent_message(
                from_agent, to_agent, message
            )

            if result["status"] == "error":
                console.print(f"❌ {result['message']}", style="red")
                return

            console.print(
                f"✅ Message sent: [cyan]{from_agent}[/cyan] → [green]{to_agent}[/green]"
            )
            console.print(f"📝 Content: {message}")

        except Exception as e:
            console.print(f"❌ Failed to send message: {e}", style="red")

    asyncio.run(_send())


@app.command()
def start(
    agent_name: str = typer.Argument(
        ..., help="Name of the agent to start from workflow.spec"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Start in interactive mode"
    ),
):
    """🚀 Start a single agent from workflow.spec (like 'docker-compose start <service>')"""

    async def _start():
        try:
            # Check if workflow.spec exists in current directory
            workflow_spec = Path("workflow.spec")
            if not workflow_spec.exists():
                console.print(
                    "❌ No workflow.spec found in current directory", style="red"
                )
                console.print(
                    "Create a workflow.spec file or use [bold]ago run workflow.spec[/bold] to start all agents"
                )
                raise typer.Exit(1)

            # Load workflow.spec to check if agent is defined
            try:
                with open(workflow_spec, "r") as f:
                    workflow = yaml.safe_load(f)
            except Exception as e:
                console.print(f"❌ Failed to parse workflow.spec: {e}", style="red")
                raise typer.Exit(1)

            # Check if agent is defined in spec
            agent_names = [agent["name"] for agent in workflow["spec"]["agents"]]
            if agent_name not in agent_names:
                console.print(
                    f"❌ Agent '{agent_name}' not found in workflow.spec", style="red"
                )
                console.print(f"Available agents: {', '.join(agent_names)}")
                raise typer.Exit(1)

            # Start single agent from workflow via daemon
            result = await daemon_client.start_agent("workflow.spec", agent_name)

            if result["status"] == "error":
                console.print(f"❌ {result['message']}", style="red")
                raise typer.Exit(1)

            # Background mode (default)
            if not interactive:
                console.print(
                    f"🚀 Agent [bold cyan]{agent_name}[/bold cyan] started (running in background)"
                )
                console.print("Use [bold]ago ps[/bold] to see running agents")
                console.print(f"Use [bold]ago chat {agent_name}[/bold] to interact")
                return

            # Interactive mode: start chat immediately
            console.print(
                f"🚀 Interactive mode: Starting chat with [bold cyan]{agent_name}[/bold cyan]..."
            )
            await _interactive_chat(agent_name)

        except Exception as e:
            console.print(f"❌ Failed to start agent: {e}", style="red")
            raise typer.Exit(1)

    asyncio.run(_start())


@app.command()
def stop(agent_name: str = typer.Argument(..., help="Name of agent to stop")):
    """🛑 Stop a specific agent (like 'docker stop')"""

    async def _stop():
        try:
            result = await daemon_client.stop_agent(agent_name)
            if result["status"] == "success":
                console.print(
                    f"🛑 Agent [cyan]{agent_name}[/cyan] stopped", style="green"
                )
            else:
                console.print(f"❌ {result['message']}", style="red")

        except Exception as e:
            console.print(f"❌ Stop failed: {e}", style="red")

    asyncio.run(_stop())


# Create daemon subcommand group
daemon_app = typer.Typer(help="🔧 Manage Ago daemon")
app.add_typer(daemon_app, name="daemon")


@daemon_app.command("start")
def daemon_start():
    """🚀 Start the Ago daemon"""
    console.print("🚀 Starting Ago daemon...")

    async def _start():
        try:
            # Just trigger daemon startup by checking if it's running
            await daemon_client._ensure_daemon_running()
            console.print("✅ Ago daemon is running", style="green")
        except Exception as e:
            console.print(f"❌ Failed to start daemon: {e}", style="red")

    asyncio.run(_start())


@daemon_app.command("stop")
def daemon_stop():
    """🛑 Stop the Ago daemon"""

    async def _stop():
        try:
            result = await daemon_client.stop_daemon()
            if result:
                console.print("🛑 Ago daemon stopped", style="green")
            else:
                console.print("❌ Failed to stop daemon", style="red")
        except Exception as e:
            console.print(f"❌ Stop failed: {e}", style="red")

    asyncio.run(_stop())


@daemon_app.command("status")
def daemon_status():
    """📊 Show daemon status"""

    async def _status():
        try:
            is_running = await daemon_client._is_daemon_running()
            if is_running:
                console.print("✅ Ago daemon is running", style="green")
                # Also show agent count
                result = await daemon_client.list_agents()
                if result["status"] == "success":
                    agent_count = len(result["agents"])
                    console.print(f"📊 Managing {agent_count} agents")
            else:
                console.print("❌ Ago daemon is not running", style="red")
        except Exception as e:
            console.print(f"❌ Status check failed: {e}", style="red")

    asyncio.run(_status())


@app.command()
def version():
    """Show Ago version"""
    console.print("🤖 Ago v1.0.0 - Docker for AI agents")


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    app()
