#!/usr/bin/env python3
"""
Ago Process Manager - Manages agent processes and IPC communication
"""

import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import msgpack
from rich.console import Console

console = Console()


class ProcessManager:
    """Manages agent processes and their lifecycle"""

    def __init__(self, daemon_dir: Path):
        self.daemon_dir = daemon_dir
        self.processes_dir = daemon_dir / "processes"
        self.processes_dir.mkdir(exist_ok=True, parents=True)

        # Process registry: instance_id -> process info
        self.agent_instances: Dict[str, Dict[str, Any]] = {}

        # Agent type mapping: agent_type -> [instance_ids]
        self.agent_types: Dict[str, List[str]] = {}

        # Setup logging
        self.logger = logging.getLogger("ago.process_manager")

    async def spawn_agent_process(
        self,
        agent_name: str,  # This is the agent type (e.g., "researcher")
        agent_spec: Dict[str, Any],
        agent_template: str,
        agent_tools: List[Dict[str, Any]],
        daemon_socket_path: str,
    ) -> Dict[str, Any]:
        """Spawn a new agent process with unique instance ID"""
        try:
            # Generate unique instance ID: agent_name + short UUID
            instance_id = f"{agent_name}-{uuid.uuid4().hex[:8]}"

            self.logger.info(f"Spawning agent process: {agent_name} -> {instance_id}")

            # Create process-specific socket path using instance ID
            process_socket_path = str(self.processes_dir / f"{instance_id}.sock")

            # Prepare configuration for the agent process
            agent_config = {
                "agent_name": agent_name,  # Agent type
                "instance_id": instance_id,  # Unique instance identifier
                "agent_spec": agent_spec,
                "agent_template": agent_template,
                "agent_tools": agent_tools,
                "daemon_socket_path": daemon_socket_path,
                "process_socket_path": process_socket_path,
            }

            # Convert config to JSON string for command line
            config_json = json.dumps(agent_config)

            # Python executable and module path
            python_executable = sys.executable
            module_path = "ago.core.agent_process"

            # Spawn the agent process
            process = await asyncio.create_subprocess_exec(
                python_executable,
                "-m",
                module_path,
                config_json,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.daemon_dir.parent,  # Run from ago package directory
            )

            # Store process information with instance ID
            self.agent_instances[instance_id] = {
                "instance_id": instance_id,
                "agent_name": agent_name,  # Agent type
                "pid": process.pid,
                "process": process,
                "socket_path": process_socket_path,
                "spec": agent_spec,
                "status": "starting",
                "created_at": datetime.now().isoformat(),
                "restart_count": 0,
            }

            # Update agent type mapping
            if agent_name not in self.agent_types:
                self.agent_types[agent_name] = []
            self.agent_types[agent_name].append(instance_id)

            self.logger.info(
                f"Spawned agent process {agent_name} -> {instance_id} with PID: {process.pid}"
            )

            # Wait briefly for process to initialize
            await asyncio.sleep(0.5)

            # Check if process is still running
            if process.returncode is not None:
                stdout, stderr = await process.communicate()
                error_msg = f"Process failed immediately: {stderr.decode()}"
                self.logger.error(error_msg)
                return {"status": "error", "message": error_msg}

            return {
                "status": "success",
                "message": f"Agent process {agent_name} spawned successfully as {instance_id}",
                "instance_id": instance_id,
                "agent_name": agent_name,
                "pid": process.pid,
            }

        except Exception as e:
            self.logger.error(f"Failed to spawn agent process {agent_name}: {e}")
            return {"status": "error", "message": str(e)}

    async def stop_agent_process(self, identifier: str) -> Dict[str, Any]:
        """Stop an agent process by instance ID or agent name (stops all instances)"""
        try:
            instances_to_stop = []

            # Check if identifier is an instance ID
            if identifier in self.agent_instances:
                instances_to_stop.append(identifier)
            # Otherwise, treat as agent name and stop all instances
            elif identifier in self.agent_types:
                instances_to_stop.extend(self.agent_types[identifier])
            else:
                return {
                    "status": "error",
                    "message": f"Agent or instance {identifier} not found",
                }

            stopped_instances = []
            for instance_id in instances_to_stop:
                result = await self._stop_single_instance(instance_id)
                if result["status"] == "success":
                    stopped_instances.append(instance_id)

            if stopped_instances:
                return {
                    "status": "success",
                    "message": f"Stopped {len(stopped_instances)} instance(s)",
                    "stopped_instances": stopped_instances,
                }
            else:
                return {"status": "error", "message": "Failed to stop any instances"}

        except Exception as e:
            self.logger.error(f"Failed to stop agent process {identifier}: {e}")
            return {"status": "error", "message": str(e)}

    async def _stop_single_instance(self, instance_id: str) -> Dict[str, Any]:
        """Stop a single agent instance"""
        try:
            if instance_id not in self.agent_instances:
                return {
                    "status": "error",
                    "message": f"Instance {instance_id} not found",
                }

            process_info = self.agent_instances[instance_id]
            process = process_info["process"]
            pid = process_info["pid"]
            agent_name = process_info["agent_name"]

            self.logger.info(f"Stopping agent instance: {instance_id} (PID: {pid})")

            # Send stop command via IPC first (graceful shutdown)
            try:
                await self.send_ipc_message(instance_id, "stop", {})
                # Wait briefly for graceful shutdown
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # If graceful shutdown fails, terminate forcefully
                self.logger.warning(
                    f"Graceful shutdown timeout, terminating {instance_id}"
                )
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    # Last resort: kill
                    process.kill()
                    await process.wait()

            # Clean up
            socket_path = Path(process_info["socket_path"])
            socket_path.unlink(missing_ok=True)

            # Remove from registries
            del self.agent_instances[instance_id]

            # Remove from agent type mapping
            if agent_name in self.agent_types:
                self.agent_types[agent_name].remove(instance_id)
                if not self.agent_types[agent_name]:  # No more instances
                    del self.agent_types[agent_name]

            self.logger.info(f"Stopped agent instance: {instance_id}")
            return {"status": "success", "message": f"Instance {instance_id} stopped"}

        except Exception as e:
            self.logger.error(f"Failed to stop agent instance {instance_id}: {e}")
            return {"status": "error", "message": str(e)}

    async def stop_all_agents(self) -> Dict[str, Any]:
        """Stop all agent instances"""
        stopped_instances = []
        failed_instances = []

        for instance_id in list(self.agent_instances.keys()):
            result = await self._stop_single_instance(instance_id)
            if result["status"] == "success":
                stopped_instances.append(instance_id)
            else:
                failed_instances.append(instance_id)

        return {
            "status": "success",
            "message": f"Stopped {len(stopped_instances)} instances",
            "stopped": stopped_instances,
            "failed": failed_instances,
        }

    async def send_ipc_message(
        self, identifier: str, command: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send IPC message to an agent instance (by instance ID or agent name - picks first instance)"""
        try:
            # Determine instance ID to send to
            instance_id = None
            if identifier in self.agent_instances:
                instance_id = identifier
            elif identifier in self.agent_types and self.agent_types[identifier]:
                # Pick first instance of this agent type
                instance_id = self.agent_types[identifier][0]
            else:
                return {
                    "status": "error",
                    "message": f"Agent or instance {identifier} not found",
                }

            process_info = self.agent_instances[instance_id]
            socket_path = process_info["socket_path"]

            # Check if socket exists
            if not Path(socket_path).exists():
                return {
                    "status": "error",
                    "message": f"Instance {instance_id} socket not found",
                }

            self.logger.info(f"Attempting to send IPC to {identifier} -> {instance_id}")
            self.logger.info(f"Socket path exists: {Path(socket_path).exists()}")
            self.logger.info(f"Command: {command}, Args: {args}")

            try:
                # Connect to agent process socket
                reader, writer = await asyncio.open_unix_connection(socket_path)

                # Send message with length prefix
                message = {"command": command, "args": args}
                message_packed = msgpack.packb(message)
                length_prefix = len(message_packed).to_bytes(4, "big")
                writer.write(length_prefix + message_packed)
                await writer.drain()

                self.logger.debug(
                    f"Message sent to {instance_id}, waiting for response..."
                )

                # Read response with timeout (shorter for send commands, longer for chat with tools)
                if command == "send_inter_agent_message":
                    timeout_duration = 15.0
                elif command == "process_chat_message":
                    timeout_duration = 60.0  # Longer timeout for ReAct flows with multiple tool calls
                else:
                    timeout_duration = 30.0
                try:
                    # Read response with length prefixing
                    length_bytes = await asyncio.wait_for(
                        reader.readexactly(4), timeout=timeout_duration
                    )
                    message_length = int.from_bytes(length_bytes, "big")

                    response_data = await asyncio.wait_for(
                        reader.readexactly(message_length), timeout=timeout_duration
                    )
                    if not response_data:
                        self.logger.warning(f"Empty response from {instance_id}")
                        return {
                            "status": "error",
                            "message": f"Agent {instance_id} sent empty response",
                        }

                    response = msgpack.unpackb(response_data, raw=False)
                    self.logger.debug(
                        f"Received response from {instance_id}: {response.get('status', 'unknown')}"
                    )

                except asyncio.TimeoutError:
                    self.logger.warning(
                        f"IPC timeout for {instance_id}, command: {command} ({timeout_duration}s timeout)"
                    )
                    response = {
                        "status": "timeout",
                        "message": f"Agent {instance_id} did not respond within {timeout_duration} seconds",
                    }
                except asyncio.IncompleteReadError as e:
                    self.logger.error(
                        f"Incomplete read from {instance_id}: expected {e.expected} bytes, got {len(e.partial)}"
                    )
                    response = {
                        "status": "error",
                        "message": f"Connection closed unexpectedly from agent {instance_id}",
                    }
                except Exception as e:
                    self.logger.error(
                        f"Invalid msgpack response from {instance_id}: {e}"
                    )
                    response = {
                        "status": "error",
                        "message": f"Invalid response from agent: {e}",
                    }

                # Clean up connection
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception as e:
                    self.logger.debug(f"Error closing connection to {instance_id}: {e}")

                return response

            except (ConnectionRefusedError, FileNotFoundError) as e:
                self.logger.error(f"Cannot connect to {instance_id}: {e}")
                return {
                    "status": "error",
                    "message": f"Cannot connect to agent {instance_id}: {e}",
                }
            except Exception as e:
                self.logger.error(
                    f"Unexpected error communicating with {instance_id}: {e}"
                )
                return {
                    "status": "error",
                    "message": f"Communication error with agent {instance_id}: {e}",
                }

        except Exception as e:
            self.logger.error(f"Failed to send IPC message to {identifier}: {e}")
            return {"status": "error", "message": str(e)}

    async def get_agent_status(self, identifier: str) -> Dict[str, Any]:
        """Get status of an agent instance"""
        try:
            # Determine instance to check
            instance_id = None
            if identifier in self.agent_instances:
                instance_id = identifier
            elif identifier in self.agent_types and self.agent_types[identifier]:
                instance_id = self.agent_types[identifier][0]  # Check first instance
            else:
                return {
                    "status": "error",
                    "message": f"Agent or instance {identifier} not found",
                }

            # Send ping to check if process is responsive
            response = await self.send_ipc_message(instance_id, "ping", {})

            if response.get("status") == "success":
                process_info = self.agent_instances[instance_id]
                return {
                    "status": "success",
                    "agent_status": "running",
                    "instance_id": instance_id,
                    "agent_name": process_info["agent_name"],
                    "pid": process_info["pid"],
                    "created_at": process_info["created_at"],
                    "spec": process_info["spec"],
                }
            else:
                # Process not responding
                return {
                    "status": "error",
                    "message": f"Instance {instance_id} not responding",
                }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def list_agents(self) -> Dict[str, Any]:
        """List all agent instances"""
        agents_dict = {}

        for instance_id, process_info in self.agent_instances.items():
            # Check if process is still alive
            process = process_info["process"]
            if process.returncode is None:  # Still running
                status = "running"
            else:
                status = "stopped"

            agents_dict[instance_id] = {
                "instance_id": instance_id,
                "agent_name": process_info["agent_name"],
                "pid": process_info["pid"],
                "status": status,
                "created_at": process_info["created_at"],
                "spec": process_info["spec"],
                "model": process_info["spec"].get("model", "unknown"),
                "tools": process_info["spec"].get("tools", []),
            }

        return {"status": "success", "agents": agents_dict}

    async def process_chat_message(
        self, agent_name: str, message: str
    ) -> Dict[str, Any]:
        """Send chat message to agent process"""
        return await self.send_ipc_message(
            agent_name, "process_chat_message", {"message": message}
        )

    async def get_agent_logs(self, agent_name: str, tail: int = 10) -> Dict[str, Any]:
        """Get agent conversation history"""
        response = await self.send_ipc_message(
            agent_name, "get_conversation_history", {}
        )

        if response.get("status") == "success":
            history = response.get("history", [])
            # Return last 'tail' entries
            if tail > 0:
                history = history[-tail:]

            return {"status": "success", "logs": history}
        else:
            return response

    async def send_inter_agent_message(
        self, from_agent: str, to_agent: str, message: str
    ) -> Dict[str, Any]:
        """Send message between agent processes (fire-and-forget for better performance)"""
        try:
            # Fire-and-forget: Start message delivery in background task
            # This prevents blocking on agent LLM processing time (which can take 15-30+ seconds)
            asyncio.create_task(
                self._deliver_inter_agent_message(from_agent, to_agent, message)
            )

            return {
                "status": "sent",
                "message": f"Message sent from {from_agent} to {to_agent}",
                "note": "Agent response will appear in message queues. Use 'ago queues --follow' to monitor."
            }

        except Exception as e:
            self.logger.error(f"Error starting inter-agent message delivery: {e}")
            return {"status": "error", "message": str(e)}

    async def _deliver_inter_agent_message(
        self, from_agent: str, to_agent: str, message: str
    ) -> None:
        """Internal method to deliver inter-agent message (runs in background)"""
        try:
            # 1. FIRST: Log outgoing message to sender's conversation history
            # This ensures the sender remembers what they "said" BEFORE any responses
            sender_response = await self.send_ipc_message(
                from_agent,
                "log_outgoing_message", 
                {"to_agent": to_agent, "message": message},
            )

            # Log if sender logging failed (but don't fail the main operation)
            if sender_response.get("status") != "success":
                self.logger.warning(
                    f"Failed to log outgoing message for sender {from_agent}: {sender_response.get('message')}"
                )

            # 2. THEN: Send message to receiving agent (this may take time for LLM processing)
            response = await self.send_ipc_message(
                to_agent,
                "send_inter_agent_message",
                {"from_agent": from_agent, "message": message},
            )

            if response.get("status") == "success":
                self.logger.info(f"Inter-agent message delivered: {from_agent} → {to_agent}")
            else:
                self.logger.error(f"Inter-agent message failed: {from_agent} → {to_agent}: {response.get('message')}")

        except Exception as e:
            self.logger.error(f"Error in background inter-agent message delivery: {e}")

    async def test_agent_ping(self, agent_name: str) -> Dict[str, Any]:
        """Test basic IPC communication with an agent"""
        response = await self.send_ipc_message(agent_name, "ping", {})
        self.logger.info(f"Ping response from {agent_name}: {response}")
        return response

    async def health_check(self):
        """Perform health check on all agent instances"""
        for instance_id in list(self.agent_instances.keys()):
            process_info = self.agent_instances[instance_id]
            process = process_info["process"]
            agent_name = process_info["agent_name"]

            # Check if process is still alive
            if process.returncode is not None:
                self.logger.warning(
                    f"Agent instance {instance_id} ({agent_name}) has died (exit code: {process.returncode})"
                )

                # TODO: Implement auto-restart logic here
                # For now, just remove from registry
                socket_path = Path(process_info["socket_path"])
                socket_path.unlink(missing_ok=True)

                # Clean up from both registries
                del self.agent_instances[instance_id]
                if agent_name in self.agent_types:
                    self.agent_types[agent_name].remove(instance_id)
                    if not self.agent_types[agent_name]:  # No more instances
                        del self.agent_types[agent_name]

    async def cleanup(self):
        """Clean up all processes and resources"""
        self.logger.info("Cleaning up all agent processes")

        await self.stop_all_agents()

        # Clean up process directory
        for socket_file in self.processes_dir.glob("*.sock"):
            socket_file.unlink(missing_ok=True)
