# Field Mapping in Linear Workflows

Linear workflows support field mapping to control how data flows between steps.

## Basic Concepts

### Outputs Mapping
Map specific fields from a step's output to named variables in shared state:

```yaml
- name: get_input
  type: interactive
  fields:
    - name: name
    - name: topic
  outputs:
    user_name: name      # shared["user_name"] = output["name"]
    user_topic: topic    # shared["user_topic"] = output["topic"]
```

### Inputs Mapping
Map shared state fields to specific input fields for a step:

```yaml
- name: validate
  type: script
  script: python3 validate.py
  inputs:
    content: analysis    # input["content"] = shared["analysis"]
```

## Template Variables

Agent prompts support template variables:

- `{{field_name}}` - Direct field from shared state
- `{{previous_output}}` - Full JSON of previous step's output
- `{{previous_output.field}}` - Specific field from previous output

Example:
```yaml
- name: process
  type: agent
  template: simple-assistant
  prompt: "Analyze {{user_topic}} for {{user_name}}"
```

## Step Types

### Interactive Step
Collect user input via terminal:

```yaml
- name: get_input
  type: interactive
  prompt: "Enter your details"
  fields:
    - name: username
      label: "Username"
      default: "alice"
    - name: email
      label: "Email address"
  outputs:
    user: username
    contact: email
```

### Script Step
Execute shell commands with JSON I/O:

```yaml
- name: process
  type: script
  script: python3 process.py
  inputs:
    data: user_input     # Pass specific field
  outputs:
    result: output       # Extract specific field
```

### Agent Step
Run AI agent with template variables:

```yaml
- name: analyze
  type: agent
  template: analyst
  prompt: "Analyze: {{data}}"
  outputs:
    report: content
```

## Complete Example

```yaml
apiVersion: v1
kind: LinearWorkflow
metadata:
  name: data-pipeline

spec:
  steps:
    # Step 1: Get user input
    - name: collect
      type: interactive
      prompt: "Data collection"
      fields:
        - name: dataset
          label: "Dataset name"
        - name: format
          label: "Output format"
      outputs:
        dataset_name: dataset
        output_format: format

    # Step 2: Process with agent
    - name: process
      type: agent
      template: processor
      prompt: "Process {{dataset_name}} as {{output_format}}"
      outputs:
        processed_data: content

    # Step 3: Validate
    - name: validate
      type: script
      script: python3 validate.py
      inputs:
        data: processed_data
        format: output_format
```

## Tips

1. **Use descriptive names**: `user_email` better than `e`
2. **Keep it simple**: Only map fields you need
3. **Avoid deep nesting**: Flat structures are clearer
4. **Default behavior**: Without mappings, entire `output` is passed
