# Workflows Cookbook

Examples and documentation for creating workflows with Ago: linear, parallel, conditional, and mixed.

## Quick Start

```bash
# Run a simple linear workflow
ago up --file cookbook/workflows/simple_linear_workflow.spec

# Run an interactive workflow
ago up --file cookbook/workflows/interactive_workflow.spec

# Run a parallel workflow
ago up --file cookbook/workflows/parallel_analysis.spec
```

## What are Workflows?

Workflows define how nodes execute. Each workflow type serves different purposes:

### Linear Workflows
Execute nodes sequentially: Step 1 → Step 2 → Step 3

### Parallel Workflows
Execute multiple nodes simultaneously: Input → [Agent 1, Agent 2, Agent 3] → Merge

### Conditional Workflows
Branch based on node outputs: Check -"valid"→ Process, Check -"invalid"→ Retry

### Mixed Workflows
Combine any of the above patterns in a single workflow

Each node can be:
- **script** - Execute shell commands with JSON I/O
- **agent** - Run AI agents with template variables
- **interactive** - Collect user input via terminal
- **merge** - Combine outputs from multiple parallel nodes

## Examples in this Directory

### 1. Simple Linear Workflow (`simple_linear_workflow.spec`)
Basic three-step workflow demonstrating:
- Script generating input data
- Agent processing the data
- Script validating the output

### 2. Interactive Workflow (`interactive_workflow.spec`)
Interactive workflow demonstrating:
- User input collection with multiple fields
- Field mapping between steps with dotted notation
- Template variables in agent prompts

### 3. Parallel Analysis (`parallel_analysis.spec`)
Parallel workflow demonstrating:
- Fan-out: One input triggers multiple agents
- Parallel execution of sentiment, summary, and keyword extraction
- Fan-in: Merge all results with a custom script

### 4. Parallel with MergeNode (`parallel_with_merge.spec`)
Parallel workflow using built-in MergeNode:
- Same parallel pattern as above
- Uses MergeNode instead of custom script
- Demonstrates dict merge strategy

## Documentation

- [Quick Start Guide](./QUICK_START.md)
- [Linear Workflow Guide](./LINEAR_WORKFLOW.md)
- [Field Mapping Guide](./FIELD_MAPPING.md)
- [MergeNode Guide](./MERGE_NODE.md) - **NEW**: Combine parallel results

## Scripts

Helper scripts used by the example workflows are in `scripts/`:
- `step1_input.py` - Simple input generator
- `step3_validate.py` - Simple validation script

## Creating Your Own Workflows

1. Copy an example spec file
2. Modify the steps to fit your needs
3. Add custom scripts if needed
4. Run with `ago up --file your-workflow.spec`

## Adding Custom Node Types

Node types are defined in `ago/core/nodes/`:
- `script_node.py` - ScriptNode implementation
- `interactive_node.py` - InteractiveNode implementation
- `agent_node.py` - AgentNode implementation
- `merge_node.py` - MergeNode implementation (for combining parallel results)

To add a new node type (e.g., CSV processing):

1. Create `ago/core/nodes/csv_node.py`:
```python
from pocketflow import AsyncNode

class CsvNode(AsyncNode):
    def __init__(self, name: str, csv_file: str, ...):
        super().__init__()
        self.name = name
        self.csv_file = csv_file

    async def prep_async(self, shared):
        # Get input from previous step
        pass

    async def exec_async(self, prep_res):
        # Process CSV file
        pass

    async def post_async(self, shared, prep_res, exec_res):
        # Pass output to next step
        return "default"
```

2. Add to `ago/core/nodes/__init__.py`:
```python
from .csv_node import CsvNode

__all__ = ["ScriptNode", "InteractiveNode", "AgentNode", "CsvNode"]
```

3. Register in `ago/core/workflow.py`:
```python
elif step_type == "csv":
    node = CsvNode(
        step_name,
        step["file"],
        ...
    )
```

4. Use in your workflow spec:
```yaml
- name: process_data
  type: csv
  file: data.csv
  outputs:
    records: rows
```

## Examples of Custom Nodes

Potential custom nodes you could create:
- **CSVNode** - Read/write CSV files
- **DatabaseNode** - Query databases
- **APINode** - Call REST APIs
- **FileNode** - File operations (read, write, transform)
- **ConditionNode** - Conditional branching
- **LoopNode** - Iterate over data
- **ParallelNode** - Run multiple agents in parallel
- **EmailNode** - Send emails
- **NotificationNode** - Slack/Discord notifications

The modular design makes it easy to extend!
