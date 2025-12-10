# Ago Workflow Vision 🎯

## Goal: n8n-style Workflow Builder for AI Agents

Build a flexible workflow system where users can create flows by connecting nodes, just like n8n or any visual automation tool - but for AI agents.

## Core Concept

**Ago Nodes = Wrappers around PocketFlow Nodes**

Users define workflows in YAML that compile to PocketFlow graphs. The YAML syntax supports both simple linear flows and complex parallel/conditional flows.

## Architecture

```
YAML Spec → Ago Parser → PocketFlow Graph → Execution
```

### Components:

1. **Ago Nodes** (`ago/core/nodes/`)
   - Thin wrappers around `AsyncNode`, `AsyncBatchNode`, `AsyncParallelBatchNode`
   - Handle I/O, field mapping, and agent communication
   - Examples: `ScriptNode`, `AgentNode`, `InteractiveNode`, `LoopNode`

2. **Flow Builder** (`ago/core/flow_builder.py`)
   - Parses YAML specs into PocketFlow graphs
   - Supports connections: `>>`, `- "action" >>`
   - Handles flow types: `Flow`, `AsyncBatchFlow`, `AsyncParallelBatchFlow`

3. **YAML Spec** (user-facing)
   - Declarative workflow definition
   - Simple syntax for connections
   - Support for parallel, batch, and conditional flows

## Workflow Types

### 1. Linear Flow (Sequential)
```yaml
apiVersion: v1
kind: Workflow
metadata:
  name: simple-pipeline

spec:
  type: linear  # AsyncFlow with >> connections

  nodes:
    - name: input
      type: interactive
      fields: [name, topic]

    - name: analyze
      type: agent
      template: analyst
      prompt: "Analyze {{topic}} for {{name}}"

    - name: save
      type: script
      script: python save.py

  connections:
    - from: input
      to: analyze

    - from: analyze
      to: save
```

**Compiles to PocketFlow:**
```python
input_node >> analyze_node >> save_node
flow = AsyncFlow(start=input_node)
```

---

### 2. Parallel Flow (Multiple Agents)
```yaml
apiVersion: v1
kind: Workflow
metadata:
  name: multi-perspective

spec:
  type: parallel  # Multiple agents running concurrently

  nodes:
    - name: input
      type: script
      script: python get_text.py

    - name: sentiment
      type: agent
      template: sentiment-analyzer
      prompt: "Analyze sentiment: {{text}}"

    - name: summary
      type: agent
      template: summarizer
      prompt: "Summarize: {{text}}"

    - name: entities
      type: agent
      template: ner-extractor
      prompt: "Extract entities: {{text}}"

    - name: combine
      type: script
      script: python merge_results.py

  connections:
    # Fan-out pattern
    - from: input
      to: [sentiment, summary, entities]

    # Fan-in pattern
    - from: [sentiment, summary, entities]
      to: combine
```

**Compiles to PocketFlow:**
```python
# Fan-out
input_node >> sentiment_node
input_node >> summary_node
input_node >> entities_node

# Fan-in
sentiment_node >> combine_node
summary_node >> combine_node
entities_node >> combine_node

flow = AsyncFlow(start=input_node)
```

---

### 3. Batch Flow (Process Multiple Items)
```yaml
apiVersion: v1
kind: Workflow
metadata:
  name: batch-processor

spec:
  type: batch  # AsyncBatchFlow - sequential batching

  batch:
    items: records        # Field containing list
    item_var: record      # Variable name for each item

  nodes:
    - name: load
      type: script
      script: python load_data.py
      outputs:
        records: data

    - name: process
      type: agent
      template: processor
      prompt: "Process: {{record}}"

    - name: validate
      type: script
      script: python validate.py

  connections:
    - from: load
      to: process
    - from: process
      to: validate
```

**Compiles to PocketFlow:**
```python
load_node >> process_node >> validate_node

class DataBatchFlow(AsyncBatchFlow):
    async def prep_async(self, shared):
        records = shared.get("records", [])
        return [{"record": r} for r in records]

flow = DataBatchFlow(start=load_node)
```

---

### 4. Parallel Batch Flow (Process Items Concurrently)
```yaml
apiVersion: v1
kind: Workflow
metadata:
  name: parallel-batch

spec:
  type: parallel-batch  # AsyncParallelBatchFlow

  batch:
    items: images
    item_var: image
    parallel: true        # Use asyncio.gather

  nodes:
    - name: load
      type: script
      script: python get_images.py

    - name: analyze
      type: agent
      template: image-analyzer
      prompt: "Analyze image: {{image}}"

    - name: save
      type: script
      script: python save_results.py

  connections:
    - from: load
      to: analyze
    - from: analyze
      to: save
```

**Compiles to PocketFlow:**
```python
load_node >> analyze_node >> save_node

class ImageParallelBatchFlow(AsyncParallelBatchFlow):
    async def prep_async(self, shared):
        images = shared.get("images", [])
        return [{"image": img} for img in images]

flow = ImageParallelBatchFlow(start=load_node)
```

---

