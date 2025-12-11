# Forked Flows Pattern

Forked flows allow you to split workflow execution into multiple independent paths that run concurrently.

## When to Use

Use forked flows when:
- You need to process the same input in different ways simultaneously
- The processing paths are independent and don't need to merge
- You want to optimize for speed by running parallel operations
- Different flows have different completion times

## Example: Dual Processing Paths

The `forked_flows.spec` demonstrates a common pattern:

```
Input
  ├─→ Flow A (Fast Path) → Validate A
  └─→ Flow B (Deep Path) → Validate B
```

### Flow Definition

```yaml
flow: |
  collect_input >> [process_a_fast, process_b_deep]
  process_a_fast >> validate_a
  process_b_deep >> validate_b
```

This creates:
- **Fan-out**: `collect_input` triggers both `process_a_fast` and `process_b_deep` in parallel
- **Independent paths**: Each flow continues independently
- **No merge**: Flows complete separately

## How It Works

1. **ParallelNode is created** for the fan-out: `collect_input >> [process_a_fast, process_b_deep]`
2. **Both nodes run concurrently** using `asyncio.gather`
3. **Each flow continues independently** with its own linear path
4. **Both validations run** (possibly at different times)

## Execution Flow

```
Time →

0s:  collect_input ─┐
                    │
1s:  ┌──────────────┴──────────────┐
     │                             │
     process_a_fast           process_b_deep
     (quick summary)          (detailed analysis)
     │                             │
2s:  validate_a                    │
     ✓ Complete                    │
                                   │
5s:                            validate_b
                               ✓ Complete
```

## Use Cases

### 1. Fast + Slow Processing

Process the same data with:
- Quick approximate result (for immediate feedback)
- Detailed analysis (for comprehensive result)

### 2. Multiple Output Formats

Generate different outputs simultaneously:
- PDF report generation
- JSON data export
- Email notification

### 3. Parallel Validations

Run different validation strategies:
- Format validation
- Business logic validation
- External API validation

### 4. Multi-Model Processing

Use different AI models in parallel:
- Fast model for quick results
- Accurate model for quality results
- Specialized model for specific tasks

## Advanced: Truly Independent Flows

For flows that fork into completely separate AsyncFlow instances (not just parallel nodes), you would need to create multiple workflow specs and orchestrate them at a higher level:

```python
# Hypothetical: Run two separate workflows concurrently
import asyncio

flow_a = create_workflow_a()
flow_b = create_workflow_b()

results = await asyncio.gather(
    flow_a.run_async(shared),
    flow_b.run_async(shared)
)
```

This is useful when:
- Flows are defined in separate spec files
- Flows have completely different node structures
- You need maximum isolation between flows

## Limitations

Current implementation:
- ✅ Parallel fan-out works perfectly
- ✅ Independent linear paths after fan-out work
- ❌ Cannot have flows that end at different times with different merge points
- ❌ Cannot have conditional re-joining (use conditional edges instead)

For complex flow control with dynamic merging, consider using PocketFlow's conditional edges (`-"action">>`) or separate workflow orchestration.

## Testing

Run the forked flows example:

```bash
ago up --file cookbook/workflows/forked_flows.spec
```

You'll see:
1. Input collection
2. Both processes start simultaneously
3. Both validations complete (possibly at different times)
4. Workflow completes when all paths finish
