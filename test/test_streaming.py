import asyncio
import copy
import time
from typing import Any, AsyncIterator


class AsyncConcurrentBatchNode:
    def __init__(self):
        self.params = {}
        self.successors = {}

    def next(self, node, action="default"):
        """Chain nodes together."""
        self.successors[action] = node
        return node

    def __rshift__(self, other):
        """Allow using >> operator for chaining."""
        return self.next(other)

    def __sub__(self, action):
        """Allow using - operator for conditional actions."""
        return _ConditionalTransition(self, action)

    async def prep_async(self, shared, item=None):
        """
        Default: pass through item (no preprocessing).

        Override this ONLY if:
        1. You're an ENTRY node (item=None) - return list of items or single item
        2. You need preprocessing (item!=None) - transform and return item

        Most chained nodes don't need to override this!
        """
        return item  # Smart default: just pass through

    async def exec_async(self, prep_res):
        """Execute the node's main logic. ALWAYS override this."""
        pass

    async def post_async(self, shared, prep_res, exec_res):
        """Post-process and return action for next node."""
        return "default"

    async def _run_single_with_continuation(self, shared, item, idx, skip_prep=False):
        """
        Execute this node for one item, then continue to next node.
        Each item follows its own independent path!
        """
        try:
            # STEP 1: Prep/preprocess (skip for entry node on its own items)
            if skip_prep:
                prep_res = item  # Entry node already prepped, just use item
            else:
                prep_res = await self.prep_async(shared, item)

            # STEP 2: Execute
            exec_res = await self.exec_async(prep_res)

            # STEP 3: Post-process and get action
            action = await self.post_async(shared, prep_res, exec_res)

            # STEP 4: Continue to next node if exists
            next_node = self.successors.get(action or "default")
            if next_node:
                next_node_copy = copy.copy(next_node)
                return await next_node_copy._run_single_with_continuation(
                    shared, exec_res, idx, skip_prep=False
                )

            return (idx, exec_res)

        except Exception as e:
            return (idx, e)

    async def _exec_streaming(
        self, shared, items, is_entry=True
    ) -> AsyncIterator[tuple[int, Any]]:
        """Execute items concurrently and yield results as they complete."""
        tasks = {}

        # Handle single item (not a list)
        if not isinstance(items, list):
            items = [items]

        for idx, item in enumerate(items):
            task = asyncio.create_task(
                self._run_single_with_continuation(
                    shared, item, idx, skip_prep=is_entry
                )
            )
            tasks[task] = idx

        while tasks:
            done, pending = await asyncio.wait(
                tasks.keys(), return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                tasks.pop(task)
                idx, result = await task
                yield (idx, result)

    async def run_streaming(self, shared) -> AsyncIterator[tuple[int, Any]]:
        """Public API to stream results as they complete."""
        items = await self.prep_async(shared, item=None)
        async for idx, result in self._exec_streaming(shared, items, is_entry=True):
            yield (idx, result)


class _ConditionalTransition:
    def __init__(self, src, action):
        self.src = src
        self.action = action

    def __rshift__(self, tgt):
        return self.src.next(tgt, self.action)


# ============================================================================
# GENERIC FAN-OUT NODE
# ============================================================================


class FanOutNode(AsyncConcurrentBatchNode):
    """
    Generic fan-out node that routes items based on their data.

    Each item should have a "node_name" field that specifies which route to take.

    Usage:
        shared = {
            "items": [
                {"text": "Hello", "node_name": "ascii", ...},
                {"text": "World", "node_name": "reverse", ...},
            ]
        }

        fan_out = FanOutNode()
        fan_out - "ascii" >> ascii_node
        fan_out - "reverse" >> reverse_node
    """

    async def prep_async(self, shared, item=None):
        """Return list of items from shared."""
        if isinstance(shared, list):
            return shared
        items = shared.get("items", [])
        print(f"📋 [FanOut] Loaded {len(items)} items for concurrent processing\n")
        return items

    async def exec_async(self, prep_res):
        """Just pass through the item."""
        return prep_res

    async def post_async(self, shared, prep_res, exec_res):
        """Route based on the item's node_name field."""
        node_name = exec_res.get("node_name", "default")
        language = exec_res.get("language", "unknown")
        print(f"   → Routing {language} to '{node_name}' action\n")
        return node_name


# ============================================================================
# FAN-IN NODE (Internal - created automatically)
# ============================================================================


class _FanInNode(AsyncConcurrentBatchNode):
    """
    Internal fan-in node that collects all results from parallel paths.
    Users don't create this directly - it's auto-created by list >> node syntax.
    """

    def __init__(self, expected_count):
        super().__init__()
        self.expected_count = expected_count
        self.collected_items = []
        self.collection_lock = asyncio.Lock()
        self.collection_event = asyncio.Event()

    async def prep_async(self, shared, item=None):
        """Collect items until all are received."""
        if item is None:
            raise RuntimeError("FanInNode cannot be used as entry point")

        async with self.collection_lock:
            self.collected_items.append(item)
            collected = len(self.collected_items)

            print(f"      📥 [FanIn] Collected {collected}/{self.expected_count} items")

            if collected == self.expected_count:
                print(f"      ✅ [FanIn] All {self.expected_count} items collected!\n")
                self.collection_event.set()

        return item

    async def exec_async(self, prep_res):
        """Execute only after all items are collected."""
        await self.collection_event.wait()
        return prep_res

    async def post_async(self, shared, prep_res, exec_res):
        """Continue to next node."""
        return "default"


# ============================================================================
# EXTENDED LIST FOR IMPLICIT FAN-IN
# ============================================================================


class NodeList(list):
    """Extended list that supports >> operator for implicit fan-in."""

    def __rshift__(self, other):
        if not isinstance(other, AsyncConcurrentBatchNode):
            raise TypeError(
                f"Can only use >> with AsyncConcurrentBatchNode, got {type(other)}"
            )

        # Create implicit fan-in node
        fan_in = _FanInNode(expected_count=len(self))

        # Connect all nodes to fan-in
        for node in self:
            node >> fan_in

        # Connect fan-in to target node
        fan_in >> other

        return other


# ============================================================================
# PROCESSING NODES
# ============================================================================


class TranslateCharToIntNode(AsyncConcurrentBatchNode):
    """Converts characters to ASCII."""

    async def exec_async(self, prep_res):
        language = prep_res["language"]
        text = prep_res["text"]
        print(f"   🔢 [CharToInt] Converting {language}...")
        await asyncio.sleep(prep_res["sleep_time"])
        char_to_int = [f"{char}→{ord(char)}" for char in text]
        return {
            "language": language,
            "original_text": text,
            "transformed_text": " ".join(char_to_int),
            "transformation": "char_to_ascii",
            "process_time": prep_res["sleep_time"],
        }

    async def post_async(self, shared, prep_res, exec_res):
        print(f"   ✓  [CharToInt] {exec_res['language']} complete\n")
        return "default"


class CapitalizeEveryOtherNode(AsyncConcurrentBatchNode):
    """Capitalizes every other character."""

    async def exec_async(self, prep_res):
        language = prep_res["language"]
        text = prep_res["text"]
        print(f"   🔠 [CapitalizeEveryOther] Processing {language}...")
        await asyncio.sleep(prep_res["sleep_time"])
        result = "".join(
            char.upper() if i % 2 == 0 else char.lower() for i, char in enumerate(text)
        )
        return {
            "language": language,
            "original_text": text,
            "transformed_text": result,
            "transformation": "capitalize_every_other",
            "process_time": prep_res["sleep_time"],
        }

    async def post_async(self, shared, prep_res, exec_res):
        print(f"   ✓  [CapitalizeEveryOther] {exec_res['language']} complete\n")
        return "default"


class ReverseStringNode(AsyncConcurrentBatchNode):
    """Reverses the text string."""

    async def exec_async(self, prep_res):
        language = prep_res["language"]
        text = prep_res["text"]
        print(f"   🔄 [ReverseString] Reversing {language}...")
        await asyncio.sleep(prep_res["sleep_time"])
        return {
            "language": language,
            "original_text": text,
            "transformed_text": text[::-1],
            "transformation": "reverse",
            "process_time": prep_res["sleep_time"],
        }

    async def post_async(self, shared, prep_res, exec_res):
        print(f"   ✓  [ReverseString] {exec_res['language']} complete\n")
        return "default"


class SummarizeNode(AsyncConcurrentBatchNode):
    """Summarize results."""

    async def exec_async(self, prep_res):
        language = prep_res["language"]
        print(f"      📊 [Summarize] Creating summary for {language}...")
        await asyncio.sleep(0.3)

        summary = {
            "language": language,
            "transformation": prep_res["transformation"],
            "original": prep_res["original_text"],
            "result": prep_res["transformed_text"][:50] + "..."
            if len(prep_res["transformed_text"]) > 50
            else prep_res["transformed_text"],
            "process_time": prep_res["process_time"],
        }

        return summary

    async def post_async(self, shared, prep_res, exec_res):
        print(f"      ✓  [Summarize] Complete for {exec_res['language']}\n")
        return "default"


class FinalReportNode(AsyncConcurrentBatchNode):
    """Generate final report."""

    async def exec_async(self, prep_res):
        print(f"         📝 [FinalReport] Finalizing {prep_res['language']}...")
        await asyncio.sleep(0.2)

        report = {
            "language": prep_res["language"],
            "status": "completed",
            "transformation": prep_res["transformation"],
            "summary": f"{prep_res['language']}: {prep_res['transformation']}",
            "duration": prep_res["process_time"],
        }

        return report

    async def post_async(self, shared, prep_res, exec_res):
        print(f"         ✓  [FinalReport] Report ready for {exec_res['language']}\n")
        return "default"


# ============================================================================
# MAIN DEMO
# ============================================================================


async def main():
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 18 + "GENERIC FAN-OUT WITH DATA-DRIVEN ROUTING" + " " * 20 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    print("Flow architecture:")
    print()
    print("                         ┌─→ Spanish → CharToInt ──────────┐")
    print("  FanOut ────────────────┼─→ German  → CapitalizeEvery ────┼─→ [FanIn]")
    print("  (generic!)             └─→ French  → ReverseString ───────┘")
    print()
    print("                                        ↓")
    print()
    print("                                   Summarize")
    print()
    print("                                        ↓")
    print()
    print("                                   FinalReport")
    print()
    print("Routing is data-driven: each item specifies its target via 'node_name'!")
    print("=" * 80)
    print()

    # Data with routing information embedded
    shared = {
        "items": [
            {
                "text": "Hello World",
                "language": "Spanish",
                "node_name": "ascii",  # Route to ASCII node
                "sleep_time": 1.5,
            },
            {
                "text": "Hello World",
                "language": "German",
                "node_name": "capitalize",  # Route to capitalize node
                "sleep_time": 2.25,
            },
            {
                "text": "Hello World",
                "language": "French",
                "node_name": "reverse",  # Route to reverse node
                "sleep_time": 3.0,
            },
        ]
    }

    # Create generic FanOut - completely reusable!
    fan_out = FanOutNode()

    # Create processing nodes
    char_to_int = TranslateCharToIntNode()
    capitalize = CapitalizeEveryOtherNode()
    reverse = ReverseStringNode()
    summarize = SummarizeNode()
    final_report = FinalReportNode()

    # Connect based on node_name in data
    fan_out - "ascii" >> char_to_int
    fan_out - "capitalize" >> capitalize
    fan_out - "reverse" >> reverse

    # FanIn and continue
    NodeList([char_to_int, capitalize, reverse]) >> summarize >> final_report

    print("Starting concurrent execution...\n")
    print("=" * 80)
    print()

    start_time = time.perf_counter()

    results = []
    async for idx, result in fan_out.run_streaming(shared):
        elapsed = time.perf_counter() - start_time
        results.append(result)

        print("╔" + "=" * 78 + "╗")
        print(f"║  🎉 COMPLETED [{elapsed:.2f}s] - {result['status']:<48} ║")
        print("╠" + "=" * 78 + "╣")
        print(f"║  Summary: {result['summary']:<63} ║")
        print(f"║  Duration: {result['duration']}s{' ' * 60} ║")
        print("╚" + "=" * 78 + "╝")
        print()

    total_time = time.perf_counter() - start_time

    print("=" * 80)
    print(f"✅ TOTAL TIME: {total_time:.2f}s")
    print(f"📦 Collected {len(results)} final reports")
    print("=" * 80)
    print()
    print("Key features:")
    print("  ✓ Generic FanOutNode - completely reusable!")
    print("  ✓ Data-driven routing via 'node_name' field")
    print("  ✓ No hardcoded routing logic in nodes")
    print("  ✓ Implicit FanIn with NodeList syntax")
    print("  ✓ True concurrent execution with streaming")
    print()
    print("Data structure:")
    print(
        '  {"text": "...", "language": "...", "node_name": "ascii", "sleep_time": 1.5}'
    )
    print("                                      ^^^^^^^^^^^^^^^^^^")
    print("                                      Routes to correct node!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
