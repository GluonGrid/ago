# Linear Workflows - Quick Start

## What We Built

A simple plug-and-play linear workflow system for `ago` using PocketFlow:

```
Script (input) → Agent (process) → Script (validate)
```

## Files Created

```
ago/
├── ago/core/workflow.py          # PocketFlow-based workflow engine
├── ago/cli/main.py                  # Added "ago linear" command
└── examples/
    ├── simple_linear_workflow.spec  # Workflow definition
    ├── scripts/
    │   ├── step1_input.py          # Get user input → JSON
    │   └── step3_validate.py       # Validate JSON → exit code
    └── LINEAR_WORKFLOW.md           # Full documentation
```

## Usage

```bash
# Run the workflow
ago linear examples/simple_linear_workflow.spec

# Output:
# Step 1: Get input (runs step1_input.py)
# Step 2: Process with agent (runs assistant agent)
# Step 3: Validate (runs step3_validate.py)
```

## How It Works

### 1. Workflow Spec
```yaml
apiVersion: v1
kind: LinearWorkflow
metadata:
  name: simple-example

spec:
  steps:
    - name: get_input
      type: script
      script: python scripts/step1_input.py

    - name: process
      type: agent
      template: assistant
      prompt: "Process: {{previous_output}}"

    - name: validate
      type: script
      script: python scripts/step3_validate.py
```

### 2. Scripts (Super Simple)

**Input Script** (outputs JSON):
```python
import json
name = input("Name: ")
print(json.dumps({"name": name}))
```

**Validate Script** (reads JSON from stdin):
```python
import json, sys
data = json.loads(sys.stdin.read())
sys.exit(0 if valid(data) else 1)
```

### 3. PocketFlow Engine

```python
# In ago/core/workflow.py
step1 - "continue" >> step2
step2 - "continue" >> step3
flow = AsyncFlow(start=step1)
await flow.run(shared)
```

## Key Features

✅ **Simple**: Just define steps in YAML
✅ **Plug-and-play**: Scripts just input/output JSON
✅ **PocketFlow**: Uses existing ago infrastructure
✅ **New command**: `ago linear` for sequential workflows
✅ **Separate from `ago up`**: Parallel vs Linear workflows

## Example: Custom Workflow

```yaml
# my_workflow.spec
apiVersion: v1
kind: LinearWorkflow
metadata:
  name: data-pipeline

spec:
  steps:
    - name: extract
      type: script
      script: python extract_data.py

    - name: transform
      type: agent
      template: analyst
      prompt: "Analyze and transform: {{previous_output}}"

    - name: load
      type: script
      script: python load_to_db.py
```

Run it:
```bash
ago linear my_workflow.spec
```

## vs. Parallel Workflows

| Feature | `ago linear` | `ago up` |
|---------|-------------|----------|
| Execution | Sequential | Parallel |
| Data Flow | Output → Input | Messages |
| Use Case | ETL, Pipelines | Multi-agent |
| Workflow Kind | `LinearWorkflow` | `AgentWorkflow` |

## What's Next

To extend this system, you could add:
- Retry logic on failures
- Conditional branching
- Loop/iteration steps
- Parallel sub-steps
- State persistence

All by extending the PocketFlow nodes in `ago/core/workflow.py`!
