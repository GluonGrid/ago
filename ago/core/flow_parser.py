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

    # First pass: parse all edges and track connections
    for line in lines:
        # Handle conditional edges: node -"action">> target
        if '-"' in line or "-'" in line:
            _parse_conditional_edge(line, nodes)
        # Handle regular edges: node >> target
        elif '>>' in line:
            _parse_regular_edge(line, nodes)

    # Second pass: detect parallel nodes with successors and convert to ParallelFlowNode
    _convert_parallel_to_flow_nodes(nodes)


def _parse_regular_edge(line: str, nodes: Dict) -> None:
    """
    Parse regular edge: a >> b, a >> [b,c], [a,b] >> c, a >> b >> c

    Args:
        line: Flow line (e.g., "a >> b >> c")
        nodes: Dict of node instances
    """
    from .nodes import ParallelNode

    parts = [p.strip() for p in line.split('>>')]

    for i in range(len(parts) - 1):
        source = parts[i]
        target = parts[i + 1]

        # Parse source: "node" or "[node1, node2]"
        sources = _parse_node_list(source)
        # Parse target: "node" or "[node1, node2]"
        targets = _parse_node_list(target)

        # Fan-out: single source >> multiple targets → create ParallelNode
        if len(sources) == 1 and len(targets) > 1:
            src = sources[0]
            if src not in nodes:
                raise ValueError(f"Unknown node in flow: '{src}'")

            # Mark these targets as being part of a parallel group
            # This will be used later to detect if they need sub-flows
            parallel_node_name = f"_parallel_{src}_to_{'_'.join(targets)}"
            target_nodes = []
            for tgt in targets:
                if tgt not in nodes:
                    raise ValueError(f"Unknown node in flow: '{tgt}'")
                target_nodes.append(nodes[tgt])
                # Mark node as part of parallel execution
                if not hasattr(nodes[tgt], '_parallel_group'):
                    nodes[tgt]._parallel_group = parallel_node_name

            parallel_node = ParallelNode(parallel_node_name, target_nodes)
            nodes[parallel_node_name] = parallel_node

            # Connect: source >> parallel_node
            nodes[src] >> parallel_node

        # Fan-in: multiple sources >> single target → each connects separately
        elif len(sources) > 1 and len(targets) == 1:
            tgt = targets[0]
            if tgt not in nodes:
                raise ValueError(f"Unknown node in flow: '{tgt}'")
            for src in sources:
                if src not in nodes:
                    raise ValueError(f"Unknown node in flow: '{src}'")
                nodes[src] >> nodes[tgt]

        # Linear: single source >> single target
        else:
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


def _convert_parallel_to_flow_nodes(nodes: Dict) -> None:
    """
    Convert ParallelNode to ParallelFlowNode when child nodes have successors.

    This enables forked flows where each parallel branch can continue
    through its own successor chain independently.

    Args:
        nodes: Dict of node instances
    """
    from .nodes import ParallelNode, ParallelFlowNode

    # Find all ParallelNode instances
    parallel_nodes_to_convert = []

    for node_name, node in list(nodes.items()):
        if isinstance(node, ParallelNode):
            # Check if any of the parallel child nodes have successors
            has_successors = any(
                child.successors for child in node.parallel_nodes
            )

            if has_successors:
                parallel_nodes_to_convert.append((node_name, node))

    # Convert ParallelNode to ParallelFlowNode
    for node_name, parallel_node in parallel_nodes_to_convert:
        print(
            f"[FlowParser] Converting {node_name} to ParallelFlowNode (children have successors)"
        )

        # Create ParallelFlowNode with the same child nodes
        flow_node = ParallelFlowNode(
            name=parallel_node.name,
            start_nodes=parallel_node.parallel_nodes,
        )

        # Replace in nodes dict
        nodes[node_name] = flow_node

        # Transfer any incoming connections from ParallelNode to ParallelFlowNode
        # Find nodes that point to the old ParallelNode and redirect them
        for other_name, other_node in nodes.items():
            if other_node is parallel_node:
                continue

            # Check if other_node has parallel_node as a successor
            for action, successor in list(other_node.successors.items()):
                if successor is parallel_node:
                    # Replace the successor
                    other_node.successors[action] = flow_node


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
