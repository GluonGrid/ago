#!/usr/bin/env python3
"""
AgentNode: Execute AI agents with template variable support
"""
import asyncio
from typing import Dict, Optional

from .base_ago_node import AgoNode


class AgentNode(AgoNode):
    """Execute agent with input from previous step"""

    def __init__(
        self,
        name: str,
        template: str,
        prompt_template: str,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
    ):
        super().__init__(name, input_mapping, output_mapping)
        self.template = template
        self.prompt_template = prompt_template

    async def prep_async(self, shared):
        """Get input and format prompt with template resolution"""
        # Use parent's prep_async to get inputs
        prep_res = await super().prep_async(shared)

        # Resolve template variables in prompt using parent's resolve_template
        prompt = self.resolve_template(self.prompt_template, shared)

        prep_res["prompt"] = prompt
        return prep_res

    async def exec_async(self, prep_res):
        """Run agent"""
        from ..daemon_client import DaemonClient

        daemon = DaemonClient()
        instance = f"linear-{self.name}"

        print(f"[AgentNode:{self.name}] Template: {self.template}")
        print(f"[AgentNode:{self.name}] Prompt: {prep_res['prompt']}")

        try:
            # Start agent
            print(f"[AgentNode:{self.name}] Starting agent...")
            result = await daemon.run_single_agent(self.template, instance)
            print(f"[AgentNode:{self.name}] Agent start result: {result}")

            if result.get("status") == "error":
                return {"error": result.get("message"), "success": False}

            # Get actual agent name from result (may have UUID appended)
            actual_agent_name = result.get("agent", {}).get("name", instance)
            print(f"[AgentNode:{self.name}] Actual agent name: {actual_agent_name}")

            # Wait briefly for agent socket to initialize
            await asyncio.sleep(0.5)

            # Send message and get response (just like ago chat)
            print(f"[AgentNode:{self.name}] Sending message...")
            msg_result = await daemon.chat_message(actual_agent_name, prep_res["prompt"])
            print(f"[AgentNode:{self.name}] Message result: {msg_result}")

            if msg_result.get("status") == "error":
                return {"error": msg_result.get("message"), "success": False}

            # Extract response directly from chat_message result
            response = msg_result.get("response", "")
            print(f"[AgentNode:{self.name}] Response: {response}")

            # Stop agent
            await daemon.stop_agent(actual_agent_name)

            return {
                "output": {"content": response, "input": prep_res["input"]},
                "success": True,
            }

        except Exception as e:
            print(f"[AgentNode:{self.name}] Error: {e}")
            import traceback

            print(f"[AgentNode:{self.name}] Traceback: {traceback.format_exc()}")
            return {"error": str(e), "success": False}
