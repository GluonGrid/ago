# Linear Workflows in Ago

Execute sequential workflows: **script → agent → validation** using PocketFlow.

## Quick Start

```bash
# Run a linear workflow
ago linear examples/simple_linear_workflow.spec
```

## How It Works

Linear workflows execute steps sequentially, passing output from one step to the next:

```
Step 1 (Script)  →  Step 2 (Agent)  →  Step 3 (Validation)
   output.json        agent_result       final_result
```

## Workflow Spec Format

```yaml
apiVersion: v1
kind: LinearWorkflow
metadata:
  name: my-workflow
  description: Description here

spec:
  steps:
    - name: get_input
      type: script
      script: python step1.py

    - name: process
      type: agent
      template: assistant
      prompt: "Process this: {{previous_output}}"

    - name: validate
      type: script
      script: python step3.py
```

## Step Types

### 1. Script Step
Runs a script that outputs JSON to stdout:

```python
#!/usr/bin/env python3
import json

# Your logic here
result = {"key": "value"}

# Output to stdout
print(json.dumps(result))
```

### 2. Agent Step
Runs an AI agent with the previous step's output:

```yaml
- name: process
  type: agent
  template: assistant  # any ago template
  prompt: "Analyze: {{previous_output}}"
```

The `{{previous_output}}` placeholder is replaced with the previous step's JSON output.

### 3. Validation Step
Validates the agent's output:

```python
#!/usr/bin/env python3
import json
import sys

# Read from stdin
data = json.loads(sys.stdin.read())

# Validate
if is_valid(data):
    print(json.dumps({"status": "valid"}))
    sys.exit(0)
else:
    print(json.dumps({"status": "invalid"}))
    sys.exit(1)  # Non-zero = failure
```

## Example: Complete Workflow

```yaml
# simple_workflow.spec
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
      prompt: |
        Given this input: {{previous_output}}
        Generate a detailed response about the topic.

    - name: validate
      type: script
      script: python scripts/step3_validate.py
```

## Data Flow

Each step receives the previous step's output:

1. **Step 1 (Script)**: Outputs `{"name": "Alice", "topic": "AI"}`
2. **Step 2 (Agent)**: Receives the JSON, processes it, outputs `{"content": "response..."}`
3. **Step 3 (Validation)**: Receives agent output, validates format

## vs. Parallel Workflows

- **Linear** (`ago linear`): Steps run sequentially, output flows step-to-step
- **Parallel** (`ago up`): Agents run independently, communicate via messages

Use linear workflows for:
- ETL pipelines (Extract → Transform → Load)
- Input → Process → Validate patterns
- Sequential data transformations

Use parallel workflows for:
- Multi-agent collaboration
- Independent concurrent tasks
- Pub/sub message patterns

## Built with PocketFlow

Linear workflows use PocketFlow's async nodes and flow system with the `>>` operator:

```python
from pocketflow import AsyncNode, AsyncFlow

# Create linear chain: step1 → step2 → step3
step1 - "continue" >> step2
step2 - "continue" >> step3

flow = AsyncFlow(start=step1)
await flow.run(shared)
```

This provides:
- ✅ Automatic error handling
- ✅ State management via shared dict
- ✅ Clean async execution
- ✅ Simple edge definitions with `>>`
