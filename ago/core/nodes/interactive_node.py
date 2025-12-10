#!/usr/bin/env python3
"""
InteractiveNode: Collect user input via terminal during workflow execution
"""
import json
from typing import Dict

from pocketflow import AsyncNode

from .utils import store_node_output


class InteractiveNode(AsyncNode):
    """Get user input interactively via terminal"""

    def __init__(
        self,
        name: str,
        prompt: str,
        fields: list = None,
        output_mapping: Dict = None,
    ):
        super().__init__()
        self.name = name
        self.prompt = prompt
        self.fields = fields or [{"name": "input", "label": "Enter value"}]
        self.output_mapping = output_mapping or {}

    async def prep_async(self, shared):
        """Show previous output if available"""
        return {"previous_output": shared.get("output")}

    async def exec_async(self, prep_res):
        """Prompt user for input via terminal"""
        print(f"\n📝 {self.name}")
        print(f"{self.prompt}\n")

        # Show previous output if available
        if prep_res.get("previous_output"):
            print("Previous step output:")
            print(json.dumps(prep_res["previous_output"], indent=2))
            print()

        # Collect input for each field
        user_data = {}
        for field in self.fields:
            field_name = field.get("name", "input")
            field_label = field.get("label", field_name)
            field_default = field.get("default", "")

            prompt_text = f"{field_label}"
            if field_default:
                prompt_text += f" [{field_default}]"
            prompt_text += ": "

            value = input(prompt_text).strip()
            if not value and field_default:
                value = field_default

            user_data[field_name] = value

        print()
        return {"output": user_data, "success": True}

    async def post_async(self, shared, prep_res, exec_res):
        """Store output with dotted notation support"""
        output = exec_res.get("output")

        # Store output under node name: shared[node_name] = output
        # Also create optional shortcuts via output_mapping
        store_node_output(self.name, output, self.output_mapping, shared)

        shared["success"] = exec_res.get("success", True)
        return "default"
