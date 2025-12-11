#!/usr/bin/env python3
"""
Extended PocketFlow with streaming/concurrent execution capabilities.

Adds new node/flow types that yield results as they complete instead of
waiting for all parallel tasks to finish.
"""
import asyncio
import warnings
import copy
from typing import AsyncIterator, Any

# Import base PocketFlow classes
from pocketflow import (
    AsyncNode,
    AsyncBatchNode,
    AsyncParallelBatchNode,
    AsyncFlow,
    AsyncBatchFlow,
    AsyncParallelBatchFlow,
)


# ============================================================================
# NEW: CONCURRENT NODES THAT YIELD RESULTS AS THEY COMPLETE
# ============================================================================


class AsyncConcurrentBatchNode(AsyncParallelBatchNode):
    """
    Executes items concurrently and yields results as they complete.
    Each completed item continues to the next node immediately.

    Inherits from AsyncParallelBatchNode to avoid MRO issues.
    """

    async def _exec_streaming(self, items) -> AsyncIterator[tuple[int, Any]]:
        """Execute items and yield (index, result) as they complete."""
        tasks = {}
        for idx, item in enumerate(items):
            # Call the exec_async method for each item
            task = asyncio.create_task(self.exec_async(item))
            tasks[task] = idx

        while tasks:
            # Wait for next task to complete
            done, pending = await asyncio.wait(
                tasks.keys(), return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                idx = tasks.pop(task)
                try:
                    result = await task
                    yield (idx, result)
                except Exception as e:
                    yield (idx, e)

    async def _exec(self, items):
        """Collect all results (for backward compatibility)."""
        results = [None] * len(items)
        async for idx, result in self._exec_streaming(items):
            results[idx] = result
        return results


# ============================================================================
# NEW: CONCURRENT FLOWS THAT ALLOW INDEPENDENT EXECUTION
# ============================================================================


class AsyncConcurrentBatchFlow(AsyncParallelBatchFlow):
    """
    Spawns multiple flow executions that run independently.
    Each flow continues through its path without waiting for others.
    Results are yielded as flows complete.

    Inherits from AsyncParallelBatchFlow to avoid MRO issues.
    """

    async def _run_async_streaming(
        self, shared
    ) -> AsyncIterator[tuple[int, Any]]:
        """Execute flows and yield (index, result) as they complete."""
        pr = await self.prep_async(shared) or []

        tasks = {}
        for idx, bp in enumerate(pr):
            task = asyncio.create_task(
                self._orch_async(shared, {**self.params, **bp})
            )
            tasks[task] = idx

        while tasks:
            done, pending = await asyncio.wait(
                tasks.keys(), return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                idx = tasks.pop(task)
                try:
                    result = await task
                    yield (idx, result)
                except Exception as e:
                    yield (idx, e)

        await self.post_async(shared, pr, None)

    async def _run_async(self, shared):
        """Collect all results (for backward compatibility)."""
        results = []
        async for idx, result in self._run_async_streaming(shared):
            results.append((idx, result))
        return await self.post_async(
            shared, [r[1] for r in sorted(results)], None
        )

    async def run_async_streaming(
        self, shared
    ) -> AsyncIterator[tuple[int, Any]]:
        """Public API to stream results as they complete."""
        async for idx, result in self._run_async_streaming(shared):
            yield idx, result


# ============================================================================
# ADVANCED: CONCURRENT NODE WITH INDEPENDENT FLOW CONTINUATION
# ============================================================================


class AsyncConcurrentNode(AsyncNode):
    """
    A node that spawns concurrent tasks where each task continues
    independently through the flow graph after completion.

    This is the key class for forked flows: each concurrent execution
    follows its own successor path without waiting for other branches.
    """

    async def prep_async(self, shared):
        """Return list of items to process concurrently."""
        return []

    async def exec_async(self, prep_res):
        """Execute single item."""
        pass

    async def _spawn_concurrent_execution(self, shared, item, idx):
        """
        Execute a single item and continue through successors.
        This is the key: each concurrent execution follows its own path.
        """
        try:
            # Execute this node for this item
            result = await super()._exec(item)

            # Get the action to determine next node
            action = await self.post_async(shared, item, result)

            # Continue to next node if exists
            next_node = self.successors.get(action or "default")
            if next_node:
                next_node_copy = copy.copy(next_node)
                next_node_copy.set_params(self.params)

                # Continue the flow with this result
                if isinstance(next_node_copy, AsyncNode):
                    final_result = await next_node_copy._run_async(shared)
                else:
                    final_result = next_node_copy._run(shared)

                return (idx, final_result)

            return (idx, result)

        except Exception as e:
            return (idx, e)

    async def _run_async(self, shared):
        """Execute all items concurrently, each following its own path."""
        prep_res = await self.prep_async(shared)
        items = prep_res if isinstance(prep_res, list) else [prep_res]

        # Spawn all concurrent tasks immediately
        tasks = [
            asyncio.create_task(
                self._spawn_concurrent_execution(shared, item, idx)
            )
            for idx, item in enumerate(items)
        ]

        # Wait for all tasks to complete (they run in parallel)
        results = await asyncio.gather(*tasks)

        # Return sorted by original index
        return [r[1] for r in sorted(results, key=lambda x: x[0])]

    async def run_async_streaming(
        self, shared
    ) -> AsyncIterator[tuple[int, Any]]:
        """Stream results as they complete."""
        prep_res = await self.prep_async(shared)
        items = prep_res if isinstance(prep_res, list) else [prep_res]

        tasks = {
            asyncio.create_task(
                self._spawn_concurrent_execution(shared, item, idx)
            ): idx
            for idx, item in enumerate(items)
        }

        while tasks:
            done, pending = await asyncio.wait(
                tasks.keys(), return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                tasks.pop(task)
                idx, result = await task
                yield (idx, result)
