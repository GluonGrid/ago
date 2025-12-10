#!/usr/bin/env python3
"""
InteractiveNode: Collect user input via terminal during workflow execution
"""
import json
from typing import Dict, List, Optional

from .base_ago_node import AgoNode


class InteractiveNode(AgoNode):
    """Get user input interactively via terminal"""

    def __init__(
        self,
        name: str,
        prompt: str,
        fields: Optional[List[Dict]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
    ):
        # InteractiveNode doesn't need input_mapping (it gets input from user)
        super().__init__(name, input_mapping=None, output_mapping=output_mapping)
        self.prompt = prompt
        self.fields = fields or [{"name": "input", "label": "Enter value"}]

    async def exec_async(self, prep_res):
        """Prompt user for input via terminal"""
        print(f"\n📝 {self.name}")
        print(f"{self.prompt}\n")

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
