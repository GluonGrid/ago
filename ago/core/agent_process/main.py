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
        """Initialize the PocketFlow agent with streaming capability"""
        try:
            # Import both regular and streaming flow creators
            from ...agents.agent_react_flow import create_agent_flow
            from ...agents.streaming_react_wrapper import StreamingFlow
            
            # Create the original PocketFlow ReAct agent
            original_flow = create_agent_flow(
                self.agent_name, self.agent_spec, self.agent_template, self.agent_tools
            )
            
            # Wrap it with streaming capability
            self.agent_flow = StreamingFlow(original_flow)
            
            self.logger.info(f"🔄 Agent {self.agent_name} initialized with streaming capability")

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

                # Store writer for streaming use
                self._current_writer = writer
                
                response = await self._process_ipc_command(message)
                
                # Clear writer after processing
                self._current_writer = None

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
            # Check if this is a streaming request
            is_streaming = message.get("streaming", False)
            if is_streaming:
                # Handle streaming chat message
                await self._process_chat_message_streaming(args.get("message", ""))
                # Return completion status (after streaming)
                return {"status": "completed"}
            else:
                # Handle regular chat message
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
        """Process chat message using streaming ReAct flow"""
        try:
            self.logger.info(f"Processing chat message with streaming: {user_message}")

            # Update shared store with user message
            self.shared_store["user_message"] = user_message
            
            # Check if we have streaming capability
            if hasattr(self.agent_flow, 'run_with_streaming'):
                # Use streaming version
                async for step in self.agent_flow.run_with_streaming(self.shared_store):
                    # Send each step immediately via IPC to daemon
                    await self._send_stream_update(step)
                    
                    # Log streaming step for debugging  
                    content = step.get('content', '')
                    if isinstance(content, dict):
                        content_str = str(content)[:100] + "..." if len(str(content)) > 100 else str(content)
                    else:
                        content_str = str(content)[:100] + "..." if len(str(content)) > 100 else str(content)
                    self.logger.info(f"🔄 STREAM [{step['type']}]: {content_str}")
                    
                    if step.get('is_final', False):
                        break
                
                # Get final assistant response
                assistant_response = self.shared_store.get("assistant_response", "")
                
                return {
                    "status": "success",
                    "response": assistant_response,
                    "agent": self.agent_name,
                    "streaming": True
                }
            else:
                # Fallback to regular flow execution
                await self.agent_flow.run_async(self.shared_store)
                assistant_response = self.shared_store.get("assistant_response", "")
                
                return {
                    "status": "success", 
                    "response": assistant_response,
                    "agent": self.agent_name,
                    "streaming": False
                }

        except Exception as e:
            self.logger.error(f"Error processing chat message: {e}")
            # Send error as stream update if possible
            try:
                await self._send_stream_update({
                    "type": "error",
                    "content": str(e),
                    "is_final": True
                })
            except:
                pass  # Ignore streaming errors during error handling
            
            return {"status": "error", "message": str(e)}

    async def _process_chat_message_streaming(self, user_message: str):
        """Process chat message with streaming - sends each step via IPC"""
        try:
            self.logger.info(f"Processing streaming chat message: {user_message}")

            # Update shared store with user message
            self.shared_store["user_message"] = user_message
            
            # Check if we have streaming capability
            if hasattr(self.agent_flow, 'run_with_streaming'):
                # Stream each ReAct step back to daemon via IPC
                async for step in self.agent_flow.run_with_streaming(self.shared_store):
                    # Send step back via current IPC connection
                    await self._send_step_via_ipc(step)
                    
                    # Log for debugging
                    content = step.get('content', '')
                    if isinstance(content, dict):
                        content_str = str(content)[:100] + "..." if len(str(content)) > 100 else str(content)
                    else:
                        content_str = str(content)[:100] + "..." if len(str(content)) > 100 else str(content)
                    self.logger.info(f"🔄 STREAMED [{step['type']}]: {content_str}")
                    
                    if step.get('is_final', False):
                        break
            else:
                # Fallback to regular flow execution
                await self.agent_flow.run_async(self.shared_store)
                # Send final response as single step
                assistant_response = self.shared_store.get("assistant_response", "")
                await self._send_step_via_ipc({
                    "type": "final",
                    "content": assistant_response,
                    "is_final": True,
                    "agent": self.agent_name
                })

        except Exception as e:
            self.logger.error(f"Error processing streaming chat message: {e}")
            # Send error as final step
            await self._send_step_via_ipc({
                "type": "error",
                "content": str(e),
                "is_final": True
            })

    async def _send_step_via_ipc(self, step_data: Dict[str, Any]):
        """Send streaming step back to daemon via current IPC connection"""
        try:
            # Send the step data as a response back through the current IPC connection
            # The daemon's streaming handler will receive this
            
            # Add metadata
            response = {
                "status": "streaming",
                "agent": self.agent_name,
                "timestamp": datetime.now().isoformat(),
                **step_data
            }
            
            # Send via IPC (this will be received by daemon's streaming loop)
            response_packed = msgpack.packb(response)
            length_prefix = len(response_packed).to_bytes(4, "big")
            
            # We need access to the current writer from the IPC handler
            # Store it in self for streaming use
            if hasattr(self, '_current_writer') and self._current_writer:
                self._current_writer.write(length_prefix + response_packed)
                await self._current_writer.drain()
            else:
                self.logger.warning("No IPC writer available for streaming")
                
        except Exception as e:
            self.logger.error(f"Failed to send streaming step via IPC: {e}")

    async def _send_stream_update(self, step_data: Dict[str, Any]):
        """Send streaming update back to daemon via IPC"""
        step_type = step_data.get("type", "unknown")
        content = step_data.get("content", "")
        is_final = step_data.get("is_final", False)
        
        # Format content for logging
        if isinstance(content, dict):
            content_str = str(content)
        else:
            content_str = str(content)
        
        self.logger.info(f"📡 STREAMING [{step_type}]: {content_str[:200]}{'...' if len(content_str) > 200 else ''}")
        
        if is_final:
            self.logger.info("🏁 STREAMING: Final step completed")
        
        # Send streaming update to daemon via IPC
        try:
            await self._send_ipc_to_daemon("stream_update", step_data)
            self.logger.debug(f"✅ Sent stream update to daemon: {step_type}")
        except Exception as e:
            self.logger.error(f"❌ Failed to send stream update to daemon: {e}")
            # Don't fail the entire process if streaming fails
    
    async def _send_ipc_to_daemon(self, command: str, data: Dict[str, Any]):
        """Send IPC message back to daemon (reverse direction)"""
        try:
            # Connect to daemon's IPC socket 
            daemon_socket_path = Path.home() / ".ago" / "daemon_stream.sock"
            
            if not daemon_socket_path.exists():
                # Daemon doesn't have streaming socket yet
                self.logger.debug("Daemon streaming socket not available")
                return
            
            # Create message
            message = {
                "command": command,
                "agent_name": self.agent_name,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            
            # Connect and send
            reader, writer = await asyncio.open_unix_connection(str(daemon_socket_path))
            
            # Send message (using same msgpack protocol as daemon)
            import msgpack
            message_packed = msgpack.packb(message)
            length_prefix = len(message_packed).to_bytes(4, "big")
            writer.write(length_prefix + message_packed)
            await writer.drain()
            
            # Close connection
            writer.close()
            await writer.wait_closed()
            
        except Exception as e:
            self.logger.debug(f"IPC to daemon failed: {e}")
            # Don't raise - streaming is best-effort

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
