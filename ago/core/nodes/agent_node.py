#!/usr/bin/env python3
"""
AgentNode: Execute AI agents with template variable support
"""
import asyncio
import json
import re
from typing import Dict

from pocketflow import AsyncNode

from .utils import resolve_field_path, resolve_inputs, store_node_output


class AgentNode(AsyncNode):
    """Execute agent with input from previous step"""

    def __init__(
        self,
        name: str,
        template: str,
        prompt_template: str,
        input_mapping: Dict = None,
        output_mapping: Dict = None,
    ):
        super().__init__()
        self.name = name
        self.template = template
        self.prompt_template = prompt_template
        self.input_mapping = input_mapping or {}
        self.output_mapping = output_mapping or {}
        self.daemon = None

    async def prep_async(self, shared):
        """Get input and format prompt with dotted notation"""
        if self.input_mapping:
            # Use dotted notation: sentiment.content, node.field, etc.
            input_data = resolve_inputs(self.input_mapping, shared)
        else:
            # No mapping - empty dict
            input_data = {}

        # Replace template variables in prompt using dotted notation
        # Support: {{node.field}}, {{field}}
        prompt = self.prompt_template

        # Find all {{...}} patterns
        pattern = r"\{\{([^}]+)\}\}"
        matches = re.findall(pattern, prompt)

        for match in matches:
            match = match.strip()

            # Dotted notation: {{node.field}} or {{field}}
            resolved = resolve_field_path(match, shared)
            value = str(resolved) if resolved is not None else ""

            prompt = prompt.replace(f"{{{{{match}}}}}", value)

        return {"prompt": prompt, "input": input_data}

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

    async def post_async(self, shared, prep_res, exec_res):
        """Store output with dotted notation support"""
        output = exec_res.get("output")

        # Store output under node name: shared[node_name] = output
        # Also create optional shortcuts via output_mapping
        store_node_output(self.name, output, self.output_mapping, shared)

        shared["success"] = exec_res.get("success", True)
        return "default"  # PocketFlow uses "default" for >> edges