### 5. Conditional Flow (Branching)
```yaml
apiVersion: v1
kind: Workflow
metadata:
  name: conditional-router

spec:
  type: conditional

  nodes:
    - name: check
      type: script
      script: python quality_check.py
      outputs:
        score: quality_score

    - name: high_quality
      type: agent
      template: advanced-processor

    - name: low_quality
      type: agent
      template: basic-processor

    - name: finalize
      type: script
      script: python finalize.py

  connections:
    - from: check
      to: high_quality
      condition: "score > 0.8"  # Named edge

    - from: check
      to: low_quality
      condition: "score <= 0.8"

    - from: [high_quality, low_quality]
      to: finalize
```

**Compiles to PocketFlow:**
```python
check_node - "high" >> high_quality_node
check_node - "low" >> low_quality_node

high_quality_node >> finalize_node
low_quality_node >> finalize_node

flow = AsyncFlow(start=check_node)

# check_node.post_async() returns "high" or "low"
```

---

## Implementation Roadmap

### Phase 1: Foundation ✅
- [x] Create Ago node wrappers (ScriptNode, AgentNode, InteractiveNode)
- [x] Implement linear flow engine
- [x] Field mapping support
- [x] Template variable substitution

### Phase 2: Flow Builder 🚧
- [ ] Create `FlowBuilder` class to parse YAML specs
- [ ] Support connection syntax: `from/to` in YAML
- [ ] Detect flow type (linear, parallel, batch, conditional)
- [ ] Generate PocketFlow graphs from connections

### Phase 3: Advanced Flows 📋
- [ ] **Parallel flows** - Fan-out/fan-in patterns
- [ ] **Batch flows** - Sequential iteration (AsyncBatchFlow)
- [ ] **Parallel batch flows** - Concurrent processing (AsyncParallelBatchFlow)
- [ ] **Conditional flows** - Named edges for branching

### Phase 4: Advanced Nodes 📋
- [ ] **LoopNode** - Extend AsyncBatchNode for iteration
- [ ] **ParallelNode** - Extend AsyncParallelBatchNode for concurrency
- [ ] **ConditionalNode** - Branch based on conditions
- [ ] **MergeNode** - Combine outputs from multiple nodes
- [ ] **CSVNode** - CSV file operations
- [ ] **APINode** - REST API calls
- [ ] **DatabaseNode** - Database queries

### Phase 5: Visual Builder 🎯
- [ ] Web UI for visual workflow design (like n8n)
- [ ] Drag-and-drop node placement
- [ ] Visual connection drawing
- [ ] Export to YAML specs
- [ ] Live execution monitoring

---

## Simplified YAML Syntax

Users shouldn't need to know PocketFlow internals. They should write simple YAML:

### Simple Linear
```yaml
spec:
  nodes:
    - name: step1
      type: script
      script: python a.py
    - name: step2
      type: agent
      template: analyst

  # Optional - if omitted, nodes run in order
  connections:
    - step1 >> step2
```

### Parallel Agents
```yaml
spec:
  nodes:
    - name: input
      type: script
    - name: agent1
      type: agent
    - name: agent2
      type: agent
    - name: merge
      type: script

  connections:
    - input >> [agent1, agent2]  # Fan-out
    - [agent1, agent2] >> merge  # Fan-in
```

### Batch Processing
```yaml
spec:
  type: batch
  batch:
    items: records
    parallel: true  # Use AsyncParallelBatchFlow

  nodes:
    - name: process
      type: agent
      prompt: "Process {{item}}"
```

---

## Key Principles

1. **Simple by default** - Linear flows need minimal config
2. **Power when needed** - Support complex parallel/batch patterns
3. **PocketFlow underneath** - Leverage battle-tested execution engine
4. **Node extensibility** - Easy to add new node types
5. **Visual future** - YAML → Graph representation

---

## Example: Image Processing Pipeline

```yaml
apiVersion: v1
kind: Workflow
metadata:
  name: image-pipeline

spec:
  type: parallel-batch

  batch:
    items: images
    parallel: true

  nodes:
    - name: load
      type: script
      script: python load_images.py
      outputs:
        images: image_list

    - name: resize
      type: script
      script: python resize.py
      inputs:
        image: "{{item}}"

    - name: analyze
      type: agent
      template: vision-analyzer
      prompt: "Describe this image: {{item}}"

    - name: tag
      type: agent
      template: tagger
      prompt: "Generate tags based on: {{analysis}}"

    - name: save
      type: script
      script: python save_metadata.py

  connections:
    - load >> resize
    - resize >> [analyze, tag]  # Parallel analysis
    - [analyze, tag] >> save
```

**Result:**
- Loads all images
- For each image (in parallel):
  - Resize
  - Analyze with vision model
  - Generate tags with LLM
  - Save metadata
- Uses `AsyncParallelBatchFlow` for 10x speedup!

---

## Next Steps

1. **Implement FlowBuilder** - Parse YAML → PocketFlow graphs
2. **Add connection syntax** - Support `>>`, fan-out, fan-in
3. **Create batch nodes** - LoopNode, ParallelNode
4. **Test complex flows** - Multi-agent collaboration patterns
5. **Document patterns** - Cookbook examples for each flow type

**Goal:** Make Ago the best framework for building AI agent workflows! 🚀
