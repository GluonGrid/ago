#!/usr/bin/env python3
"""
Workflow Engine using PocketFlow
Supports linear, parallel, conditional, and mixed workflows.
"""
from typing import Any, Dict

from pocketflow import AsyncFlow

from .flow_parser import detect_start_node, parse_flow_syntax
from .nodes import AgentNode, InteractiveNode, MergeNode, ScriptNode


async def run_workflow(spec: Dict[str, Any]) -> bool:
    """
    Execute workflow from spec.

    Supports:
    - Linear workflows (nodes in order or with flow key)
    - Parallel workflows (fan-out/fan-in patterns)
    - Conditional workflows (branching with named edges)
    - Mixed workflows (combination of above)

    Args:
        spec: Workflow specification

    Returns:
        bool: True if workflow completed successfully, False otherwise
    """
    workflow_spec = spec.get("spec", {})

    # Support both "steps" (legacy) and "nodes" (new)
    node_list = workflow_spec.get("nodes") or workflow_spec.get("steps", [])

    # Build node instances
    nodes = {}  # Dict for flow parser

    for node_def in node_list:
        node_name = node_def["name"]
        node_type = node_def["type"]

        # Get optional field mappings
        input_mapping = node_def.get("inputs", {})
        output_mapping = node_def.get("outputs", {})

        # Create node instance
        if node_type == "script":
            node = ScriptNode(
                node_name,
                node_def["script"],
                input_mapping=input_mapping,
                output_mapping=output_mapping,
            )
        elif node_type == "agent":
            node = AgentNode(
                node_name,
                node_def["template"],
                node_def.get("prompt", ""),
                input_mapping=input_mapping,
                output_mapping=output_mapping,
            )
        elif node_type == "interactive":
            node = InteractiveNode(
                node_name,
                node_def.get("prompt", "Enter input:"),
                fields=node_def.get("fields", None),
                output_mapping=output_mapping,
            )
        elif node_type == "merge":
            node = MergeNode(
                node_name,
                input_mapping=input_mapping,
                output_mapping=output_mapping,
                merge_strategy=node_def.get("strategy", "dict"),
            )
        else:
            raise ValueError(f"Unknown node type: {node_type}")

        nodes[node_name] = node

    # Determine flow type and create connections
    if "flow" in workflow_spec:
        # Parse flow syntax for parallel/conditional workflows
        flow_str = workflow_spec["flow"]
        parse_flow_syntax(nodes, flow_str)

        # Detect start node from flow
        start_node_name = detect_start_node(nodes, flow_str)
        start_node = nodes[start_node_name]

    else:
        # Legacy linear: connect nodes in order
        node_list_ordered = list(nodes.values())
        for i in range(len(node_list_ordered) - 1):
            node_list_ordered[i] >> node_list_ordered[i + 1]

        start_node = node_list_ordered[0]

    # Create and execute flow
    flow = AsyncFlow(start=start_node)

    shared = {}
    result = await flow.run_async(shared)

    return shared.get("success", False)
