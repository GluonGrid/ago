#!/usr/bin/env python3
"""
Base AgoNode class with dotted notation support.

Custom nodes can inherit from this to get automatic field mapping,
dotted notation resolution, and template variable support.
"""
import json
import re
from typing import Any, Dict, Optional

from pocketflow import AsyncNode

from .utils import resolve_field_path, resolve_inputs, store_node_output


class AgoNode(AsyncNode):
    """
    Base class for Ago workflow nodes with dotted notation support.

    Features:
    - Automatic input/output field mapping
    - Dotted notation: node.field, node.nested.field
    - Template variable resolution: {{node.field}}
    - Backwards compatible with legacy syntax

    To create a custom node:
    1. Inherit from AgoNode
    2. Implement async def exec_async(self, prep_res)
    3. Optionally override prep_async() or post_async()

    Example:
        class MyCustomNode(AgoNode):
            async def exec_async(self, prep_res):
                input_data = prep_res.get("input")
                # Your logic here
                result = process(input_data)
                return {"output": result, "success": True}
    """

    def __init__(
        self,
        name: str,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        """
        Initialize AgoNode.

        Args:
            name: Node name (used for dotted notation)
            input_mapping: Map input fields from shared state
                          e.g., {"data": "previous_node.content"}
            output_mapping: Create shortcuts for output fields
                           e.g., {"result": "content"} creates shared["result"]
            **kwargs: Additional node-specific parameters
        """
        super().__init__()
        self.name = name
        self.input_mapping = input_mapping or {}
        self.output_mapping = output_mapping or {}

    async def prep_async(self, shared):
        """
        Prepare inputs with dotted notation support.

        Override this to add custom prep logic.
        Call super().prep_async(shared) first to get mapped inputs.

        Returns:
            Dict with "input" key containing resolved input data
        """
        if self.input_mapping:
            # Resolve inputs using dotted notation
            input_data = resolve_inputs(self.input_mapping, shared)
        else:
            # No mapping - empty dict
            input_data = {}

        return {"input": input_data, "shared": shared}

    async def exec_async(self, prep_res):
        """
        Execute node logic - MUST be implemented by subclasses.

        Args:
            prep_res: Result from prep_async(), contains:
                     - "input": Mapped input data
                     - "shared": Full shared state (for advanced use)

        Returns:
            Dict with "output" and "success" keys:
            {"output": result_data, "success": True}
        """
        raise NotImplementedError("Subclasses must implement exec_async()")

    async def post_async(self, shared, prep_res, exec_res):
        """
        Store outputs with dotted notation support.

        Override this to add custom post logic.
        Call super().post_async() at the end to store outputs.

        Returns:
            str: Edge name for flow control (default: "default")
        """
        output = exec_res.get("output")

        # Store output under node name: shared[node_name] = output
        # Also create optional shortcuts via output_mapping
        store_node_output(self.name, output, self.output_mapping, shared)

        shared["success"] = exec_res.get("success", True)
        return "default"  # PocketFlow uses "default" for >> edges

    def resolve_template(self, template: str, shared: Dict[str, Any]) -> str:
        """
        Resolve template variables with dotted notation.

        Supports:
        - {{node.field}} - Dotted notation
        - {{field}} - Direct field lookup

        Args:
            template: Template string with {{...}} variables
            shared: Shared state

        Returns:
            Resolved template string

        Example:
            >>> template = "User {{input.username}} analyzed {{sentiment.content}}"
            >>> self.resolve_template(template, shared)
            "User alice analyzed positive"
        """
        # Find all {{...}} patterns
        pattern = r"\{\{([^}]+)\}\}"
        matches = re.findall(pattern, template)

        for match in matches:
            match = match.strip()

            # Dotted notation: {{node.field}} or {{field}}
            resolved = resolve_field_path(match, shared)
            value = str(resolved) if resolved is not None else ""

            template = template.replace(f"{{{{{match}}}}}", value)

        return template
