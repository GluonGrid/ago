# Creating Custom Nodes

Create your own workflow nodes by inheriting from `AgoNode`.

## Quick Start

```python
from ago.core.nodes import AgoNode

class MyCustomNode(AgoNode):
    async def exec_async(self, prep_res):
        input_data = prep_res.get("input")

        # Your custom logic here
        result = do_something(input_data)

        return {"output": result, "success": True}
```

## What You Get Automatically

✅ **Dotted notation**: `node.field`, `node.nested.field`
✅ **Input mapping**: `inputs: {data: other_node.content}`
✅ **Output mapping**: `outputs: {result: content}`
✅ **Template variables**: `{{node.field}}` in prompts
✅ **Backwards compatibility**: Works with old syntax

## Example: CSV Node

```python
from ago.core.nodes import AgoNode
import csv
import json

class CSVNode(AgoNode):
    def __init__(self, name, file_path, operation="read", **kwargs):
        super().__init__(name, **kwargs)
        self.file_path = file_path
        self.operation = operation

    async def exec_async(self, prep_res):
        if self.operation == "read":
            # Read CSV file
            with open(self.file_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            return {"output": {"rows": rows}, "success": True}

        elif self.operation == "write":
            # Write CSV file
            data = prep_res.get("input", {})
            rows = data.get("rows", [])

            if rows:
                with open(self.file_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)

            return {"output": {"written": len(rows)}, "success": True}
```

### Usage in Workflow

```yaml
spec:
  nodes:
    - name: load_data
      type: csv
      file: data.csv
      operation: read

    - name: process
      type: agent
      prompt: "Analyze these records: {{load_data.rows}}"

    - name: save_results
      type: csv
      file: results.csv
      operation: write
      inputs:
        rows: process.content

  flow: "load_data >> process >> save_results"
```

## Example: API Node

```python
from ago.core.nodes import AgoNode
import aiohttp

class APINode(AgoNode):
    def __init__(self, name, url, method="GET", headers=None, **kwargs):
        super().__init__(name, **kwargs)
        self.url_template = url
        self.method = method
        self.headers = headers or {}

    async def prep_async(self, shared):
        # Get mapped inputs
        prep_res = await super().prep_async(shared)

        # Resolve URL template
        url = self.resolve_template(self.url_template, shared)
        prep_res["url"] = url

        return prep_res

    async def exec_async(self, prep_res):
        url = prep_res.get("url")
        input_data = prep_res.get("input")

        async with aiohttp.ClientSession() as session:
            if self.method == "GET":
                async with session.get(url, headers=self.headers) as resp:
                    data = await resp.json()
            elif self.method == "POST":
                async with session.post(url, json=input_data, headers=self.headers) as resp:
                    data = await resp.json()

        return {"output": data, "success": True}
```

### Usage in Workflow

```yaml
spec:
  nodes:
    - name: get_user
      type: interactive
      fields:
        - name: user_id

    - name: fetch_profile
      type: api
      url: "https://api.example.com/users/{{get_user.user_id}}"
      method: GET

    - name: analyze
      type: agent
      prompt: "Analyze this user profile: {{fetch_profile.name}}"

  flow: "get_user >> fetch_profile >> analyze"
```

## Advanced: Template Resolution

Use `self.resolve_template()` for dynamic values:

```python
class EmailNode(AgoNode):
    def __init__(self, name, to, subject, body, **kwargs):
        super().__init__(name, **kwargs)
        self.to_template = to
        self.subject_template = subject
        self.body_template = body

    async def prep_async(self, shared):
        prep_res = await super().prep_async(shared)

        # Resolve all templates
        prep_res["to"] = self.resolve_template(self.to_template, shared)
        prep_res["subject"] = self.resolve_template(self.subject_template, shared)
        prep_res["body"] = self.resolve_template(self.body_template, shared)

        return prep_res

    async def exec_async(self, prep_res):
        # Send email
        await send_email(
            to=prep_res["to"],
            subject=prep_res["subject"],
            body=prep_res["body"]
        )

        return {"output": {"sent": True}, "success": True}
```

### Usage

```yaml
- name: send_report
  type: email
  to: "{{user.email}}"
  subject: "Analysis Report for {{user.name}}"
  body: |
    Hi {{user.name}},

    Your analysis is complete:
    {{analysis.summary}}
```

## Conditional Edges

Return different edge names for branching:

```python
class ConditionalNode(AgoNode):
    def __init__(self, name, condition, **kwargs):
        super().__init__(name, **kwargs)
        self.condition = condition

    async def post_async(self, shared, prep_res, exec_res):
        # Store output
        await super().post_async(shared, prep_res, exec_res)

        # Evaluate condition
        score = exec_res["output"].get("score", 0)

        if score > 0.8:
            return "high"
        elif score > 0.5:
            return "medium"
        else:
            return "low"
```

### Usage with Flow

```yaml
spec:
  nodes:
    - name: quality_check
      type: conditional

    - name: premium_path
      type: agent

    - name: standard_path
      type: agent

  flow: |
    quality_check -"high">> premium_path
    quality_check -"low">> standard_path
```

## Registration

Add your custom node to the workflow system:

```python
# In ago/core/workflow.py or your custom module

from .nodes.csv_node import CSVNode
from .nodes.api_node import APINode

NODE_REGISTRY = {
    "script": ScriptNode,
    "agent": AgentNode,
    "interactive": InteractiveNode,
    "csv": CSVNode,
    "api": APINode,
}

def create_node(step):
    node_type = step["type"]
    NodeClass = NODE_REGISTRY.get(node_type)

    if not NodeClass:
        raise ValueError(f"Unknown node type: {node_type}")

    return NodeClass(...)
```

## Best Practices

1. **Inherit from AgoNode** - Get all mapping features automatically
2. **Implement exec_async()** - Your main logic goes here
3. **Return {"output": ..., "success": ...}** - Standard format
4. **Use resolve_template()** - For dynamic values
5. **Override prep_async()** - For custom preparation
6. **Override post_async()** - For conditional edges

## Testing Your Node

```python
import asyncio
from ago.core.nodes import AgoNode

# Your custom node
class TestNode(AgoNode):
    async def exec_async(self, prep_res):
        return {"output": {"result": "test"}, "success": True}

# Test it
async def test():
    node = TestNode("test_node")
    shared = {}
    result = await node.run_async(shared)
    print(shared["test_node"])  # {"result": "test"}

asyncio.run(test())
```

Happy node building! 🚀
