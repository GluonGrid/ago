#!/usr/bin/env python3
"""
Flow Parser: Parse YAML flow syntax into PocketFlow graphs

Supports:
- Linear: a >> b >> c
- Fan-out: a >> [b, c, d]
- Fan-in: [b, c, d] >> e
- Conditional: a -"action">> b
- Mixed: any combination of the above
"""
import re
from typing import Dict, List


def parse_flow_syntax(nodes: Dict, flow_str: str) -> None:
    """
    Parse flow syntax and create PocketFlow connections.

    Modifies nodes in-place by creating >> connections.

    Supported patterns:
    - "a >> b"           → nodes["a"] >> nodes["b"]
    - "a >> [b, c]"      → nodes["a"] >> nodes["b"], nodes["a"] >> nodes["c"]
    - "[b, c] >> d"      → nodes["b"] >> nodes["d"], nodes["c"] >> nodes["d"]
    - "a -"high">> b"    → nodes["a"] - "high" >> nodes["b"]
    - "a >> b >> c"      → nodes["a"] >> nodes["b"] >> nodes["c"]

    Args:
        nodes: Dict of node_name → node_instance
        flow_str: Multi-line flow definition string

    Example:
        >>> flow = '''
        ... input >> validate
        ... validate >> [process_a, process_b]
        ... [process_a, process_b] >> merge
        ... '''
        >>> parse_flow_syntax(nodes, flow)
    """
    # Split into lines and remove comments/empty lines
    lines = [
        line.strip()
        for line in flow_str.strip().split('\n')
        if line.strip() and not line.strip().startswith('#')
    ]

    for line in lines:
        # Handle conditional edges: node -"action">> target
        if '-"' in line or "-'" in line:
            _parse_conditional_edge(line, nodes)
        # Handle regular edges: node >> target
        elif '>>' in line:
            _parse_regular_edge(line, nodes)


def _parse_regular_edge(line: str, nodes: Dict) -> None:
    """
    Parse regular edge: a >> b, a >> [b,c], [a,b] >> c, a >> b >> c

    Args:
        line: Flow line (e.g., "a >> b >> c")
        nodes: Dict of node instances
    """
    parts = [p.strip() for p in line.split('>>')]

    for i in range(len(parts) - 1):
        source = parts[i]
        target = parts[i + 1]

        # Parse source: "node" or "[node1, node2]"
        sources = _parse_node_list(source)
        # Parse target: "node" or "[node1, node2]"
        targets = _parse_node_list(target)

        # Connect: each source >> each target
        for src in sources:
            if src not in nodes:
                raise ValueError(f"Unknown node in flow: '{src}'")
            for tgt in targets:
                if tgt not in nodes:
                    raise ValueError(f"Unknown node in flow: '{tgt}'")
                nodes[src] >> nodes[tgt]


def _parse_conditional_edge(line: str, nodes: Dict) -> None:
    """
    Parse conditional edge: a -"high">> b

    Args:
        line: Flow line with conditional (e.g., 'check -"valid">> process')
        nodes: Dict of node instances
    """
    # Match: node -"action">> target or node -'action'>> target
    match = re.match(r'(\w+)\s*-["\'](\w+)["\']\s*>>\s*(.+)', line)
    if not match:
        raise ValueError(f"Invalid conditional syntax: {line}")

    source = match.group(1)
    action = match.group(2)
    target = match.group(3).strip()

    if source not in nodes:
        raise ValueError(f"Unknown node in flow: '{source}'")

    # Parse target(s)
    targets = _parse_node_list(target)

    for tgt in targets:
        if tgt not in nodes:
            raise ValueError(f"Unknown node in flow: '{tgt}'")
        nodes[source] - action >> nodes[tgt]


def _parse_node_list(s: str) -> List[str]:
    """
    Parse node list: 'node' → ['node'], '[a, b, c]' → ['a', 'b', 'c']

    Args:
        s: String representing node(s)

    Returns:
        List of node names

    Examples:
        >>> _parse_node_list("node1")
        ['node1']
        >>> _parse_node_list("[node1, node2, node3]")
        ['node1', 'node2', 'node3']
    """
    s = s.strip()
    if s.startswith('[') and s.endswith(']'):
        # Array of nodes: [a, b, c]
        return [n.strip() for n in s[1:-1].split(',')]
    else:
        # Single node
        return [s]


def detect_start_node(nodes: Dict, flow_str: str) -> str:
    """
    Detect the starting node from flow definition.

    The start node is the first node that appears on the left side
    of a >> but never on the right side in the first line.

    Args:
        nodes: Dict of node instances
        flow_str: Flow definition string

    Returns:
        Name of the start node

    Raises:
        ValueError: If start node cannot be determined
    """
    lines = [
        line.strip()
        for line in flow_str.strip().split('\n')
        if line.strip() and not line.strip().startswith('#')
    ]

    if not lines:
        raise ValueError("Empty flow definition")

    # Parse first line to get start node
    first_line = lines[0]

    # Handle conditional: "node -"action">> ..."
    if '-"' in first_line or "-'" in first_line:
        match = re.match(r'(\w+)\s*-', first_line)
        if match:
            return match.group(1)

    # Handle regular: "node >> ..." or "[node1, node2] >> ..."
    if '>>' in first_line:
        source = first_line.split('>>')[0].strip()
        sources = _parse_node_list(source)
        # Return first source node
        return sources[0]

    raise ValueError(f"Cannot determine start node from: {first_line}")
