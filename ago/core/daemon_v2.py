#!/usr/bin/env python3
"""
Ago Daemon v2 - Multi-process architecture with IPC
Background process that manages agent processes instead of in-memory agents
"""

import asyncio
import logging
import os
import signal
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import msgpack
import yaml
# Removed Rich import - daemon should not use Rich

# Import local modules
from .mcp_integration import get_tools_async
from .process_manager import ProcessManager
from .registry import registry

# Removed Rich console - daemon should not use Rich


class AgoDaemonV2:
    """Background daemon that manages AI agent processes"""

    def __init__(self, daemon_dir: Path = Path.home() / ".ago"):
        self.daemon_dir = daemon_dir
        self.daemon_dir.mkdir(exist_ok=True)

        # Daemon state files
        self.pid_file = self.daemon_dir / "daemon.pid"
        self.socket_file = self.daemon_dir / "daemon.sock"

        # Process manager for agent processes
        self.process_manager = ProcessManager(self.daemon_dir)

        # Global message history for CLI queues command
        self.message_history: list = []

        # Server and state
        self.server = None
        self.logger = logging.getLogger("ago.daemon.v2")
        self._shutdown_requested = False

        # Setup logging
        log_dir = self.daemon_dir / "logs"
        log_dir.mkdir(exist_ok=True, parents=True)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_dir / "daemon.log"),
                logging.StreamHandler(),
            ],
        )

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self._shutdown_requested = True

    async def start(self):
        """Start the daemon process"""
        # Check if already running
        if self.is_running():
            raise RuntimeError("Daemon already running")

        # Write PID file
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))

        self.logger.info("Ago daemon v2 starting...")

        # Start Unix socket server for CLI communication
        self.server = await asyncio.start_unix_server(
            self._handle_client, path=str(self.socket_file)
        )

        print("🚀 Ago daemon v2 started (Multi-Process Architecture)")
        print(f"PID: {os.getpid()}")
        print(f"Socket: {self.socket_file}")

        # Keep daemon running
        async with self.server:
            # Start serving in the background
            serve_task = asyncio.create_task(self.server.serve_forever())

            # Start health check loop
            health_check_task = asyncio.create_task(self._health_check_loop())

            # Check for shutdown signal
            while not self._shutdown_requested:
                await asyncio.sleep(0.1)

            # Cancel background tasks and shutdown
            serve_task.cancel()
            health_check_task.cancel()

            try:
                await serve_task
            except asyncio.CancelledError:
                pass

            try:
                await health_check_task
            except asyncio.CancelledError:
                pass

            await self.shutdown()

    async def _health_check_loop(self):
        """Periodic health check of agent processes"""
        while not self._shutdown_requested:
            try:
                await self.process_manager.health_check()
                await asyncio.sleep(10)  # Check every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health check error: {e}")
                await asyncio.sleep(5)

    async def shutdown(self):
        """Shutdown daemon gracefully"""
        self.logger.info("Shutting down daemon...")

        # Stop all agent processes
        await self.process_manager.cleanup()

        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Clean up files
        try:
            self.pid_file.unlink(missing_ok=True)
            self.socket_file.unlink(missing_ok=True)
        except Exception as e:
            self.logger.error(f"Error cleaning up: {e}")

        print("👋 Ago daemon v2 stopped")

    def is_running(self) -> bool:
        """Check if daemon is already running"""
        if not self.pid_file.exists():
            return False

        try:
            with open(self.pid_file, "r") as f:
                pid = int(f.read().strip())
            # Check if process exists
            os.kill(pid, 0)
            return True
        except (FileNotFoundError, ProcessLookupError, ValueError):
            # Clean up stale PID file
            self.pid_file.unlink(missing_ok=True)
            return False

    async def _handle_client(self, reader, writer):
        """Handle CLI client requests"""
        try:
            # Read message with length prefixing for reliable msgpack parsing
            try:
                # First, read 4-byte length prefix
                length_bytes = await reader.readexactly(4)
                message_length = int.from_bytes(length_bytes, "big")

                # Then read exact message length
                data = await reader.readexactly(message_length)
                if not data:
                    self.logger.warning("Received empty data from client")
                    return

                request = msgpack.unpackb(data, raw=False)

            except asyncio.IncompleteReadError as e:
                self.logger.error(
                    f"Incomplete read from client: expected {e.expected} bytes, got {len(e.partial)}"
                )
                return
            except Exception as e:
                self.logger.error(f"Failed to read client request: {e}")
                return

            command = request.get("command")
            
            # Handle streaming commands differently
            if command == "chat_message_streaming":
                # Process streaming command - returns async generator
                stream = await self._process_command(command, request.get("args", {}))
                
                # Forward each streaming response
                async for step in stream:
                    step_packed = msgpack.packb(step)
                    length_prefix = len(step_packed).to_bytes(4, "big")
                    writer.write(length_prefix + step_packed)
                    await writer.drain()
                    
                    # Stop after final step
                    if step.get("status") == "completed" or step.get("is_final", False):
                        break
            else:
                # Handle regular commands
                response = await self._process_command(command, request.get("args", {}))

                # Send response with length prefix
                response_packed = msgpack.packb(response)
                length_prefix = len(response_packed).to_bytes(4, "big")
                writer.write(length_prefix + response_packed)
                await writer.drain()

        except Exception as e:
            self.logger.error(f"Error handling client request: {e}")
            try:
                error_response = {"status": "error", "message": str(e)}
                error_packed = msgpack.packb(error_response)
                length_prefix = len(error_packed).to_bytes(4, "big")
                writer.write(length_prefix + error_packed)
                await writer.drain()
            except:
                pass  # Connection may be closed
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass  # Connection may already be closed

    async def _process_command(
        self, command: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process command from CLI client"""

        if command == "load_workflow":
            return await self._load_workflow(args["workflow_spec"])

        elif command == "run_single_agent":
            return await self._run_single_agent(
                args["template_name"],
                args.get("agent_name"),
                args.get("config", {})
            )

        elif command == "list_agents":
            return await self.process_manager.list_agents()

        elif command == "chat_message":
            return await self.process_manager.process_chat_message(
                args["agent_name"], args["message"]
            )
        
        elif command == "chat_message_streaming":
            # Return async generator for streaming
            return self.process_manager.process_chat_message_streaming(
                args["agent_name"], args["message"]
            )

        elif command == "get_agent_logs":
            return await self.process_manager.get_agent_logs(
                args["agent_name"], args.get("tail", 10)
            )

        elif command == "get_message_queues":
            return await self._get_message_queues(args.get("agent_name"))

        elif command == "send_inter_agent_message":
            # Log the message BEFORE sending it (so we capture it even if response fails)
            message = args["message"]
            if len(message) > 1000:
                message = message[:1000] + "..."

            # Pre-log the outgoing message
            message_entry = {
                "timestamp": datetime.now().isoformat(),
                "from": args["from_agent"],
                "to": args["to_agent"],
                "message": message,
                "status": "sending",
                "type": "message",
            }
            self.message_history.append(message_entry)

            # Send the message to the agent
            response = await self.process_manager.send_inter_agent_message(
                args["from_agent"], args["to_agent"], args["message"]
            )

            # Update the status based on response
            message_entry["status"] = response.get("status", "unknown")
            if response.get("status") == "timeout":
                message_entry["status"] = "timeout"
            elif response.get("status") == "error":
                message_entry["status"] = "error"
                message_entry["error"] = response.get("message", "Unknown error")
            else:
                message_entry["status"] = "sent"

            return response

        elif command == "stop_agent":
            return await self.process_manager.stop_agent_process(args["agent_name"])

        elif command == "stop_all_agents":
            return await self.process_manager.stop_all_agents()

        elif command == "start_agent":
            return await self._start_agent(args["workflow_spec"], args["agent_name"])

        elif command == "register_agent_process":
            return await self._register_agent_process(args)

        elif command == "inter_agent_response":
            return await self._handle_inter_agent_response(args)

        else:
            return {"status": "error", "message": f"Unknown command: {command}"}

    async def _load_workflow(self, workflow_spec: str) -> Dict[str, Any]:
        """Load agents from workflow specification"""
        try:
            spec_file = Path(workflow_spec)
            if not spec_file.exists():
                return {
                    "status": "error",
                    "message": f"Workflow spec not found: {workflow_spec}",
                }

            with open(spec_file, "r") as f:
                workflow = yaml.safe_load(f)

            # Load tools
            try:
                all_tools = await get_tools_async()
                self.logger.info(f"Loaded {len(all_tools)} tools")
            except Exception as e:
                self.logger.error(f"Failed to load tools: {e}")
                all_tools = []

            # Spawn agent processes
            loaded_agents = []
            for agent_spec in workflow["spec"]["agents"]:
                agent_name = agent_spec["name"]

                # Handle template reference
                template_ref = agent_spec.get("template")
                if not template_ref:
                    return {
                        "status": "error",
                        "message": f"Agent '{agent_name}' must specify a 'template' field",
                    }

                # Parse template reference
                if ":" in template_ref:
                    template_name, template_version = template_ref.split(":", 1)
                    template_version = template_version.lstrip("v")
                else:
                    template_name = template_ref
                    template_version = "latest"

                # Get template from registry
                template = registry.get_template(template_name, template_version)
                if not template:
                    return {
                        "status": "error",
                        "message": f"Template '{template_name}:v{template_version}' not found in registry",
                    }

                # Use template's embedded prompt content (prioritize prompt_content over prompt)
                agent_template = template.get(
                    "prompt_content",
                    template.get("prompt", "You are a helpful AI assistant."),
                )

                # Use template's configuration if not overridden
                if "tools" not in agent_spec:
                    agent_spec["tools"] = template.get("tools", [])
                if "model" not in agent_spec:
                    agent_spec["model"] = template.get(
                        "model", "claude-3-5-haiku-20241022"
                    )
                if "temperature" not in agent_spec and "temperature" in template:
                    agent_spec["temperature"] = template.get("temperature")

                # Filter tools
                requested_tools = agent_spec.get("tools", [])
                if requested_tools:
                    agent_tools = []
                    for tool in all_tools:
                        tool_name = tool.get("name", "").lower()
                        if any(req.lower() in tool_name for req in requested_tools):
                            agent_tools.append(tool)
                else:
                    agent_tools = all_tools

                # Spawn agent process
                result = await self.process_manager.spawn_agent_process(
                    agent_name,
                    agent_spec,
                    agent_template,
                    agent_tools,
                    str(self.socket_file),
                )

                if result["status"] != "success":
                    return {
                        "status": "error",
                        "message": f"Failed to spawn agent {agent_name}: {result['message']}",
                    }

                loaded_agents.append(agent_name)

            return {
                "status": "success",
                "message": f"Loaded {len(loaded_agents)} agents",
                "agents": loaded_agents,
            }

        except Exception as e:
            self.logger.error(f"Failed to load workflow: {e}")
            return {"status": "error", "message": str(e)}

    async def _run_single_agent(self, template_name: str, agent_name: Optional[str] = None, config: dict = None) -> Dict[str, Any]:
        """Run a single agent from template (like 'docker run image')"""
        try:
            # Generate agent name if not provided
            if not agent_name:
                import uuid
                agent_name = f"{template_name}-{uuid.uuid4().hex[:8]}"

            # Get template from registry
            template = registry.get_template(template_name, "latest")
            if not template:
                return {
                    "status": "error",
                    "message": f"Template '{template_name}' not found in registry"
                }

            # Check and install MCP dependencies
            from .mcp_dependency_manager import check_template_mcp_dependencies
            mcp_satisfied = await check_template_mcp_dependencies(template_name, template)
            if not mcp_satisfied:
                return {
                    "status": "error", 
                    "message": f"Template '{template_name}' has unsatisfied MCP dependencies"
                }

            # Load tools
            try:
                all_tools = await get_tools_async()
                self.logger.info(f"Loaded {len(all_tools)} tools")
            except Exception as e:
                self.logger.error(f"Failed to load tools: {e}")
                all_tools = []

            # Create agent spec from template + config overrides
            agent_spec = {
                "name": agent_name,
                "template": f"{template_name}:v{template.get('version', 'latest')}",
                "model": config.get("model", template.get("model", "claude-3-5-haiku-20241022")),
                "tools": config.get("tools", template.get("tools", [])),
                "temperature": config.get("temperature", template.get("temperature", 0.2)),
            }

            # Use template's embedded prompt content
            agent_template = template.get(
                "prompt_content",
                template.get("prompt", "You are a helpful AI assistant."),
            )

            # Filter tools based on agent spec using simple glob patterns
            requested_tools = agent_spec.get("tools", [])
            if requested_tools:
                import fnmatch
                agent_tools = []
                for tool in all_tools:
                    tool_name = tool.get("name", "")
                    for pattern in requested_tools:
                        if fnmatch.fnmatch(tool_name, pattern):
                            agent_tools.append(tool)
                            break  # Don't add same tool twice
            else:
                agent_tools = []

            # Spawn agent process using process manager
            result = await self.process_manager.spawn_agent_process(
                agent_name, agent_spec, agent_template, agent_tools, str(self.socket_file)
            )

            if result.get("status") == "success":
                return {
                    "status": "success",
                    "message": f"Agent '{agent_name}' started successfully",
                    "agent": {
                        "name": agent_name,
                        "template": template_name,
                        "model": agent_spec["model"],
                        "tools": [tool.get("name") for tool in agent_tools],
                    },
                }
            else:
                return result

        except Exception as e:
            self.logger.error(f"Failed to run single agent: {e}")
            return {"status": "error", "message": str(e)}

    async def _start_agent(self, workflow_spec: str, agent_name: str) -> Dict[str, Any]:
        """Start a single agent from workflow spec"""
        # This is a simplified version that loads just one agent
        # For now, delegate to _load_workflow and filter
        return {"status": "error", "message": "Single agent start not implemented yet"}

    async def _register_agent_process(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle agent process registration"""
        try:
            agent_name = args["agent_name"]
            pid = args["pid"]

            self.logger.info(f"Agent process {agent_name} registered with PID {pid}")

            return {"status": "success", "message": "Agent registered"}
        except Exception as e:
            self.logger.error(f"Failed to register agent process: {e}")
            return {"status": "error", "message": str(e)}

    async def _handle_inter_agent_response(
        self, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle response from one agent to another"""
        try:
            from_agent = args["from_agent"]
            to_agent = args["to_agent"]
            message = args["message"]

            # Forward the clean response to the target agent (no prefixes)
            response = await self.process_manager.send_inter_agent_message(
                from_agent, to_agent, message
            )

            # Log the response (truncate long messages to avoid JSON issues)
            response_message = str(message)
            if len(response_message) > 1000:
                response_message = response_message[:1000] + "..."

            self.message_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "from": from_agent,
                    "to": to_agent,
                    "message": response_message,
                    "status": response.get("status", "unknown"),
                    "type": "response",
                }
            )

            return {"status": "success", "message": "Response forwarded"}
        except Exception as e:
            self.logger.error(f"Failed to handle inter-agent response: {e}")
            return {"status": "error", "message": str(e)}

    async def _get_message_queues(
        self, agent_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get message queue information"""
        try:
            if agent_name:
                # Filter messages for specific agent
                agent_messages = [
                    msg
                    for msg in self.message_history
                    if msg.get("from") == agent_name or msg.get("to") == agent_name
                ]
                return {"status": "success", "messages": agent_messages}
            else:
                # Return all messages
                return {"status": "success", "messages": self.message_history}
        except Exception as e:
            self.logger.error(f"Failed to get message queues: {e}")
            return {"status": "error", "message": str(e)}
