#!/usr/bin/env python3
"""
Ago Agent Process - Individual process for each agent
Runs PocketFlow agents in isolation with IPC communication
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import msgpack
from rich.console import Console

# Import PocketFlow and local modules
from ...agents.agent_react_flow import create_agent_flow

console = Console()


class AgentProcess:
    """Individual process for running a single agent with IPC"""

    def __init__(
        self,
        agent_name: str,
        instance_id: str,
        agent_spec: Dict[str, Any],
        agent_template: str,
        agent_tools: List[Dict[str, Any]],
        daemon_socket_path: str,
        process_socket_path: str,
    ):
        self.agent_name = agent_name  # Agent type (e.g., "researcher")
        self.instance_id = instance_id  # Unique instance ID (e.g., "researcher-abc123")
        self.agent_spec = agent_spec
        self.agent_template = agent_template
        self.agent_tools = agent_tools
        self.daemon_socket_path = daemon_socket_path
        self.process_socket_path = process_socket_path

        # Process state
        self.pid = os.getpid()
        self.status = "starting"
        self.created_at = datetime.now().isoformat()
        self._shutdown_requested = False

        # PocketFlow agent and state
        self.agent_flow = None
        self.shared_store = None
        self.server = None

        # Setup logging using instance ID
        log_dir = Path.home() / ".ago" / "logs"
        log_dir.mkdir(exist_ok=True, parents=True)
        log_file = log_dir / f"{instance_id}.log"

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(f"ago.agent.{instance_id}")

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Agent {self.instance_id} received signal {signum}")
        self._shutdown_requested = True

    async def start(self):
        """Start the agent process"""
        try:
            self.logger.info(
                f"Starting agent process: {self.instance_id} ({self.agent_name}) (PID: {self.pid})"
            )

            # Initialize PocketFlow agent
            await self._initialize_agent()

            # Start IPC server for daemon communication
            await self._start_ipc_server()

            # Register with daemon
            await self._register_with_daemon()

            self.status = "running"
            self.logger.info(f"Agent {self.agent_name} is running")

            # Keep process running
            while not self._shutdown_requested:
                await asyncio.sleep(0.1)

            await self._shutdown()

        except Exception as e:
            self.logger.error(f"Agent process failed: {e}")
            self.status = "failed"
            raise

    async def _initialize_agent(self):
        """Initialize the PocketFlow agent"""
        try:
            # Create PocketFlow agent with ReAct intelligence
            self.agent_flow = create_agent_flow(
                self.agent_name, self.agent_spec, self.agent_template, self.agent_tools
            )

            # Create shared store for conversation state
            self.shared_store = {
                "conversation_history": [],
                "tools": self.agent_tools,
                "supervisor_scratchpad": "",
                "user_message": "",
                "assistant_response": "",
                "inter_agent_message": {},
                "delegation_request": None,
                "response_to_send": None,
            }

            self.logger.info(f"Initialized PocketFlow agent: {self.agent_name}")

        except Exception as e:
            self.logger.error(f"Failed to initialize agent: {e}")
            raise

    async def _start_ipc_server(self):
        """Start Unix socket server for daemon communication"""
        try:
            # Remove existing socket if it exists
            socket_path = Path(self.process_socket_path)
            socket_path.unlink(missing_ok=True)

            # Start Unix socket server
            self.server = await asyncio.start_unix_server(
                self._handle_ipc_message, path=str(socket_path)
            )

            self.logger.info(f"Agent IPC server started: {socket_path}")

        except Exception as e:
            self.logger.error(f"Failed to start IPC server: {e}")
            raise

    async def _handle_ipc_message(self, reader, writer):
        """Handle IPC message from daemon"""
        try:
            # Read message with length prefixing for reliable msgpack parsing
            try:
                # First, read 4-byte length prefix
                length_bytes = await reader.readexactly(4)
                message_length = int.from_bytes(length_bytes, "big")

                # Then read exact message length
                data = await reader.readexactly(message_length)
                if not data:
                    return

                message = msgpack.unpackb(data, raw=False)
                command = message.get("command", "unknown")
                self.logger.info(f"Processing IPC command: {command}")

                response = await self._process_ipc_command(message)

            except asyncio.IncompleteReadError as e:
                self.logger.error(
                    f"Incomplete read from daemon: expected {e.expected} bytes, got {len(e.partial)}"
                )
                return
            except Exception as e:
                self.logger.error(f"Failed to read daemon message: {e}")
                return

            # Try to send response with better error handling
            try:
                response_packed = msgpack.packb(response)
                length_prefix = len(response_packed).to_bytes(4, "big")
                writer.write(length_prefix + response_packed)
                await writer.drain()
                self.logger.debug(f"IPC response sent for command: {command}")
            except (BrokenPipeError, ConnectionResetError) as e:
                self.logger.warning(
                    f"Connection broken while sending response for {command}: {e}"
                )
                # Don't try to send error response if connection is broken
                return

        except Exception as e:
            self.logger.error(f"Error handling IPC message: {e}")
            error_response = {"status": "error", "message": str(e)}
            try:
                if not writer.is_closing():
                    error_packed = msgpack.packb(error_response)
                    length_prefix = len(error_packed).to_bytes(4, "big")
                    writer.write(length_prefix + error_packed)
                    await writer.drain()
            except (BrokenPipeError, ConnectionResetError):
                self.logger.warning("Cannot send error response - connection broken")
            except Exception as send_error:
                self.logger.error(f"Error sending error response: {send_error}")
        finally:
            try:
                if not writer.is_closing():
                    writer.close()
                    await writer.wait_closed()
            except Exception as close_error:
                self.logger.debug(f"Error closing connection: {close_error}")

    async def _process_ipc_command(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process IPC command from daemon"""
        command = message.get("command")
        args = message.get("args", {})

        if command == "ping":
            return {"status": "success", "message": "pong", "agent": self.agent_name}

        elif command == "get_status":
            return {
                "status": "success",
                "agent_status": self.status,
                "pid": self.pid,
                "created_at": self.created_at,
            }

        elif command == "process_chat_message":
            return await self._process_chat_message(args.get("message", ""))

        elif command == "get_conversation_history":
            return {
                "status": "success",
                "history": self.shared_store["conversation_history"],
            }

        elif command == "send_inter_agent_message":
            return await self._handle_inter_agent_message(
                args.get("from_agent"), args.get("message")
            )

        elif command == "log_outgoing_message":
            return await self._log_outgoing_message(
                args.get("to_agent"), args.get("message")
            )

        elif command == "stop":
            self._shutdown_requested = True
            return {"status": "success", "message": "Agent stopping"}

        else:
            return {"status": "error", "message": f"Unknown command: {command}"}

    async def _process_chat_message(self, user_message: str) -> Dict[str, Any]:
        """Process chat message using PocketFlow agent"""
        try:
            self.logger.info(f"Processing chat message: {user_message}")

            # Update shared store with user message
            self.shared_store["user_message"] = user_message

            # Run PocketFlow agent (async)
            await self.agent_flow.run_async(self.shared_store)

            # Get assistant response
            assistant_response = self.shared_store.get("assistant_response", "")
            
            # Note: Conversation history is managed by the ReAct flow itself
            # when it completes with a "final" action

            return {
                "status": "success",
                "response": assistant_response,
                "agent": self.agent_name,
            }

        except Exception as e:
            self.logger.error(f"Error processing chat message: {e}")
            return {"status": "error", "message": str(e)}

    async def _handle_inter_agent_message(
        self, from_agent: str, message: str
    ) -> Dict[str, Any]:
        """Handle message from another agent"""
        try:
            self.logger.info(
                f"Received inter-agent message from {from_agent}: {message}"
            )

            # Store the inter-agent message
            self.shared_store["inter_agent_message"] = {
                "from": from_agent,
                "content": message,
                "timestamp": datetime.now().isoformat(),
            }

            # Process the message using the agent
            user_message = f"[Message from {from_agent}]: {message}"
            self.shared_store["user_message"] = user_message
            await self.agent_flow.run_async(self.shared_store)

            # Get response
            response = self.shared_store.get("assistant_response", "")

            # ✅ Update conversation history for inter-agent messages
            self.shared_store["conversation_history"].append(
                {
                    "role": "user",
                    "content": user_message,
                    "timestamp": datetime.now().isoformat(),
                    "type": "inter_agent",
                    "from": from_agent,
                }
            )

            self.shared_store["conversation_history"].append(
                {
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now().isoformat(),
                    "type": "inter_agent_response",
                    "to": from_agent,
                }
            )

            # Check if agent wants to send a response back
            response_to_send = self.shared_store.get("response_to_send")
            self.logger.info(
                f"Agent flow completed, response_to_send: {response_to_send}"
            )
            self.logger.info(f"Shared store keys: {list(self.shared_store.keys())}")

            if response_to_send:
                # Add the outgoing message to sender's conversation history as assistant message
                self.shared_store["conversation_history"].append(
                    {
                        "role": "assistant",
                        "content": response_to_send,
                        "timestamp": datetime.now().isoformat(),
                        "type": "inter_agent_outgoing",
                        "to": from_agent,
                    }
                )

                # Send response back through daemon
                await self._send_message_to_daemon(
                    "inter_agent_response",
                    {
                        "to_agent": from_agent,
                        "from_agent": self.instance_id,  # ✅ Use unique instance ID
                        "message": response_to_send,
                    },
                )

            return {"status": "success", "response": response}

        except Exception as e:
            self.logger.error(f"Error handling inter-agent message: {e}")
            return {"status": "error", "message": str(e)}

    async def _log_outgoing_message(
        self, to_agent: str, message: str
    ) -> Dict[str, Any]:
        """Log outgoing message to this agent's conversation history"""
        try:
            self.logger.info(f"Logging outgoing message to {to_agent}: {message}")

            # Add the sent message to this agent's conversation history as assistant message
            # This represents what this agent "said" to another agent
            self.shared_store["conversation_history"].append(
                {
                    "role": "assistant",
                    "content": message,
                    "timestamp": datetime.now().isoformat(),
                    "type": "inter_agent_outgoing",
                    "to": to_agent,
                }
            )

            return {
                "status": "success",
                "message": "Outgoing message logged to conversation history",
            }

        except Exception as e:
            self.logger.error(f"Error logging outgoing message: {e}")
            return {"status": "error", "message": str(e)}

    async def _send_message_to_daemon(self, command: str, args: Dict[str, Any]):
        """Send message to daemon process"""
        try:
            reader, writer = await asyncio.open_unix_connection(self.daemon_socket_path)

            # Send with length prefix
            message = {"command": command, "args": args}
            message_packed = msgpack.packb(message)
            length_prefix = len(message_packed).to_bytes(4, "big")
            writer.write(length_prefix + message_packed)
            await writer.drain()

            # Read response with length prefix
            length_bytes = await reader.readexactly(4)
            message_length = int.from_bytes(length_bytes, "big")
            response_data = await reader.readexactly(message_length)
            response = msgpack.unpackb(response_data, raw=False)

            writer.close()
            await writer.wait_closed()

            return response

        except Exception as e:
            self.logger.error(f"Error sending message to daemon: {e}")
            return {"status": "error", "message": str(e)}

    async def _register_with_daemon(self):
        """Register this agent process with the daemon"""
        try:
            registration_data = {
                "agent_name": self.agent_name,
                "instance_id": self.instance_id,
                "pid": self.pid,
                "socket_path": self.process_socket_path,
                "status": self.status,
                "spec": self.agent_spec,
            }

            response = await self._send_message_to_daemon(
                "register_agent_process", registration_data
            )

            if response.get("status") != "success":
                raise Exception(
                    f"Failed to register with daemon: {response.get('message')}"
                )

            self.logger.info("Successfully registered with daemon")

        except Exception as e:
            self.logger.error(f"Failed to register with daemon: {e}")
            raise

    async def _shutdown(self):
        """Shutdown agent process gracefully"""
        self.logger.info(f"Shutting down agent process: {self.instance_id}")

        # Stop IPC server
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Clean up socket file
        try:
            Path(self.process_socket_path).unlink(missing_ok=True)
        except Exception as e:
            self.logger.error(f"Error cleaning up socket: {e}")

        self.status = "stopped"
        self.logger.info(f"Agent process {self.instance_id} stopped")


async def main():
    """Main entry point for agent process"""
    if len(sys.argv) < 2:
        print("Usage: python -m ago.core.agent_process <config_json>")
        sys.exit(1)

    try:
        # Parse configuration from command line argument
        config_json = sys.argv[1]
        config = json.loads(config_json)

        # Create and start agent process
        agent_process = AgentProcess(
            agent_name=config["agent_name"],
            instance_id=config["instance_id"],
            agent_spec=config["agent_spec"],
            agent_template=config["agent_template"],
            agent_tools=config["agent_tools"],
            daemon_socket_path=config["daemon_socket_path"],
            process_socket_path=config["process_socket_path"],
        )

        await agent_process.start()

    except Exception as e:
        console.print(f"[red]Agent process failed: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
