#!/usr/bin/env python3
"""
Ago Daemon Client - Communicates with daemon via Unix socket
"""

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import msgpack
from rich.console import Console

console = Console()


class DaemonClient:
    """Client for communicating with Ago daemon"""

    def __init__(self):
        self.daemon_dir = Path.home() / ".ago"
        self.socket_file = self.daemon_dir / "daemon.sock"
        self.pid_file = self.daemon_dir / "daemon.pid"

    async def _send_command(
        self, command: str, args: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Send command to daemon and get response"""
        if not await self._ensure_daemon_running():
            raise RuntimeError("Failed to start daemon")

        try:
            reader, writer = await asyncio.open_unix_connection(str(self.socket_file))

            request = {"command": command, "args": args or {}}
            request_packed = msgpack.packb(request)

            # Send with length prefix for reliable msgpack parsing
            length_prefix = len(request_packed).to_bytes(4, "big")
            writer.write(length_prefix + request_packed)
            await writer.drain()

            # Read message with length prefixing for reliable msgpack parsing
            try:
                # First, read 4-byte length prefix
                length_bytes = await reader.readexactly(4)
                message_length = int.from_bytes(length_bytes, "big")

                # Then read exact message length
                data = await reader.readexactly(message_length)
                if not data:
                    raise RuntimeError("Received empty response from daemon")

                response = msgpack.unpackb(data, raw=False)

            except asyncio.IncompleteReadError as e:
                raise RuntimeError(
                    f"Connection closed while reading response: expected {e.expected} bytes, got {len(e.partial)}"
                )
            except Exception as e:
                raise RuntimeError(f"Failed to read response: {e}")

            writer.close()
            await writer.wait_closed()

            return response

        except Exception as e:
            raise RuntimeError(f"Failed to communicate with daemon: {e}")

    async def _ensure_daemon_running(self) -> bool:
        """Ensure daemon is running, start if necessary"""
        if await self._is_daemon_running():
            return True

        console.print("🔄 Starting Ago daemon...")
        return await self._start_daemon()

    async def _is_daemon_running(self) -> bool:
        """Check if daemon is running"""
        if not self.socket_file.exists():
            return False

        try:
            reader, writer = await asyncio.open_unix_connection(str(self.socket_file))
            writer.close()
            await writer.wait_closed()
            return True
        except:
            return False

    async def _start_daemon(self) -> bool:
        """Start daemon process"""
        try:
            # Start daemon in background as module
            # Create daemon directory if it doesn't exist
            self.daemon_dir.mkdir(exist_ok=True)

            console.print("🔧 Starting daemon as module...")

            process = subprocess.Popen(
                [sys.executable, "-m", "ago.core"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,  # Detach from parent
            )

            console.print(f"🔧 Daemon process started with PID: {process.pid}")

            # Wait for daemon to start (check socket file)
            for i in range(20):  # Wait up to 10 seconds
                await asyncio.sleep(0.5)

                # Check if process is still alive
                if process.poll() is not None:
                    # Process died, get error output
                    stdout, stderr = process.communicate()
                    console.print("❌ Daemon process died:", style="red")
                    console.print(f"stdout: {stdout.decode()}")
                    console.print(f"stderr: {stderr.decode()}")
                    return False

                if self.socket_file.exists():
                    console.print("✅ Ago daemon started")
                    return True

                if i % 4 == 0:  # Every 2 seconds
                    console.print(f"⏳ Waiting for daemon to start... ({i // 2}s)")

            # Timeout - get error output
            stdout, stderr = process.communicate(timeout=1)
            console.print("❌ Daemon failed to start within timeout", style="red")
            console.print(f"stdout: {stdout.decode()}")
            console.print(f"stderr: {stderr.decode()}")
            return False

        except Exception as e:
            console.print(f"❌ Failed to start daemon: {e}", style="red")
            import traceback

            console.print(traceback.format_exc())
            return False

    async def start_daemon(self) -> Dict[str, Any]:
        """Start daemon (used by CLI command)"""
        success = await self._start_daemon()
        if success:
            return {"status": "success", "message": "Daemon started successfully"}
        else:
            return {"status": "error", "message": "Failed to start daemon"}

    async def daemon_status(self) -> Dict[str, Any]:
        """Get daemon status"""
        is_running = await self._is_daemon_running()

        if is_running and self.pid_file.exists():
            try:
                with open(self.pid_file, "r") as f:
                    pid = int(f.read().strip())
                return {"running": True, "pid": pid}
            except:
                return {"running": True, "pid": None}
        else:
            return {"running": False, "pid": None}

    async def load_workflow(self, workflow_spec: str) -> Dict[str, Any]:
        """Load workflow in daemon"""
        return await self._send_command(
            "load_workflow", {"workflow_spec": workflow_spec}
        )

    async def start_agent(self, workflow_spec: str, agent_name: str) -> Dict[str, Any]:
        """Start a single agent from workflow spec"""
        return await self._send_command(
            "start_agent", {"workflow_spec": workflow_spec, "agent_name": agent_name}
        )

    async def list_agents(self) -> Dict[str, Any]:
        """List running agents"""
        return await self._send_command("list_agents")

    async def chat_message(self, agent_name: str, message: str) -> Dict[str, Any]:
        """Send chat message to agent"""
        return await self._send_command(
            "chat_message", {"agent_name": agent_name, "message": message}
        )

    async def get_agent_logs(self, agent_name: str, tail: int = 10) -> Dict[str, Any]:
        """Get agent conversation logs"""
        return await self._send_command(
            "get_agent_logs", {"agent_name": agent_name, "tail": tail}
        )

    async def get_message_queues(
        self, agent_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get message queue status between agents"""
        return await self._send_command(
            "get_message_queues", {"agent_name": agent_name}
        )

    async def send_inter_agent_message(
        self, from_agent: str, to_agent: str, message: str
    ) -> Dict[str, Any]:
        """Send a message between agents"""
        return await self._send_command(
            "send_inter_agent_message",
            {"from_agent": from_agent, "to_agent": to_agent, "message": message},
        )

    async def stop_agent(self, agent_name: str) -> Dict[str, Any]:
        """Stop specific agent"""
        return await self._send_command("stop_agent", {"agent_name": agent_name})

    async def stop_all_agents(self) -> Dict[str, Any]:
        """Stop all running agents but keep daemon running"""
        return await self._send_command("stop_all_agents")

    async def stop_daemon(self) -> bool:
        """Stop the daemon"""
        if not self.pid_file.exists():
            return True

        try:
            with open(self.pid_file, "r") as f:
                pid = int(f.read().strip())

            import os
            import signal

            os.kill(pid, signal.SIGTERM)

            # Wait for shutdown
            for _ in range(10):
                await asyncio.sleep(0.5)
                if not self.pid_file.exists():
                    console.print("✅ Ago daemon stopped")
                    return True

            console.print("❌ Daemon did not stop gracefully", style="red")
            return False

        except Exception as e:
            console.print(f"❌ Failed to stop daemon: {e}", style="red")
            return False
