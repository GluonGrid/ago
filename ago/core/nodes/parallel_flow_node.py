#!/usr/bin/env python3
"""
ParallelFlowNode: Execute multiple sub-flows in parallel with streaming.

Each sub-flow runs independently and continues through its successors
without waiting for other branches to complete.
"""

import asyncio
from typing import Any, List, Dict
from pocketflow import AsyncFlow, AsyncNode


class ParallelFlowNode(AsyncNode):
    """
    Executes multiple sub-flows in parallel with independent continuation.

    Unlike ParallelNode which just runs nodes in parallel, ParallelFlowNode
    creates independent AsyncFlow instances for each branch, allowing each
    branch to follow its own successor chain.

    Key behaviors:
    - Each branch starts at its designated start node
    - Each branch follows its successors independently
    - Branches complete at different times based on their work
    - Side effects (file creation, API calls) happen as each branch executes
    - The overall node completes when all branches finish

    Example:
        start >> [flow_a_start, flow_b_start]
        flow_a_start >> flow_a_done    # Flow A completes in 10s
        flow_b_start >> flow_b_done    # Flow B completes in 30s

        Creates ParallelFlowNode that:
        1. Spawns AsyncFlow(start=flow_a_start) and AsyncFlow(start=flow_b_start)
        2. Both flows run concurrently
        3. Flow A completes and executes flow_a_done at ~10s
        4. Flow B completes and executes flow_b_done at ~30s
        5. ParallelFlowNode returns after all flows complete
    """

    def __init__(
        self, name: str, start_nodes: List[Any], shared_context: Dict = None
    ):
        """
        Initialize ParallelFlowNode.

        Args:
            name: Node name
            start_nodes: List of nodes that start each parallel flow
            shared_context: Shared context dict for all flows
        """
        super().__init__()
        self.name = name
        self.start_nodes = start_nodes
        self.shared_context = shared_context or {}

    async def prep_async(self, shared):
        """Prepare - just pass through shared context."""
        pass

    async def exec_async(self, prep_res):
        """Not used - we override _run_async directly."""
        pass

    async def post_async(self, shared, prep_res, exec_res):
        """Return default action to continue to next node."""
        return "default"

    async def _run_async(self, shared):
        """
        Execute all flows concurrently using asyncio.gather.

        Simple and direct: create tasks, run them in parallel, wait for all to finish.
        """
        print(
            f"[ParallelFlowNode:{self.name}] Starting {len(self.start_nodes)} parallel flows"
        )

        # Create a task for each flow - they start running immediately
        async def run_flow(start_node):
            print(f"[ParallelFlowNode:{self.name}] Starting flow from {start_node.name}")
            flow = AsyncFlow(start=start_node)
            result = await flow.run_async(shared)
            print(f"[ParallelFlowNode:{self.name}] Completed flow from {start_node.name}")
            return result

        # Create all tasks (they start executing immediately)
        tasks = [asyncio.create_task(run_flow(node)) for node in self.start_nodes]

        # Wait for all to complete (they run concurrently)
        results = await asyncio.gather(*tasks)

        print(f"[ParallelFlowNode:{self.name}] All flows completed")

        return "default"
