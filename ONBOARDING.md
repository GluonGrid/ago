# Ago Developer Onboarding Guide

Welcome to **Ago** - Docker for AI Agents! This guide will help you get up and running as a contributor to the project.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Development Setup](#development-setup)
4. [Key Concepts](#key-concepts)
5. [Project Structure](#project-structure)
6. [Development Workflow](#development-workflow)
7. [Testing](#testing)
8. [Contributing Guidelines](#contributing-guidelines)
9. [Common Tasks](#common-tasks)
10. [Resources](#resources)

---

## Project Overview

**Ago** is a Docker-like CLI for orchestrating AI agents with:
- **Specialized agents** (researcher, assistant, analyst, writer, coordinator)
- **Multi-agent workflows** with inter-agent communication
- **ReAct intelligence** (Reasoning + Acting pattern)
- **MCP tool integration** (Model Context Protocol)
- **Production-ready daemon architecture** with UNIX process isolation
- **Textual TUI** for professional terminal interface

**Think Docker, but for AI agents:**
```bash
ago run researcher --name DataMiner    # Like docker run
ago ps                                  # Like docker ps
ago chat DataMiner                      # Interactive chat
ago stop DataMiner                      # Like docker stop
```

---

## Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────┐
│                       CLI Layer                         │
│  (Typer + Rich) - User commands & beautiful output     │
└────────────────────┬────────────────────────────────────┘
                     │ Unix Socket IPC
┌────────────────────▼────────────────────────────────────┐
│                    Daemon Layer                         │
│  Background process managing all agents                 │
│  - Agent lifecycle management                           │
│  - Inter-agent message routing                          │
│  - Process orchestration                                │
└────────────────────┬────────────────────────────────────┘
                     │ Spawns & manages
┌────────────────────▼────────────────────────────────────┐
│                   Agent Processes                       │
│  Each agent runs in isolated UNIX process              │
│  - PocketFlow ReAct agents                             │
│  - MCP tool integration                                 │
│  - Async message queues                                 │
└─────────────────────────────────────────────────────────┘
```

### Core Technologies

- **[PocketFlow](https://github.com/The-Pocket/PocketFlow)**: 100-line minimalist LLM framework for agent workflows
- **[Typer](https://typer.tiangolo.com/)**: Modern CLI framework with type hints
- **[Rich](https://rich.readthedocs.io/)**: Beautiful terminal output
- **[Textual](https://textual.textualize.io/)**: Modern TUI framework
- **[FastMCP](https://github.com/jlowin/fastmcp)**: Model Context Protocol for tool integration
- **[asyncio](https://docs.python.org/3/library/asyncio.html)**: Asynchronous programming

### Agent Architecture (ReAct Pattern)

Each agent follows the **ReAct** (Reasoning + Acting) pattern:

```
User Input → Thought → Action → Observation → [Loop] → Final Answer
             (LLM)     (Tool)    (Result)              (LLM)
```

Implemented using **PocketFlow** AsyncNode:
- `prep_async()`: Prepare context (scratchpad, tools, history)
- `exec_async()`: LLM reasoning to decide next action
- `post_async()`: Execute tool or return final answer

---

## Development Setup

### Prerequisites

- **Python 3.12+** (required)
- **uv** (recommended package manager)
- **Anthropic API key** (for Claude LLM)

### Quick Setup

```bash
# 1. Clone the repository
git clone https://github.com/gluongrid/ago.git
cd ago

# 2. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Install dependencies
uv pip install -e ".[dev]"

# 4. Set up environment variables
export ANTHROPIC_API_KEY="your-api-key-here"

# 5. Verify installation
uv run ago --help
```

### Development Dependencies

```bash
# Install with dev tools
uv pip install -e ".[dev]"

# This includes:
# - pytest: Testing framework
# - pytest-asyncio: Async test support
# - black: Code formatter
# - ruff: Fast linter
# - mypy: Type checker
```

### Configuration Files

Ago uses two config locations:
1. **Global**: `~/.ago/config.yaml` (user-wide settings)
2. **Project**: `.ago/config.yaml` (project-specific overrides)

Example config:
```yaml
# ~/.ago/config.yaml
registries:
  builtin:
    type: builtin
    enabled: true
    priority: 1

defaults:
  model: claude-3-5-sonnet-20241022
  temperature: 0.7
  template_resolution_order: ["local", "builtin"]
```

---

## Key Concepts

### 1. Agent Templates (.agt files)

Templates define agent behavior in YAML format:

```yaml
name: researcher
version: "1.0"
description: "Research specialist agent"
author: "Ago Team"
model: claude-3-5-sonnet-20241022
temperature: 0.7
tools: [web_search, file_manager]

prompt: |
  You are a Research Specialist Agent...
  [Embedded prompt - no external files needed]
```

**Template Resolution Order:**
1. Current directory (`./custom-agent.agt`)
2. Global builtin (`~/.ago/registry/templates/builtin/`)
3. Pulled templates (`~/.ago/registry/templates/pulled/`)

### 2. Agent Specs (.spec files)

Multi-agent workflows defined in YAML:

```yaml
apiVersion: v1
kind: AgentWorkflow
metadata:
  name: research-team

spec:
  agents:
    - name: researcher
      model: claude-3-5-sonnet-20241022
      tools: [web_search]

    - name: assistant
      model: claude-3-5-haiku-20241022
      tools: [file_manager]
```

### 3. PocketFlow Integration

Ago uses PocketFlow's AsyncNode pattern for agent logic:

```python
class AgentReActNode(BaseAgentNode):
    async def prep_async(self, shared):
        # Prepare reasoning context
        return {
            "user_message": shared.get("user_message"),
            "scratchpad": shared.get("supervisor_scratchpad"),
            "tools": shared.get("tools"),
        }

    async def exec_async(self, prep_res):
        # LLM reasoning to decide action
        response = await LLMService.call_llm(prompt)
        parsed = YAMLParser.parse(response)

        if parsed["action"] == "final_answer":
            return {"action": "final_answer", "answer": parsed["answer"]}
        else:
            # Execute tool
            tool_result = await call_tool_async(...)
            return {"action": "continue", "result": tool_result}

    async def post_async(self, shared, prep_res, exec_res):
        # Update scratchpad and decide next step
        if exec_res["action"] == "final_answer":
            return "end"  # Terminate flow
        else:
            return "continue"  # Loop back for more reasoning
```

### 4. Inter-Agent Communication

Agents communicate via **asyncio.Queue** managed by the daemon:

```python
# From one agent to another
await daemon_client.send_message(
    from_agent="researcher",
    to_agent="assistant",
    content="Please organize these findings..."
)

# Receiving agent gets message in prep_async()
message = await self.get_message(timeout=0.1)
```

### 5. MCP Tool System

Model Context Protocol provides standardized tool integration:

```python
# Tools defined in ~/.ago/mcp_servers.yaml
servers:
  filesystem:
    command: uvx
    args: ["mcp-server-filesystem", "/Users/sky/workspace"]

  brave-search:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-brave-search"]
    env:
      BRAVE_API_KEY: ${BRAVE_API_KEY}
```

Tools are automatically:
- Discovered from MCP servers
- Formatted for LLM consumption
- Filtered by permissions (supervisor vs subagents)
- Executed with proper error handling

---

## Project Structure

```
ago/
├── pyproject.toml              # Package configuration
├── README.md                   # User-facing documentation
├── ONBOARDING.md              # This file
├── CLAUDE.md                  # AI agent instructions
│
├── ago/
│   ├── __init__.py
│   │
│   ├── cli/                   # Command-line interface
│   │   ├── main.py           # Typer CLI commands (run, chat, ps, etc.)
│   │   ├── mcp_commands.py   # MCP-specific commands
│   │   └── tui/              # Textual TUI interface
│   │       └── agent_chat.py # Chat interface
│   │
│   ├── core/                  # Core daemon & orchestration
│   │   ├── daemon.py         # Main daemon process
│   │   ├── daemon_client.py  # CLI-daemon communication
│   │   ├── config.py         # Configuration management
│   │   ├── registry.py       # Template discovery & resolution
│   │   ├── base_node.py      # Base agent node (PocketFlow)
│   │   ├── supervisor.py     # LLM service & YAML parsing
│   │   ├── mcp_integration.py # MCP tool loading & execution
│   │   ├── tool_formatter.py  # Format tools for LLM
│   │   └── agent_process/    # Agent subprocess management
│   │       ├── main.py       # Agent process entry point
│   │       └── __main__.py
│   │
│   ├── agents/                # Agent logic
│   │   ├── agent_react_flow.py        # ReAct agent factory
│   │   └── streaming_react_wrapper.py # Streaming support
│   │
│   ├── templates/             # Built-in agent templates
│   │   ├── planner.agt
│   │   ├── socratic.agt
│   │   └── tree-of-thought.agt
│   │
│   └── cookbook/              # Example workflows
│       └── two_agent_research.spec
│
└── tests/                     # Test suite (future)
```

### Key Files to Understand

1. **ago/cli/main.py**: Entry point for all CLI commands
2. **ago/core/daemon.py**: Heart of the system - manages all agents
3. **ago/agents/agent_react_flow.py**: ReAct agent implementation
4. **ago/core/base_node.py**: PocketFlow integration base class
5. **ago/core/supervisor.py**: LLM calling & response parsing

---

## Development Workflow

### 1. Making Changes

```bash
# Create a feature branch
git checkout -b feature/my-feature

# Make changes
# ... edit files ...

# Format code
black ago/

# Lint code
ruff check ago/

# Type check (optional but recommended)
mypy ago/
```

### 2. Testing Your Changes

```bash
# Start daemon in foreground for debugging
uv run ago daemon start

# In another terminal, test commands
uv run ago create researcher --name TestAgent --quick
uv run ago chat TestAgent
uv run ago ps
uv run ago stop TestAgent

# Stop daemon
uv run ago daemon stop
```

### 3. Debugging

**Enable verbose logging:**
```bash
# Set log level in code
import logging
logging.basicConfig(level=logging.DEBUG)

# Or check daemon logs
tail -f ~/.ago/logs/daemon.log
tail -f ~/.ago/logs/researcher-abc123.log
```

**Common debugging points:**
- CLI commands: `ago/cli/main.py`
- Daemon handlers: `ago/core/daemon.py::_handle_client()`
- Agent reasoning: `ago/agents/agent_react_flow.py::exec_async()`
- Tool execution: `ago/core/mcp_integration.py::call_tool_async()`

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_daemon.py

# Run with coverage
pytest --cov=ago tests/

# Run async tests
pytest -v tests/test_async_*.py
```

### Writing Tests

Example test structure:

```python
import pytest
from ago.core.daemon import AgoDaemon

@pytest.mark.asyncio
async def test_daemon_start():
    """Test daemon starts successfully"""
    daemon = AgoDaemon()

    # Test daemon initialization
    assert daemon.agents == {}

    # Test daemon start (would need mocking)
    # ...
```

---

## Contributing Guidelines

### Code Style

- **Python 3.12+** type hints everywhere
- **Black** for formatting (line length: 88)
- **Ruff** for linting
- **Docstrings** for all public functions/classes
- **Type annotations** for function signatures

Example:
```python
async def send_message(
    self,
    from_agent: str,
    to_agent: str,
    content: str
) -> Dict[str, Any]:
    """
    Send message from one agent to another.

    Args:
        from_agent: Source agent name
        to_agent: Target agent name
        content: Message content

    Returns:
        Response dict with status

    Raises:
        ValueError: If agent not found
    """
    # Implementation...
```

### Commit Messages

Follow conventional commits:
```
feat: add new command for agent inspection
fix: resolve daemon crash on empty config
docs: update onboarding guide with examples
refactor: simplify MCP tool loading
test: add tests for registry resolution
```

### Pull Request Process

1. **Fork** the repository
2. **Create** feature branch from `main`
3. **Make** changes with tests
4. **Format** and **lint** code
5. **Push** to your fork
6. **Open** PR with clear description

PR template:
```markdown
## What does this PR do?
Brief description of the change

## Why is this needed?
Explain the motivation

## How was it tested?
Describe test approach

## Screenshots (if applicable)
Add terminal output or TUI screenshots
```

---

## Common Tasks

### Adding a New CLI Command

1. **Add command to `ago/cli/main.py`:**

```python
@app.command()
def my_command(
    arg: str = typer.Argument(..., help="Description"),
    option: bool = typer.Option(False, "--flag", help="Description")
):
    """Command description for help text"""
    console.print(f"Executing command with {arg}")

    # Use daemon client for agent operations
    daemon_client = DaemonClient()
    response = asyncio.run(daemon_client.my_operation(arg))

    # Display results with Rich
    table = Table(title="Results")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")
    # ... populate table ...
    console.print(table)
```

2. **Add daemon handler in `ago/core/daemon.py`:**

```python
async def _handle_client(self, reader, writer):
    # ... existing code ...

    if command == "my_operation":
        result = await self._my_operation(data["arg"])
        response = {"status": "success", "result": result}
```

### Adding a New Agent Template

1. **Create template file `ago/templates/my-agent.agt`:**

```yaml
name: my-agent
version: "1.0"
description: "Custom agent for specific tasks"
author: "Your Name <you@email.com>"
model: claude-3-5-sonnet-20241022
temperature: 0.7
tools: [web_search, file_manager]

prompt: |
  You are a specialized agent for...

  Your capabilities include:
  - Capability 1
  - Capability 2

  Follow these guidelines:
  1. Guideline 1
  2. Guideline 2
```

2. **Test the template:**

```bash
uv run ago create my-agent --name TestMyAgent --quick
uv run ago chat TestMyAgent
```

### Adding MCP Tool Support

1. **Add server to `~/.ago/mcp_servers.yaml`:**

```yaml
servers:
  my_tool:
    command: npx
    args: ["-y", "@org/mcp-server-my-tool"]
    env:
      API_KEY: ${MY_TOOL_API_KEY}
```

2. **Tools are automatically discovered** - no code changes needed!

3. **Test tool availability:**

```bash
uv run ago mcp list
# Should show your new tool
```

### Modifying Agent Reasoning

**Edit `ago/agents/agent_react_flow.py`:**

```python
async def exec_async(self, prep_res):
    # Modify the prompt template
    prompt = f"""
    Your custom prompt structure...

    Available tools: {tools}
    Scratchpad: {scratchpad}

    Now respond...
    """

    # Call LLM
    response = await LLMService.call_llm(prompt, self.agent_name)

    # Parse response (customize YAML schema if needed)
    parsed = YAMLParser.parse(response)

    # Handle actions...
```

---

## Resources

### Official Documentation

- **PocketFlow**: https://the-pocket.github.io/PocketFlow/
- **Typer**: https://typer.tiangolo.com/
- **Textual**: https://textual.textualize.io/
- **MCP**: https://modelcontextprotocol.io/
- **FastMCP**: https://github.com/jlowin/fastmcp

### Key Guides

- [PocketFlow Agentic Coding](https://the-pocket.github.io/PocketFlow/guide.html) - Core workflow patterns
- [Typer Best Practices](https://typer.tiangolo.com/tutorial/) - CLI design
- [Textual Tutorial](https://textual.textualize.io/tutorial/) - TUI development
- [MCP Quickstart](https://modelcontextprotocol.io/quickstart/server) - Tool integration

### Python Standards

- [PEP 8](https://pep8.org/) - Style guide
- [Type Hints](https://docs.python.org/3/library/typing.html) - Type annotations
- [asyncio](https://docs.python.org/3/library/asyncio.html) - Async programming

### Project Specific

- **README.md** - User guide and features
- **ROADMAP.md** - Development priorities
- **GLOBAL_ROADMAP.md** - Strategic vision
- **CLAUDE.md** - AI agent development guide

---

## Getting Help

### Community

- **GitHub Issues**: Report bugs and request features
- **Discussions**: Ask questions and share ideas

### Troubleshooting

**Common issues:**

1. **Daemon won't start**
   - Check logs: `cat ~/.ago/logs/daemon.log`
   - Ensure port not in use: `lsof -i :50051`
   - Kill existing: `pkill -f "ago.core.daemon"`

2. **Agent not responding**
   - Check agent logs: `cat ~/.ago/logs/agent-xxx.log`
   - Verify API key: `echo $ANTHROPIC_API_KEY`
   - Check tool permissions

3. **Import errors**
   - Reinstall: `uv pip install -e ".[dev]"`
   - Clear cache: `rm -rf ~/.cache/uv`

4. **MCP tools not loading**
   - Check config: `cat ~/.ago/mcp_servers.yaml`
   - Test server: `npx @org/server --version`
   - Verify environment variables

---

## Next Steps

1. **Explore the codebase** - Start with `ago/cli/main.py` and trace commands
2. **Run examples** - Try the cookbook workflows
3. **Read PocketFlow docs** - Understand the underlying framework
4. **Make your first contribution** - Start with documentation or small fixes
5. **Join discussions** - Share ideas and ask questions

Welcome to the team! Happy coding!
