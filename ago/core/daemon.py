#!/usr/bin/env python3
"""
Ago Daemon - Background process that manages running agents
Like Docker daemon but for AI agents
"""

import asyncio
import json
import logging
import os
import signal
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from rich.console import Console

from ..agents.agent_react_flow import create_agent_flow

# Import local modules
from .mcp_integration import get_tools_async
from .registry import registry

console = Console()


class AgoDaemon:
    """Background daemon that manages AI agents"""

    def __init__(self, daemon_dir: Path = Path.home() / ".ago"):
        self.daemon_dir = daemon_dir
        self.daemon_dir.mkdir(exist_ok=True)

        # Daemon state files
        self.pid_file = self.daemon_dir / "daemon.pid"
        self.socket_file = self.daemon_dir / "daemon.sock"
        self.agents_file = self.daemon_dir / "agents.json"

        # Runtime state - PocketFlow agents
        self.agents: Dict[str, Any] = {}  # agent_name -> {flow, shared_store, spec}
        self.message_history: list = []  # global message history for CLI queues command
        self.server = None
        self.logger = logging.getLogger("ago.daemon")
        self._shutdown_requested = False

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        # Set a flag to stop the main loop
        self._shutdown_requested = True

    async def start(self):
        """Start the daemon process"""
        # Check if already running
        if self.is_running():
            raise RuntimeError("Daemon already running")

        # Load environment variables from config
        from .config import config
        config.load_env_from_config()

        # Write PID file
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))

        # Ensure message_history is initialized as a list
        if not isinstance(self.message_history, list):
            self.message_history = []

        self.logger.info("Ago daemon starting...")

        # Start Unix socket server for CLI communication
        self.server = await asyncio.start_unix_server(
            self._handle_client, path=str(self.socket_file)
        )

        console.print("🚀 Ago daemon started")
        console.print(f"PID: {os.getpid()}")
        console.print(f"Socket: {self.socket_file}")

        # Keep daemon running
        async with self.server:
            # Start serving in the background
            serve_task = asyncio.create_task(self.server.serve_forever())

            # No inbox processing needed - using flow-per-message pattern

            # Check for shutdown signal
            while not self._shutdown_requested:
                await asyncio.sleep(0.1)

            # Cancel background tasks and shutdown
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass

            await self.shutdown()

    async def shutdown(self):
        """Shutdown daemon gracefully"""
        self.logger.info("Shutting down daemon...")

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

        console.print("👋 Ago daemon stopped")

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
            data = await reader.read(8192)
            if not data:
                self.logger.warning("Received empty data from client")
                return

            request = json.loads(data.decode())

            command = request.get("command")
            response = await self._process_command(command, request.get("args", {}))

            writer.write(json.dumps(response).encode())
            await writer.drain()

        except Exception as e:
            self.logger.error(f"Error handling client request: {e}")
            try:
                error_response = {"status": "error", "message": str(e)}
                writer.write(json.dumps(error_response).encode())
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

        elif command == "list_agents":
            return await self._list_agents()

        elif command == "run_single_agent":
            return await self._run_single_agent(
                args["template_name"],
                args.get("agent_name"),
                args.get("config", {})
            )

        elif command == "chat_message":
            return await self._process_chat_message(args["agent_name"], args["message"])

        elif command == "get_agent_logs":
            return await self._get_agent_logs(args["agent_name"], args.get("tail", 10))

        elif command == "get_message_queues":
            return await self._get_message_queues(args.get("agent_name"))

        elif command == "send_inter_agent_message":
            await self.send_inter_agent_message(
                args["from_agent"], args["to_agent"], args["message"]
            )
            return {"status": "success", "message": "Message sent"}

        elif command == "stop_agent":
            return await self._stop_agent(args["agent_name"])

        elif command == "stop_all_agents":
            return await self._stop_all_agents()

        elif command == "start_agent":
            return await self._start_agent(args["workflow_spec"], args["agent_name"])

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

            # Create agents
            loaded_agents = []
            for agent_spec in workflow["spec"]["agents"]:
                agent_name = agent_spec["name"]

                # Handle template reference - all agents now use templates
                template_ref = agent_spec.get("template")
                if not template_ref:
                    return {
                        "status": "error",
                        "message": f"Agent '{agent_name}' must specify a 'template' field",
                    }

                # Parse template reference (e.g., "researcher:v1.0" or "researcher")
                if ":" in template_ref:
                    template_name, template_version = template_ref.split(":", 1)
                    template_version = template_version.lstrip("v")  # Remove v prefix
                else:
                    template_name = template_ref
                    template_version = "latest"

                # Get template from registry (local → global → remote)
                template = registry.get_template(template_name, template_version)
                if not template:
                    return {
                        "status": "error",
                        "message": f"Template '{template_name}:v{template_version}' not found in registry",
                    }

                # Use template's embedded prompt content
                agent_template = template.get(
                    "prompt",
                    template.get("prompt_content", "You are a helpful AI assistant."),
                )

                # Use template's tools if not overridden in agent_spec
                if "tools" not in agent_spec:
                    agent_spec["tools"] = template.get("tools", [])

                # Use template's model if not overridden in agent_spec
                if "model" not in agent_spec:
                    agent_spec["model"] = template.get(
                        "model", "claude-3-5-haiku-20241022"
                    )

                # Use template's temperature if not overridden
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

                # Create PocketFlow agent with ReAct intelligence
                agent_flow = create_agent_flow(
                    agent_name, agent_spec, agent_template, agent_tools
                )

                # Create shared store following nator pattern
                shared_store = {
                    "conversation_history": [],
                    "tools": agent_tools,
                    "supervisor_scratchpad": "",
                    "user_message": "",
                    "assistant_response": "",
                    "inter_agent_message": {},
                    "delegation_request": None,
                    "response_to_send": None,
                }

                # Store PocketFlow agent state
                self.agents[agent_name] = {
                    "name": agent_name,
                    "spec": agent_spec,
                    "flow": agent_flow,  # PocketFlow ReAct agent
                    "shared_store": shared_store,  # Conversation memory
                    "tools": agent_tools,
                    "status": "running",
                    "created_at": datetime.now().isoformat(),
                }

                loaded_agents.append(agent_name)

            # Persist agent state
            self._save_agents_state()

            return {
                "status": "success",
                "message": f"Loaded {len(loaded_agents)} agents",
                "agents": loaded_agents,
            }

        except Exception as e:
            self.logger.error(f"Failed to load workflow: {e}")
            return {"status": "error", "message": str(e)}

    async def _list_agents(self) -> Dict[str, Any]:
        """List all running PocketFlow agents"""
        # Return agents in the format expected by the CLI (dict of agents)
        agents_dict = {}
        for agent_name, agent_data in self.agents.items():
            agents_dict[agent_name] = {
                "model": agent_data["spec"].get("model", "unknown"),
                "tools": agent_data.get("tools", []),
                "conversation_history": agent_data["shared_store"][
                    "conversation_history"
                ],
                "status": agent_data["status"],
                "created_at": agent_data["created_at"],
            }

        return agents_dict

    async def _process_chat_message(
        self, agent_name: str, message: str
    ) -> Dict[str, Any]:
        """Process chat message using PocketFlow ReAct agent (flow-per-message pattern)"""
        if agent_name not in self.agents:
            return {
                "status": "error",
                "message": f"Agent '{agent_name}' not found",
            }

        agent_data = self.agents[agent_name]

        try:
            # Update shared store with new message (like FastAPI WebSocket example)
            agent_data["shared_store"]["user_message"] = message

            # Clear any previous response
            agent_data["shared_store"]["assistant_response"] = ""

            # Run PocketFlow ReAct agent (triggers complete ReAct reasoning cycle)
            self.logger.info(
                f"Running ReAct flow for {agent_name} with message: {message[:50]}..."
            )
            await agent_data["flow"].run_async(agent_data["shared_store"])

            # Extract response from shared store
            response = agent_data["shared_store"].get(
                "assistant_response", "I'm not sure how to respond."
            )

            # Handle delegation requests from ReAct agent
            delegation_request = agent_data["shared_store"].get("delegation_request")
            if delegation_request:
                await self._handle_delegation_request(agent_name, delegation_request)
                agent_data["shared_store"]["delegation_request"] = None  # Clear request

            # Persist state
            self._save_agents_state()

            return {"status": "success", "response": response}

        except Exception as e:
            self.logger.error(f"ReAct flow processing failed for {agent_name}: {e}")
            return {"status": "error", "message": str(e)}

    async def _get_agent_logs(self, agent_name: str, tail: int) -> Dict[str, Any]:
        """Get conversation logs for PocketFlow agent"""
        if agent_name not in self.agents:
            return {
                "status": "error",
                "message": f"Agent '{agent_name}' not found",
            }

        agent_data = self.agents[agent_name]
        conversation_history = agent_data["shared_store"]["conversation_history"]

        logs = conversation_history[-tail:] if tail > 0 else conversation_history

        return {"status": "success", "logs": logs}

    async def _stop_agent(self, agent_name: str) -> Dict[str, Any]:
        """Stop specific agent"""
        if agent_name not in self.agents:
            return {
                "status": "error",
                "message": f"Agent '{agent_name}' not found",
            }

        del self.agents[agent_name]
        self._save_agents_state()

        return {"status": "success", "message": f"Agent '{agent_name}' stopped"}

    async def _stop_all_agents(self) -> Dict[str, Any]:
        """Stop all running agents but keep daemon running"""
        if not self.agents:
            return {"status": "success", "message": "No agents currently running"}

        agent_count = len(self.agents)
        agent_names = list(self.agents.keys())

        # Clear all agents
        self.agents.clear()
        self._save_agents_state()

        return {
            "status": "success",
            "message": f"Stopped {agent_count} agents: {', '.join(agent_names)}",
        }

    async def _start_agent(self, workflow_spec: str, agent_name: str) -> Dict[str, Any]:
        """Start a single agent from workflow spec"""
        try:
            # Check if agent already exists
            if agent_name in self.agents:
                return {
                    "status": "error",
                    "message": f"Agent '{agent_name}' already exists",
                }

            # Load workflow spec
            spec_file = Path(workflow_spec)
            if not spec_file.exists():
                return {
                    "status": "error",
                    "message": f"Workflow spec not found: {workflow_spec}",
                }

            with open(spec_file, "r") as f:
                workflow = yaml.safe_load(f)

            # Find the specific agent in the workflow
            agent_spec = None
            for agent in workflow["spec"]["agents"]:
                if agent["name"] == agent_name:
                    agent_spec = agent
                    break

            if not agent_spec:
                return {
                    "status": "error",
                    "message": f"Agent '{agent_name}' not found in {workflow_spec}",
                }

            # Load template from registry (all agents now use templates)
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

            # Use template's embedded prompt
            agent_template = template.get(
                "prompt",
                template.get("prompt_content", "You are a helpful AI assistant."),
            )

            # Apply template defaults to agent_spec if not overridden
            if "tools" not in agent_spec:
                agent_spec["tools"] = template.get("tools", [])
            if "model" not in agent_spec:
                agent_spec["model"] = template.get("model", "claude-3-5-haiku-20241022")

            # Load tools
            try:
                all_tools = await get_tools_async()
                self.logger.info(
                    f"Loaded {len(all_tools)} tools for agent {agent_name}"
                )
            except Exception as e:
                self.logger.error(f"Failed to load tools: {e}")
                all_tools = []

            # Filter tools if specified
            requested_tools = agent_spec.get("tools", [])
            if requested_tools:
                agent_tools = []
                for tool in all_tools:
                    tool_name = tool.get("name", "").lower()
                    if any(req.lower() in tool_name for req in requested_tools):
                        agent_tools.append(tool)
            else:
                agent_tools = all_tools

            # Create PocketFlow agent with ReAct intelligence
            agent_flow = create_agent_flow(
                agent_name, agent_spec, agent_template, agent_tools
            )

            # Create shared store following nator pattern
            shared_store = {
                "conversation_history": [],
                "tools": agent_tools,
                "supervisor_scratchpad": "",
                "user_message": "",
                "assistant_response": "",
                "inter_agent_message": {},
                "delegation_request": None,
            }

            # Store PocketFlow agent state
            self.agents[agent_name] = {
                "name": agent_name,
                "spec": agent_spec,
                "flow": agent_flow,  # PocketFlow ReAct agent
                "shared_store": shared_store,  # Conversation memory
                "tools": agent_tools,
                "status": "running",
                "created_at": datetime.now().isoformat(),
            }

            # Persist agent state
            self._save_agents_state()

            self.logger.info(
                f"Started agent: {agent_name} from workflow {workflow_spec}"
            )

            return {
                "status": "success",
                "message": f"Agent '{agent_name}' started from workflow '{workflow_spec}'",
                "agent": agent_name,
            }

        except Exception as e:
            self.logger.error(f"Failed to start agent: {e}")
            return {
                "status": "error",
                "message": f"Failed to start agent: {str(e)}",
            }

    async def _get_message_queues(
        self, agent_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get agent message status for PocketFlow agents"""
        try:
            queues_info = []

            # Show each agent's message status
            for agent_name_key, agent_data in self.agents.items():
                # Find the last message TO this agent
                agent_messages = [
                    msg
                    for msg in self.message_history
                    if msg.get("to") == agent_name_key
                ]
                if agent_messages:
                    last_msg = agent_messages[-1]["content"]
                    if len(last_msg) > 30:
                        last_msg = last_msg[:30] + "..."
                else:
                    last_msg = "No messages"

                queues_info.append(
                    {
                        "agent_name": agent_name_key,
                        "inbox_size": 0,  # Not using queues in flow-per-message pattern
                        "total_received": len(agent_messages),
                        "last_message": last_msg,
                        "status": "active" if agent_messages else "idle",
                    }
                )

            result = {"status": "success", "queues": queues_info}

            # Always include recent messages for follow mode to work
            result["messages"] = self.message_history[-20:]  # Last 20 messages

            return result

        except Exception as e:
            self.logger.error(f"Failed to get message queues: {e}")
            return {
                "status": "error",
                "message": f"Failed to get message queues: {str(e)}",
            }

    async def send_inter_agent_message(
        self, from_agent: str, to_agent: str, content: str
    ):
        """Send message between PocketFlow agents using BaseAgentNode inbox"""
        if to_agent not in self.agents:
            raise ValueError(f"Agent {to_agent} not found")

        target_agent_data = self.agents[to_agent]

        # Create inter-agent message
        message = {
            "from": from_agent,
            "to": to_agent,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "type": "inter_agent",
        }

        # Add to global message history for queues command
        self.message_history.append(message)

        # Set inter-agent message in target agent's shared store
        target_agent_data["shared_store"]["inter_agent_message"] = message

        # Trigger flow run for target agent (flow-per-message pattern)
        self.logger.info(
            f"📨 {from_agent} → {to_agent}: {content[:50]}... (triggering ReAct flow)"
        )

        try:
            await target_agent_data["flow"].run_async(target_agent_data["shared_store"])

            # Check if there's a response to send back
            response_to_send = target_agent_data["shared_store"].get("response_to_send")
            if response_to_send and from_agent in self.agents:
                # Send response back to originating agent
                self.logger.info(f"📤 Sending response back: {to_agent} → {from_agent}")

                from_agent_data = self.agents[from_agent]

                # Create response message
                response_message = {
                    "from": response_to_send["from"],
                    "to": response_to_send["to"],
                    "content": response_to_send["content"],
                    "timestamp": datetime.now().isoformat(),
                    "type": "inter_agent_response",
                }

                # Add to global message history
                self.message_history.append(response_message)

                # Set response in originating agent's shared store
                from_agent_data["shared_store"]["inter_agent_message"] = (
                    response_message
                )

                # Trigger flow run for originating agent to process the response
                try:
                    await from_agent_data["flow"].run_async(
                        from_agent_data["shared_store"]
                    )
                    # Clear the response message after processing
                    from_agent_data["shared_store"]["inter_agent_message"] = {}
                    self.logger.info(f"✅ Response processed by {from_agent}")
                except Exception as e:
                    self.logger.error(
                        f"Failed to process response in {from_agent}: {e}"
                    )

                # Clear the response from target agent's store
                target_agent_data["shared_store"]["response_to_send"] = None

            # Clear inter-agent message after processing
            target_agent_data["shared_store"]["inter_agent_message"] = {}

            # Save state
            self._save_agents_state()

        except Exception as e:
            self.logger.error(
                f"Failed to process inter-agent message for {to_agent}: {e}"
            )

        self.logger.info(f"✅ Inter-agent message processed by {to_agent}")

    async def _handle_delegation_request(
        self, from_agent: str, delegation_request: Dict[str, Any]
    ):
        """Handle task delegation between ReAct agents"""
        task_description = delegation_request.get("task_description", "")

        # For now, just log the delegation request
        # In future, this could route to appropriate agents based on capabilities
        self.logger.info(
            f"Delegation request from {from_agent}: {task_description[:100]}..."
        )

        # Could implement routing logic here:
        # - Find best agent for task based on spec/capabilities
        # - Create coordination messages
        # - Manage multi-agent workflows

        # For now, just add to message history for visibility in queues
        delegation_message = {
            "from": from_agent,
            "to": "system",
            "content": f"DELEGATION REQUEST: {task_description}",
            "timestamp": datetime.now().isoformat(),
            "type": "delegation",
        }
        self.message_history.append(delegation_message)

    def _save_agents_state(self):
        """Persist agents state to disk (only serializable data)"""
        try:
            # Create serializable version of agent state
            serializable_agents = {}
            for agent_name, agent_data in self.agents.items():
                serializable_agents[agent_name] = {
                    "name": agent_data["name"],
                    "spec": agent_data["spec"],
                    "conversation_history": agent_data["shared_store"][
                        "conversation_history"
                    ],
                    "status": agent_data["status"],
                    "created_at": agent_data["created_at"],
                }

            with open(self.agents_file, "w") as f:
                json.dump(serializable_agents, f, indent=2, default=str)

        except Exception as e:
            self.logger.error(f"Failed to save agents state: {e}")

    def _load_agents_state(self):
        """Load agents state from disk (PocketFlow agents need to be recreated)"""
        try:
            if self.agents_file.exists():
                with open(self.agents_file, "r") as f:
                    saved_agents = json.load(f)

                # Recreate PocketFlow agents from saved state
                for agent_name, saved_data in saved_agents.items():
                    self.logger.info(f"Restoring agent {agent_name} from saved state")
                    # Would need to recreate flows here if implementing state persistence
                    # For now, agents need to be recreated from workflow specs

        except Exception as e:
            self.logger.error(f"Failed to load agents state: {e}")


async def start_daemon():
    """Start the Ago daemon"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(Path.home() / ".ago" / "daemon.log"),
            logging.StreamHandler(),
        ],
    )

    daemon = AgoDaemon()

    try:
        await daemon.start()
    except KeyboardInterrupt:
        await daemon.shutdown()
    except Exception as e:
        console.print(f"❌ Daemon failed: {e}", style="red")
        await daemon.shutdown()


if __name__ == "__main__":
    asyncio.run(start_daemon())
