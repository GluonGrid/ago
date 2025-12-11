#!/usr/bin/env python3
"""
ParallelNode: Execute multiple nodes in parallel using PocketFlow's AsyncParallelBatchNode
"""

from typing import Any, List

from pocketflow import AsyncParallelBatchNode


class ParallelNode(AsyncParallelBatchNode):
    """
    Wrapper that executes multiple child nodes in parallel.

    This is an internal node created by the flow parser when it detects
    parallel patterns like: input >> [node1, node2, node3]

    Uses PocketFlow's AsyncParallelBatchNode which uses asyncio.gather internally.
    """

    def __init__(self, name: str, parallel_nodes: List[Any]):
        """
        Initialize ParallelNode.

        Args:
            name: Node name
            parallel_nodes: List of nodes to execute in parallel
        """
        super().__init__()
        self.name = name
        self.parallel_nodes = parallel_nodes

    async def prep_async(self, shared):
        """Prepare batch items - one per parallel node"""
        print(
            f"[ParallelNode:{self.name}] Starting {len(self.parallel_nodes)} nodes in parallel"
        )
        # Store shared in instance for use in exec_async
        self.shared = shared
        # Return list of items for batch processing (just the nodes)
        return [{"node": node} for node in self.parallel_nodes]

    async def exec_async(self, prep_res):
        """Execute a single node from the parallel batch (called by AsyncParallelBatchNode)"""
        node = prep_res["node"]

        print(f"[ParallelNode:{self.name}] Starting {node.name}")

        # Use run_async() to handle the full node lifecycle
        result = await node.run_async(self.shared)

        print(f"[ParallelNode:{self.name}] Completed {node.name}")
        return {"success": True, "node_name": node.name, "result": result}

    async def post_async(self, shared, prep_res, exec_res_list):
        """All parallel nodes completed (exec_res_list contains all results)"""
        print(f"[ParallelNode:{self.name}] All {len(exec_res_list)} nodes completed")
        return "default"
