# MergeNode Guide

The MergeNode combines outputs from multiple upstream nodes into a single output. It's perfect for fan-in patterns in parallel workflows.

## Usage

```yaml
- name: combine
  type: merge
  strategy: dict  # or list, or concat
  inputs:
    sentiment: sentiment_node.content
    summary: summary_node.content
    keywords: keywords_node.content
```

## Merge Strategies

### 1. `dict` (default)
Combines inputs into a dictionary with named keys.

**Example:**
```yaml
- name: merge_results
  type: merge
  strategy: dict
  inputs:
    sentiment: sentiment_node.content
    summary: summary_node.content
    keywords: keywords_node.content
```

**Output:**
```json
{
  "sentiment": "positive",
  "summary": "AI is transforming technology...",
  "keywords": ["AI", "machine learning", "technology"]
}
```

### 2. `list`
Combines inputs into a list (order not guaranteed).

**Example:**
```yaml
- name: merge_results
  type: merge
  strategy: list
  inputs:
    result1: node1.output
    result2: node2.output
    result3: node3.output
```

**Output:**
```json
["result from node1", "result from node2", "result from node3"]
```

### 3. `concat`
Concatenates inputs into a single string (separated by double newlines).

**Example:**
```yaml
- name: merge_reports
  type: merge
  strategy: concat
  inputs:
    intro: intro_node.text
    body: body_node.text
    conclusion: conclusion_node.text
```

**Output:**
```
Introduction text here...

Body content here...

Conclusion text here...
```

## Auto-Collection Mode

If you don't specify `inputs`, MergeNode automatically collects all node outputs from shared state:

```yaml
- name: auto_merge
  type: merge
  strategy: dict
  # No inputs specified - collects everything
```

This is useful when you want to merge all upstream nodes without explicitly listing them.

## Complete Example

Here's a parallel workflow that uses MergeNode:

```yaml
apiVersion: v1
kind: Workflow
metadata:
  name: parallel-analysis

spec:
  nodes:
    - name: input
      type: interactive
      prompt: "Enter text to analyze"
      fields:
        - name: text
          label: "Text"

    - name: sentiment
      type: agent
      template: simple-assistant
      prompt: "Analyze sentiment: {{input.text}}"

    - name: summary
      type: agent
      template: simple-assistant
      prompt: "Summarize: {{input.text}}"

    - name: keywords
      type: agent
      template: simple-assistant
      prompt: "Extract keywords: {{input.text}}"

    - name: combine
      type: merge
      strategy: dict
      inputs:
        sentiment: sentiment.content
        summary: summary.content
        keywords: keywords.content

  flow: |
    input >> [sentiment, summary, keywords]
    [sentiment, summary, keywords] >> combine
```

## Field Mapping

Use `inputs` to map specific fields from upstream nodes:

```yaml
inputs:
  # Map from node.field
  sentiment_analysis: sentiment.content
  summary_text: summary.output
  keyword_list: keywords.items
```

Use `outputs` to create shortcuts for the merged result:

```yaml
outputs:
  final_result: merged
  report: merged
```

## When to Use MergeNode vs ScriptNode

**Use MergeNode when:**
- You need simple aggregation of parallel results
- You want built-in merge strategies (dict, list, concat)
- You don't need custom processing logic

**Use ScriptNode when:**
- You need custom merge logic
- You need to transform or validate data
- You need to call external services
- You need complex data processing

## Examples in Cookbook

See these example workflows:
- `parallel_with_merge.spec` - Basic MergeNode usage
- `parallel_analysis.spec` - ScriptNode for custom merge logic
