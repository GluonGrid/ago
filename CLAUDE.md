# Ago: AI Agent Development Guidelines

> **IMPORTANT**: If you are an AI agent (Claude Code, GitHub Copilot, or similar) contributing to the Ago project, read this guide **VERY CAREFULLY**. This document outlines the architecture, coding standards, and development workflow you must follow.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Core Architecture](#core-architecture)
3. [Technology Stack](#technology-stack)
4. [Development Principles](#development-principles)
5. [Code Structure & Organization](#code-structure--organization)
6. [Coding Standards](#coding-standards)
7. [Common Development Tasks](#common-development-tasks)
8. [Testing Requirements](#testing-requirements)
9. [Important Patterns](#important-patterns)
10. [What NOT to Do](#what-not-to-do)

---

## Project Overview

**Ago** is a Docker-like CLI for orchestrating AI agents. Think "Docker for AI" - users can run, manage, and compose specialized AI agents using familiar Docker commands.

### Key Features

- **Docker-like commands**: `ago run`, `ago ps`, `ago chat`, `ago stop`
- **Specialized agents**: researcher, assistant, analyst, writer, coordinator
- **Multi-agent workflows**: Agents communicate via async queues
- **ReAct intelligence**: Reasoning + Acting pattern with tool usage
- **MCP integration**: Model Context Protocol for standardized tools
- **Production architecture**: UNIX process isolation with daemon management
- **Beautiful TUI**: Textual-based terminal interface

### Design Philosophy

1. **Simplicity First**: Use the simplest solution that works
2. **Standards Over Reinvention**: Leverage existing frameworks (PocketFlow, Typer, Textual)
3. **Developer Experience**: Make it intuitive for users AND contributors
4. **Production Ready**: Proper process isolation, error handling, logging

---

## Core Architecture

### Three-Layer Architecture

```
┌─────────────────────────────────────────────┐
│         CLI Layer (Typer + Rich)            │
│  Commands: run, chat, ps, logs, stop, etc.  │
└───────────────────┬─────────────────────────┘
                    │ Unix Socket IPC
┌───────────────────▼─────────────────────────┐
│           Daemon Layer (asyncio)            │
│  - Agent lifecycle management               │
│  - Inter-agent message routing              │
│  - Process orchestration                    │
│  - State persistence                        │
└───────────────────┬─────────────────────────┘
                    │ Process spawning
┌───────────────────▼─────────────────────────┐
│      Agent Processes (PocketFlow)           │
│  Each agent = isolated UNIX process         │
│  - ReAct reasoning loop                     │
│  - MCP tool execution                       │
│  - Async message queues                     │
└─────────────────────────────────────────────┘
```

### Data Flow

**User Command Flow:**
```
User types `ago chat researcher`
→ CLI parses command (Typer)
→ DaemonClient sends request via Unix socket
→ Daemon routes to agent process
→ Agent executes ReAct loop
→ Response flows back through socket
→ CLI displays with Rich formatting
```

**Agent Reasoning Flow (ReAct Pattern):**
```
User message → prep_async() → Load context (scratchpad, tools, history)
                            ↓
                    exec_async() → LLM decides: Tool use or Final answer
                            ↓
                  Tool execution or Answer ready
                            ↓
                  post_async() → Update scratchpad, decide next action
                            ↓
           Loop back to exec_async() OR End flow
```

---

## Technology Stack

### Core Dependencies (MUST USE)

1. **[PocketFlow](https://the-pocket.github.io/PocketFlow/)** - LLM workflow framework
   - **Why**: 100-line minimalist framework for agent orchestration
   - **Use for**: Agent nodes, flows, async patterns
   - **Pattern**: AsyncNode with `prep_async()`, `exec_async()`, `post_async()`

2. **[Typer](https://typer.tiangolo.com/)** - CLI framework
   - **Why**: Modern, type-hint based CLI with minimal boilerplate
   - **Use for**: All CLI commands, argument parsing
   - **Pattern**: Decorators with type hints

3. **[Rich](https://rich.readthedocs.io/)** - Terminal output
   - **Why**: Beautiful tables, progress bars, formatting
   - **Use for**: Console output, error messages, progress indicators
   - **Pattern**: `Console()` for all output

4. **[Textual](https://textual.textualize.io/)** - TUI framework
   - **Why**: Modern TUI with widgets, CSS-like styling, async support
   - **Use for**: Chat interface, dashboard views
   - **Pattern**: `App` with `Widget` composition

5. **[FastMCP](https://github.com/jlowin/fastmcp)** - Model Context Protocol
   - **Why**: Standardized tool integration for LLMs
   - **Use for**: Tool discovery, execution, formatting
   - **Pattern**: MCP servers → tool discovery → LLM consumption

6. **[PyYAML](https://pyyaml.org/)** - Configuration parsing
   - **Why**: Human-friendly config format
   - **Use for**: Agent templates (.agt), workflows (.spec), config files

7. **[asyncio](https://docs.python.org/3/library/asyncio.html)** - Async programming
   - **Why**: Handle concurrent agent operations, I/O-bound tasks
   - **Use for**: Agent communication, tool execution, daemon operations

### LLM Provider

- **Anthropic Claude** (primary): `claude-sonnet-4-20250514`
- API calls via `aiohttp` (async HTTP client)
- Must support image inputs for multimodal agents

---

## Development Principles

### 1. Follow PocketFlow Patterns

**DO:**
```python
from pocketflow import AsyncNode, AsyncFlow

class MyAgentNode(AsyncNode):
    async def prep_async(self, shared):
        """Prepare context - READ from shared store"""
        return {
            "user_input": shared["user_message"],
            "context": shared.get("scratchpad", "")
        }

    async def exec_async(self, prep_res):
        """Execute logic - NO shared access"""
        result = await some_async_operation(prep_res)
        return result

    async def post_async(self, shared, prep_res, exec_res):
        """Post-process - WRITE to shared store"""
        shared["result"] = exec_res
        return "next_action"  # Return action name for flow routing
```

**Key Rules:**
- `prep_async()`: Read from shared store, return data for exec
- `exec_async()`: Pure computation, NO shared access
- `post_async()`: Write to shared store, return action for routing
- Use `AsyncFlow` to connect nodes: `node1 >> node2`

### 2. Follow Typer Best Practices

**DO:**
```python
import typer
from rich.console import Console

app = typer.Typer(help="Command group description")
console = Console()

@app.command()
def my_command(
    # Positional argument with help text
    agent_name: str = typer.Argument(..., help="Name of the agent"),

    # Optional flag with default
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),

    # Option with default value
    model: str = typer.Option("claude-3-5-sonnet-20241022", "--model", help="LLM model")
):
    """
    Clear command description shown in --help.

    Provide detailed explanation here.
    """
    if verbose:
        console.print("[cyan]Verbose mode enabled[/cyan]")

    try:
        # Command logic
        result = perform_operation(agent_name, model)
        console.print(f"[green]✓[/green] Success: {result}")

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {str(e)}")
        raise typer.Exit(1)
```

**Key Rules:**
- Use type hints for automatic validation
- Provide clear help text for all parameters
- Use `Console()` for all output (never `print()`)
- Handle errors gracefully with rich error messages
- Return proper exit codes (0 = success, 1 = error)

### 3. Follow Textual Patterns

**DO:**
```python
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Static, Input

class MyApp(App):
    """Textual app with CSS styling"""

    CSS = """
    #my_container {
        background: $surface;
        border: solid $primary;
        padding: 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with Container(id="my_container"):
            yield Static("Hello World")
            yield Input(placeholder="Type here...")

    def on_mount(self) -> None:
        """Called when app is mounted"""
        self.title = "My App"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        self.query_one(Static).update(f"You typed: {event.value}")
```

**Key Rules:**
- Inherit from `App` or `Widget`
- Use `compose()` to build UI hierarchy
- CSS for styling (separate from logic)
- Use reactive programming for dynamic updates
- Async methods for I/O operations

### 4. Handle Async Properly

**DO:**
```python
import asyncio

# Async function
async def async_operation():
    result = await some_async_call()
    return result

# Call from sync context
def sync_function():
    result = asyncio.run(async_operation())
    return result

# Call from async context
async def async_function():
    result = await async_operation()
    return result

# Multiple concurrent operations
async def parallel_operations():
    results = await asyncio.gather(
        operation1(),
        operation2(),
        operation3()
    )
    return results
```

**Key Rules:**
- Always `await` async functions
- Use `asyncio.run()` only at entry points (CLI commands)
- Use `asyncio.gather()` for concurrent operations
- Don't mix sync/async without proper wrappers

---

## Code Structure & Organization

### File Organization

```
ago/
├── cli/                    # CLI commands (Typer)
│   ├── main.py            # Main commands (run, chat, ps, logs)
│   ├── mcp_commands.py    # MCP-specific commands
│   └── tui/               # Textual TUI
│       └── agent_chat.py  # Chat interface
│
├── core/                   # Core daemon & orchestration
│   ├── daemon.py          # Main daemon (agent lifecycle)
│   ├── daemon_client.py   # Unix socket client
│   ├── config.py          # Configuration management
│   ├── registry.py        # Template discovery
│   ├── base_node.py       # PocketFlow base class
│   ├── supervisor.py      # LLM service & parsing
│   ├── mcp_integration.py # MCP tool loading
│   └── tool_formatter.py  # Format tools for LLM
│
├── agents/                 # Agent logic (PocketFlow)
│   ├── agent_react_flow.py        # ReAct agent factory
│   └── streaming_react_wrapper.py # Streaming support
│
├── templates/              # Built-in agent templates
│   └── *.agt              # YAML agent definitions
│
└── cookbook/               # Example workflows
    └── *.spec             # Multi-agent specs
```

### Where to Add Code

**Adding CLI commands?** → `ago/cli/main.py`
**Adding daemon logic?** → `ago/core/daemon.py`
**Modifying agent reasoning?** → `ago/agents/agent_react_flow.py`
**Adding MCP integration?** → `ago/core/mcp_integration.py`
**New agent template?** → `ago/templates/my_agent.agt`
**TUI changes?** → `ago/cli/tui/agent_chat.py`

---

## Coding Standards

### 1. Type Hints (REQUIRED)

**DO:**
```python
from typing import Dict, List, Optional, Any

async def send_message(
    from_agent: str,
    to_agent: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Send message between agents."""
    # Implementation
    return {"status": "success", "id": "msg-123"}
```

**DON'T:**
```python
async def send_message(from_agent, to_agent, content):
    # Missing type hints
    return {"status": "success"}
```

### 2. Docstrings (REQUIRED for public APIs)

**DO:**
```python
async def create_agent(
    agent_name: str,
    template: str,
    config: Dict[str, Any]
) -> str:
    """
    Create a new agent from template.

    Args:
        agent_name: Unique name for the agent instance
        template: Template name (e.g., "researcher")
        config: Agent configuration dict with model, tools, etc.

    Returns:
        Agent instance ID (e.g., "researcher-abc123")

    Raises:
        ValueError: If template not found
        RuntimeError: If agent creation fails
    """
    # Implementation
```

### 3. Error Handling

**DO:**
```python
from rich.console import Console

console = Console()

try:
    result = await risky_operation()
    console.print(f"[green]✓[/green] Operation succeeded")
except ValueError as e:
    console.print(f"[yellow]⚠[/yellow] Validation error: {str(e)}")
    # Maybe retry or prompt user
except Exception as e:
    console.print(f"[red]✗ Error:[/red] {str(e)}")
    logger.exception("Unexpected error in operation")
    raise typer.Exit(1)
```

**DON'T:**
```python
try:
    result = operation()
except:  # Bare except - TOO BROAD
    print("Error")  # No details
    pass  # Silently swallow
```

### 4. Logging

**DO:**
```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate levels
logger.debug("Detailed debug info")
logger.info("Normal operation")
logger.warning("Something unexpected but handled")
logger.error("Error occurred but recoverable")
logger.exception("Critical error with traceback")
```

**Configure logging:**
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### 5. Code Formatting

**Use Black (line length 88):**
```bash
black ago/
```

**Use Ruff for linting:**
```bash
ruff check ago/
```

**Type checking with mypy:**
```bash
mypy ago/
```

---

## Common Development Tasks

### Task 1: Add New CLI Command

**File:** `ago/cli/main.py`

```python
@app.command()
def inspect(
    agent_name: str = typer.Argument(..., help="Agent name to inspect")
):
    """
    Show detailed information about an agent.

    Displays configuration, status, tools, and recent activity.
    """
    try:
        # Use daemon client for communication
        daemon_client = DaemonClient()
        response = asyncio.run(daemon_client.inspect_agent(agent_name))

        # Display with Rich table
        table = Table(title=f"Agent: {agent_name}")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        for key, value in response["agent_info"].items():
            table.add_row(key, str(value))

        console.print(table)

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {str(e)}")
        raise typer.Exit(1)
```

**Then add daemon handler in `ago/core/daemon.py`:**

```python
async def _handle_client(self, reader, writer):
    # ... existing code ...

    elif command == "inspect":
        agent_name = data["agent_name"]
        result = await self._inspect_agent(agent_name)
        response = {"status": "success", "agent_info": result}

async def _inspect_agent(self, agent_name: str) -> Dict[str, Any]:
    """Get detailed agent information."""
    if agent_name not in self.agents:
        raise ValueError(f"Agent {agent_name} not found")

    agent = self.agents[agent_name]
    return {
        "name": agent["agent_name"],
        "model": agent["spec"]["model"],
        "tools": agent["spec"]["tools"],
        "status": "running",
        # ... more info
    }
```

### Task 2: Modify Agent Reasoning

**File:** `ago/agents/agent_react_flow.py`

To change how agents think, modify the prompt template in `exec_async()`:

```python
async def exec_async(self, prep_res):
    """Execute ReAct reasoning cycle."""

    # Build reasoning prompt
    prompt = f"""You are {self.agent_name}, a specialized AI agent.

## Your Task
{prep_res['user_message']}

## Context
{prep_res['scratchpad']}

## Available Tools
{self._format_tools(prep_res['tools'])}

## Instructions
Think step-by-step using this format:

```yaml
thought: |
  Your reasoning about what to do next
action: tool_name  # OR "final_answer"
parameters:
  param1: value1
  param2: value2
```

If you have enough information, use action: final_answer with your answer.
"""

    # Call LLM
    response = await LLMService.call_llm(
        prompt,
        agent_name=self.agent_name,
        images=prep_res.get('images')
    )

    # Parse YAML response
    parsed = YAMLParser.parse(response)

    # Execute action
    if parsed["action"] == "final_answer":
        return {
            "action": "final_answer",
            "answer": parsed.get("answer", parsed.get("thought"))
        }
    else:
        # Execute tool
        tool_result = await call_tool_async(
            parsed["action"],
            parsed.get("parameters", {}),
            self.agent_name
        )
        return {
            "action": "continue",
            "tool": parsed["action"],
            "result": tool_result
        }
```

### Task 3: Add New Agent Template

**File:** `ago/templates/my_custom_agent.agt`

```yaml
name: my_custom_agent
version: "1.0"
description: "Specialized agent for specific domain tasks"
author: "Your Name <you@example.com>"
model: claude-3-5-sonnet-20241022
temperature: 0.7
tools: [web_search, file_manager, calculator]

prompt: |
  You are a Domain Expert Agent specializing in [DOMAIN].

  ## Your Expertise
  You excel at:
  - Domain-specific task 1
  - Domain-specific task 2
  - Domain-specific task 3

  ## Your Approach
  1. Analyze the user's request carefully
  2. Break complex problems into steps
  3. Use available tools effectively
  4. Provide clear, actionable answers

  ## Tool Usage Guidelines
  - web_search: For finding current information
  - file_manager: For reading/writing files
  - calculator: For mathematical operations

  ## Communication Style
  - Be concise but thorough
  - Explain your reasoning
  - Ask clarifying questions when needed

  Remember: Focus on delivering high-quality results in your domain.

metadata:
  category: "specialized"
  use_cases:
    - "Use case 1"
    - "Use case 2"
  requires_human_oversight: false
```

### Task 4: Add MCP Tool Integration

**File:** `~/.ago/mcp_servers.yaml` (user config, not in repo)

```yaml
servers:
  # Filesystem access
  filesystem:
    command: uvx
    args: ["mcp-server-filesystem", "/Users/username/workspace"]

  # Web search
  brave-search:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-brave-search"]
    env:
      BRAVE_API_KEY: ${BRAVE_API_KEY}

  # Custom tool
  my_custom_tool:
    command: python
    args: ["/path/to/my_mcp_server.py"]
    env:
      CUSTOM_API_KEY: ${CUSTOM_API_KEY}
```

**No code changes needed** - tools auto-discovered by `ago/core/mcp_integration.py`!

---

## Testing Requirements

### Running Tests

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_daemon.py -v

# Run with coverage
pytest --cov=ago tests/

# Run async tests
pytest -v -k "async"
```

### Writing Tests

**Example test structure:**

```python
import pytest
import asyncio
from ago.core.daemon_client import DaemonClient

@pytest.mark.asyncio
async def test_send_message():
    """Test inter-agent messaging."""
    client = DaemonClient()

    # Send message
    response = await client.send_message(
        from_agent="agent1",
        to_agent="agent2",
        content="Test message"
    )

    # Verify response
    assert response["status"] == "success"
    assert "message_id" in response

@pytest.mark.asyncio
async def test_error_handling():
    """Test proper error handling."""
    client = DaemonClient()

    with pytest.raises(ValueError):
        await client.send_message(
            from_agent="nonexistent",
            to_agent="agent2",
            content="Test"
        )
```

### Test Coverage Requirements

- **Core daemon logic**: 80%+ coverage
- **CLI commands**: Manual testing + smoke tests
- **Agent nodes**: Unit tests for prep/exec/post
- **MCP integration**: Mock external tool calls

---

## Important Patterns

### Pattern 1: PocketFlow Agent Node

```python
from pocketflow import AsyncNode
from ..core.base_node import BaseAgentNode

class MyAgentNode(BaseAgentNode):
    """Agent node following ReAct pattern."""

    def __init__(self, agent_name: str, config: Dict[str, Any]):
        super().__init__(agent_name, max_iterations=50)
        self.config = config

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare reasoning context."""
        return {
            "user_message": shared.get("user_message", ""),
            "scratchpad": shared.get("scratchpad", ""),
            "tools": shared.get("tools", []),
            "history": shared.get("conversation_history", [])
        }

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """Execute reasoning cycle."""
        # LLM reasoning
        response = await self._reason(prep_res)

        # Execute tool or return answer
        if response["action"] == "final_answer":
            return {"type": "answer", "content": response["answer"]}
        else:
            tool_result = await self._execute_tool(response)
            return {"type": "continue", "result": tool_result}

    async def post_async(
        self,
        shared: Dict[str, Any],
        prep_res: Dict[str, Any],
        exec_res: Dict[str, Any]
    ) -> str:
        """Post-process and update state."""
        if exec_res["type"] == "answer":
            shared["final_answer"] = exec_res["content"]
            return "end"  # Terminate flow
        else:
            # Append to scratchpad for next iteration
            shared["scratchpad"] += f"\nTool result: {exec_res['result']}"
            return "continue"  # Loop back to exec_async
```

### Pattern 2: Daemon Request Handler

```python
# ago/core/daemon.py

async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle incoming client requests."""
    try:
        # Read request
        data = await reader.read(10000)
        request = json.loads(data.decode())

        command = request.get("command")
        payload = request.get("data", {})

        # Route to handler
        if command == "create_agent":
            response = await self._create_agent(payload)
        elif command == "send_message":
            response = await self._send_message(payload)
        elif command == "list_agents":
            response = await self._list_agents()
        else:
            response = {"status": "error", "message": f"Unknown command: {command}"}

        # Send response
        writer.write(json.dumps(response).encode())
        await writer.drain()

    except Exception as e:
        self.logger.exception("Error handling client request")
        error_response = {"status": "error", "message": str(e)}
        writer.write(json.dumps(error_response).encode())
        await writer.drain()

    finally:
        writer.close()
        await writer.wait_closed()
```

### Pattern 3: Rich Console Output

```python
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Simple messages
console.print("[green]✓[/green] Success!")
console.print("[yellow]⚠[/yellow] Warning message")
console.print("[red]✗ Error:[/red] Something failed")

# Tables
table = Table(title="Running Agents")
table.add_column("Name", style="cyan")
table.add_column("Status", style="green")
table.add_column("Model", style="blue")

table.add_row("researcher-abc", "running", "claude-3-5-sonnet")
table.add_row("assistant-def", "running", "claude-3-5-haiku")

console.print(table)

# Progress indicators
with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    console=console
) as progress:
    task = progress.add_task("Creating agent...", total=None)
    # Do work
    progress.update(task, description="[green]✓[/green] Agent created")
```

---

## What NOT to Do

### ❌ DON'T: Access shared store in exec_async()

```python
# WRONG
async def exec_async(self, prep_res):
    user_input = self.shared["user_message"]  # ❌ NO DIRECT ACCESS
    # ...
```

**Instead:** Pass all needed data through `prep_async()` return value.

### ❌ DON'T: Use print() for output

```python
# WRONG
print("Agent created")  # ❌ UGLY, NO FORMATTING
print(f"Error: {e}")    # ❌ NO COLOR
```

**Instead:** Use Rich Console:
```python
console.print("[green]✓[/green] Agent created")
console.print(f"[red]✗ Error:[/red] {str(e)}")
```

### ❌ DON'T: Mix sync and async incorrectly

```python
# WRONG
def sync_function():
    await async_call()  # ❌ Can't await in sync function

async def async_function():
    result = sync_blocking_call()  # ❌ Blocks event loop
```

**Instead:**
```python
# Correct
def sync_function():
    result = asyncio.run(async_call())  # ✓ Proper sync wrapper

async def async_function():
    result = await asyncio.to_thread(sync_blocking_call)  # ✓ Run in thread
```

### ❌ DON'T: Swallow errors silently

```python
# WRONG
try:
    risky_operation()
except:
    pass  # ❌ SILENT FAILURE
```

**Instead:**
```python
# Correct
try:
    risky_operation()
except ValueError as e:
    logger.warning(f"Validation error: {e}")
    # Handle gracefully
except Exception as e:
    logger.exception("Unexpected error")
    raise  # Re-raise after logging
```

### ❌ DON'T: Create agents without daemon

```python
# WRONG - Bypasses daemon architecture
agent = MyAgentNode(...)
result = await agent.run(shared)  # ❌ NOT MANAGED BY DAEMON
```

**Instead:** Always use daemon client:
```python
# Correct
daemon_client = DaemonClient()
response = await daemon_client.create_agent(
    template="researcher",
    agent_name="my-researcher"
)
```

### ❌ DON'T: Hardcode file paths

```python
# WRONG
config_path = "/Users/username/.ago/config.yaml"  # ❌ BREAKS ON WINDOWS
```

**Instead:**
```python
# Correct
from pathlib import Path
config_path = Path.home() / ".ago" / "config.yaml"  # ✓ CROSS-PLATFORM
```

### ❌ DON'T: Add unnecessary dependencies

Before adding a new dependency, ask:
1. Is there a stdlib alternative?
2. Is it already transitively included?
3. Does it align with project philosophy?

**Current dependencies are carefully chosen** - don't bloat the stack!

---

## Summary Checklist

When contributing code, verify:

- [ ] **Type hints** on all function signatures
- [ ] **Docstrings** for public APIs
- [ ] **Error handling** with informative messages
- [ ] **Rich Console** for all CLI output
- [ ] **Async/await** used correctly
- [ ] **PocketFlow patterns** followed (prep/exec/post)
- [ ] **Logging** at appropriate levels
- [ ] **Tests** written for new functionality
- [ ] **Black** formatting applied
- [ ] **Ruff** linting passes
- [ ] **No breaking changes** without discussion

---

## Getting Help

If you're an AI agent and:
- **Unsure about architecture**: Review PocketFlow docs and this file
- **Hit a bug**: Check logs in `~/.ago/logs/`
- **Need clarification**: Ask the human developer
- **Want to propose changes**: Open a GitHub issue first

**Remember**: You're working on a production system. Prioritize correctness, maintainability, and user experience over clever solutions.

Happy coding! 🚀

---

**Document Version**: 2.0
**Last Updated**: December 2025
**Maintained by**: Ago Development Team
