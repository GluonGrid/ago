#!/usr/bin/env python3
"""
Utility functions for node field resolution and data mapping.
"""
from typing import Any, Dict


def resolve_field_path(path: str, shared: Dict[str, Any]) -> Any:
    """
    Resolve a field path from shared state.

    Supports:
    - "node.field" → shared["node"]["field"]
    - "node.nested.field" → shared["node"]["nested"]["field"]
    - "node" → shared["node"] (entire output)
    - "field" → shared["field"] (direct lookup)

    Args:
        path: Field path string (e.g., "sentiment.content")
        shared: Shared state dictionary

    Returns:
        Resolved value or None if path not found

    Examples:
        >>> shared = {"sentiment": {"content": "positive"}}
        >>> resolve_field_path("sentiment.content", shared)
        "positive"
        >>> resolve_field_path("sentiment", shared)
        {"content": "positive"}
    """
    if not path:
        return None

    # No dots - direct lookup
    if '.' not in path:
        return shared.get(path)

    # Dotted path - navigate nested structure
    parts = path.split('.')
    value = shared

    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
            if value is None:
                return None
        else:
            return None

    return value


def resolve_inputs(input_mapping: Dict[str, str], shared: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve all input mappings using field paths.

    Args:
        input_mapping: Dict mapping target field names to source paths
        shared: Shared state dictionary

    Returns:
        Dict with resolved values

    Example:
        >>> input_mapping = {"sentiment": "analyze.content", "user": "input.username"}
        >>> shared = {"analyze": {"content": "positive"}, "input": {"username": "alice"}}
        >>> resolve_inputs(input_mapping, shared)
        {"sentiment": "positive", "user": "alice"}
    """
    if not input_mapping:
        return {}

    resolved = {}
    for target_field, source_path in input_mapping.items():
        value = resolve_field_path(source_path, shared)
        resolved[target_field] = value

    return resolved


def store_node_output(
    node_name: str,
    output: Any,
    output_mapping: Dict[str, str],
    shared: Dict[str, Any]
) -> None:
    """
    Store node output in shared state.

    1. Stores entire output under node name: shared[node_name] = output
    2. Optionally creates shortcuts via output_mapping

    Args:
        node_name: Name of the node
        output: Output data to store
        output_mapping: Optional mapping for shortcuts (e.g., {"analysis": "content"})
        shared: Shared state dictionary to update

    Example:
        >>> shared = {}
        >>> output = {"content": "result", "score": 0.9}
        >>> store_node_output("analyze", output, {"result": "content"}, shared)
        >>> shared["analyze"]
        {"content": "result", "score": 0.9}
        >>> shared["result"]  # Shortcut
        "result"
    """
    # Store entire output under node name
    shared[node_name] = output

    # Create optional shortcuts
    if output_mapping and isinstance(output, dict):
        for shortcut_key, output_key in output_mapping.items():
            shared[shortcut_key] = output.get(output_key)
