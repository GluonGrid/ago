#!/usr/bin/env python3
"""
MergeNode: Combine outputs from multiple parallel nodes
"""
from typing import Any, Dict, Optional

from .base_ago_node import AgoNode


class MergeNode(AgoNode):
    """Merge outputs from multiple upstream nodes"""

    def __init__(
        self,
        name: str,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        merge_strategy: str = "dict",
    ):
        """
        Initialize MergeNode.

        Args:
            name: Node name
            input_mapping: Map fields from upstream nodes
                          e.g., {"sentiment": "sentiment_node.content",
                                 "keywords": "keywords_node.content"}
            output_mapping: Output field shortcuts
            merge_strategy: How to merge inputs:
                - "dict" (default): Create dict with all inputs
                - "list": Create list of input values
                - "concat": Concatenate string values
        """
        super().__init__(name, input_mapping, output_mapping)
        self.merge_strategy = merge_strategy

    async def prep_async(self, shared):
        """Collect inputs from upstream nodes"""
        if self.input_mapping:
            # Use parent's resolve_inputs
            return await super().prep_async(shared)
        else:
            # No mapping - collect all non-internal fields
            input_data = {
                key: value
                for key, value in shared.items()
                if not key.startswith("_") and key != "success"
            }
            return {"input": input_data, "shared": shared}

    async def exec_async(self, prep_res):
        """Merge inputs based on strategy"""
        input_data = prep_res.get("input", {})

        print(f"[MergeNode:{self.name}] Merging {len(input_data)} inputs")
        print(f"[MergeNode:{self.name}] Strategy: {self.merge_strategy}")

        if self.merge_strategy == "dict":
            # Return as dictionary (default)
            merged = input_data

        elif self.merge_strategy == "list":
            # Return as list of values
            merged = list(input_data.values())

        elif self.merge_strategy == "concat":
            # Concatenate string values
            parts = []
            for key, value in input_data.items():
                if isinstance(value, dict):
                    # Extract text-like fields from dicts
                    text_fields = ["content", "result", "text", "output"]
                    for field in text_fields:
                        if field in value:
                            parts.append(str(value[field]))
                            break
                    else:
                        parts.append(str(value))
                else:
                    parts.append(str(value))
            merged = "\n\n".join(parts)

        else:
            raise ValueError(f"Unknown merge strategy: {self.merge_strategy}")

        print(f"[MergeNode:{self.name}] Merged result type: {type(merged)}")
        return {"output": merged, "success": True}
