# Ago - "Docker for AI Agents"

*A minimalist CLI that creates specialized AI agents as easily as running Docker containers*

## 🎯 Current Status: v1.3 UNIX MULTI-PROCESS! 🎉

**Ago v1.3** achieves true UNIX process isolation with horizontal scaling foundation!

**🚀 MAJOR BREAKTHROUGH (v1.3 UNIX MULTI-PROCESS):**

- 🎯 **True Process Isolation** - Each agent runs in separate process (no more single-process bottleneck!)
- 🔗 **Unix Socket IPC** - Replaced in-memory communication with robust inter-process communication
- 🏷️ **Unique Instance IDs** - `researcher-abc12345`, `helper-def67890` prevent name collisions
- 📈 **Horizontal Scaling Ready** - Multiple instances of same agent type can run simultaneously
- 🛡️ **Robust Process Management** - Health checks, graceful shutdown, orphan cleanup, crash isolation
- 🧹 **No More Orphaned Processes** - Proper lifecycle management prevents resource leaks

**✅ Previous Features (v1.2 + v1.1):**

- ✅ **Multi-Registry Support** - GitHub, GitLab, and HTTP registries with token authentication
- ✅ **Enhanced .agt Template System** - Templates with embedded prompts (no external files)
- ✅ **Two-Tier Template Resolution** - Project → Global → Remote template discovery
- ✅ **Magic Create Command** - Zero-config agent creation in under 2 minutes
- ✅ **All Docker Commands** - run, ps, chat, logs, stop, daemon working flawlessly
- ✅ **Multi-Agent Communication** - Bidirectional messaging with auto-responses (now via IPC!)
- ✅ **ReAct Intelligence** - Full reasoning cycle with tool usage and memory

---

## 🌟 **Magic Create Experience**

The centerpiece of Ago - create specialized agents with **zero configuration**:

```bash
# Interactive wizard with beautiful tables
uv run ago create

# Quick creation for power users  
uv run ago create researcher --name DataMiner --quick

# Immediately start using your agent
uv run ago chat DataMiner
> "What are the latest trends in AI?"
```

### **5 Specialized Agent Types** 🤖

Each optimized with custom prompts and tools:

- 🔬 **Researcher** - Information gathering and analysis specialist
- 🤖 **Assistant** - General purpose helpful assistant  
- 📊 **Analyst** - Data analysis and insights expert
- ✍️ **Writer** - Content creation and documentation specialist
- 🎯 **Coordinator** - Project management and task orchestration

### **Complete Workflow: Creation to Conversation in 60 seconds** ⚡

```bash
# 1. Create agent (10 seconds)
uv run ago create assistant --name Helper --quick

# 2. Agent auto-loads and runs (5 seconds)
uv run ago run Helper_workflow.spec

# 3. Start chatting immediately
uv run ago chat Helper
> "Help me organize my project tasks"

# 4. Check all running agents
uv run ago ps
# 📊 Beautiful table showing all agents with status and tools
```

---

## 🏗️ **Complete Docker-like Architecture**

### **All Commands Working** ✅

```bash
# Core Docker-style Commands
uv run ago create [type] [--options]    # 🌟 Magic agent creation wizard
uv run ago run workflow.spec            # Start agents from workflow file
uv run ago run template_name agent_name # Run template directly (like docker run)
uv run ago ps                           # List running agents (like docker ps)
uv run ago chat agent_name              # Interactive chat (like docker exec -it)
uv run ago logs agent_name              # View conversation history (like docker logs)
uv run ago stop [agent_name]            # Stop specific agent or all agents

# Docker Registry Pattern
uv run ago agents                       # List all templates (registry + local .agt files)
uv run ago pull template_name           # Download/update template (like docker pull)
uv run ago up [service]                 # Start workflow (like docker-compose up)
uv run ago down                         # Stop workflow (like docker-compose down)

# Configuration Management
uv run ago config set key value [--local]  # Set global or project config
uv run ago config get [key] [--merged]     # Get config values
uv run ago registry add name url           # Add template registry

# Multi-Agent Communication
uv run ago send from_agent to_agent "msg"  # Send inter-agent messages
uv run ago queues [--follow]               # Show/monitor message queues

# Daemon Management
uv run ago daemon start/stop/status        # Daemon lifecycle management
```

### **Multi-Registry System** 🗂️

Complete template management with GitHub, GitLab & HTTP registry support:

```bash
# Add private registries with token authentication
uv run ago registry add my-github https://github.com/user/templates --type github --token $GITHUB_TOKEN
uv run ago registry add my-gitlab https://gitlab.com/user/templates --type gitlab --token $GITLAB_TOKEN

# Pull templates from private repositories  
uv run ago pull my-gitlab:test-private-template    # ✅ GitLab private repo
uv run ago pull my-github:custom-agent             # ✅ GitHub private repo

# Template discovery and usage
uv run ago agents                       # Shows ALL templates
# Built-in: researcher v1.0, assistant v1.0, analyst v1.0, writer v1.0, coordinator v1.0
# Local: my-custom-agent v1.0 (from ./my-custom-agent.agt)
# Pulled: test-private-template v1.0.0 (from GitLab private repo)

# Direct template execution from any source
uv run ago run researcher DataMiner           # ✅ Builtin template
uv run ago run my-custom-agent Bot            # ✅ Local .agt file  
uv run ago run test-private-template TestBot  # ✅ Pulled private template

# Multi-registry configuration
# ~/.ago/config.yaml OR .ago/config.yaml
registries:
  builtin:
    type: builtin
    enabled: true
    priority: 1
  my-gitlab:
    url: https://gitlab.com/user/templates
    type: gitlab
    token: glpat-xxxxxxxxxxxxx
    enabled: true
    priority: 50
  my-github:
    url: https://github.com/user/templates  
    type: github
    token: ghp_xxxxxxxxxxxxx
    enabled: true
    priority: 100

defaults:
  template_resolution_order: ["local", "builtin"]  # Configurable!
```

### **Enhanced .agt Template Format** 📄

Complete YAML-based templates with embedded prompts (no external .prompt files needed):

```yaml
# my-custom-agent.agt
name: my-custom-agent
version: "1.0.0"
description: "Custom agent for specific tasks"
author: "Developer Name <dev@company.com>"
model: claude-3-5-haiku-20241022
temperature: 0.3
tools: [file_manager, web_search]

# Embedded prompt - no external files needed
prompt: |
  You are a custom AI agent specialized in specific tasks.
  
  ## Your Capabilities
  You excel at:
  - Task-specific expertise
  - Tool usage for research and file management
  - ReAct reasoning pattern
  
  Remember: Focus on your specialized domain and use available tools effectively.

# Optional metadata for better organization
metadata:
  category: "custom"
  use_cases:
    - "Specialized task automation"
    - "Domain-specific assistance"
```

### **Production-Ready UNIX Multi-Process Architecture** 🔧

- **🎯 True Process Isolation** - Each agent runs in separate UNIX process with unique instance ID
- **🔗 Unix Socket IPC** - Fast inter-process communication between CLI, daemon, and agents
- **📈 Horizontal Scaling** - Multiple instances of same agent type (`researcher-abc123`, `researcher-def456`)
- **🛡️ Fault Tolerance** - Agent crashes don't affect other agents or daemon
- **🧹 Process Lifecycle Management** - Health checks, graceful shutdown, orphan cleanup
- **📋 Individual Logging** - Separate log files per instance (`~/.ago/logs/researcher-abc123.log`)
- **💾 Persistent Agent State** - Agents and conversations survive CLI restarts
- **🤖 ReAct Intelligence** - Full reasoning cycle (Thought→Action→Observation→Answer) in isolation
- **🔧 Tool Integration** - MCP tools with proper permissions per process
- **💬 IPC Communication** - Inter-agent messaging through daemon coordination

### **UNIX Process Architecture (v1.3)**

```bash
# Process tree showing true isolation
$ ps aux | grep ago
daemon-76308     python -m ago.core                    # Main daemon
researcher-a1b2  python -m ago.core.agent_process {...} # Agent instance 1  
researcher-c3d4  python -m ago.core.agent_process {...} # Agent instance 2
helper-e5f6      python -m ago.core.agent_process {...} # Helper instance

# Each agent gets unique instance ID and isolated resources
$ ls ~/.ago/
├── logs/
│   ├── daemon.log              # Daemon process logs
│   ├── researcher-a1b2c3d4.log # Individual agent logs
│   ├── researcher-c3d4e5f6.log
│   └── helper-e5f6g7h8.log
├── processes/
│   ├── researcher-a1b2c3d4.sock # Unix socket per instance
│   ├── researcher-c3d4e5f6.sock
│   └── helper-e5f6g7h8.sock
└── daemon.sock                 # Main daemon socket
```

**Benefits Achieved:**

- 🛡️ **Crash Isolation**: One agent crash doesn't affect others
- 📈 **Horizontal Scaling**: Multiple instances of same agent type  
- 🧹 **Resource Management**: Proper cleanup prevents memory leaks
- 📋 **Individual Monitoring**: Per-instance logs and health checks

---

## 🎉 **What This Achieves: "Docker for AI" Vision Realized**

Ago successfully delivers the complete "Docker for AI" vision:

1. ✅ **Declarative deployment** - Agents defined in YAML specs
2. ✅ **Background operation** - Persistent agents managed by daemon
3. ✅ **Familiar tooling** - Docker-like commands and workflows
4. ✅ **Resource isolation** - Each agent is independent  
5. ✅ **Tool ecosystem** - Shared MCP tool mesh across agents
6. ✅ **Developer experience** - Simple, intuitive interface
7. ✅ **Multi-agent orchestration** - AsyncIO queue-based communication
8. ✅ **Live monitoring** - Real-time message flow visualization
9. ✅ **Individual lifecycle** - Docker-compose style agent management
10. ✅ **🌟 Magic creation** - Zero-config agent generation in under 2 minutes

---

## 📦 **Why Ago vs ChatGPT?**

| Feature | ChatGPT | Ago |
|---------|---------|---------|
| **Specialization** | Generic responses | Role-specific expertise |
| **Memory** | Conversation only | Persistent across sessions |
| **Agent Collaboration** | None | Bidirectional agent-to-agent communication |
| **Reasoning** | Hidden process | Full ReAct pattern visible |
| **Tools** | Limited web access | Extensible tool system |
| **Control** | Cloud-dependent | Local control |
| **Customization** | Limited | Fully customizable |
| **Creation Time** | Manual setup | Magic command in 60 seconds |

---

## 🧪 **Proven End-to-End Testing**

All workflows verified working:

### **Magic Create Command** ✅

```bash
cd /Users/sky/git/CodeSwarm/pocket/ago/vision

# Interactive creation wizard
uv run ago create
# ✅ Beautiful table with 5 agent types, model selection, tool configuration

# Quick creation  
uv run ago create assistant --name TestAgent --quick
# ✅ Agent created in 10 seconds with progress indicators
```

### **Complete Docker Workflow** ✅

```bash
# 1. Create agent
uv run ago create assistant --name MyHelper --quick

# 2. Run agent  
uv run ago run MyHelper_workflow.spec

# 3. List running agents
uv run ago ps

# 4. Chat with agent
uv run ago chat MyHelper

# 5. View logs
uv run ago logs MyHelper

# 6. Graceful shutdown
uv run ago daemon stop
```

### **Multi-Agent Communication** ✅

```bash
# Create multiple agents
uv run ago create researcher --name DataMiner --quick
uv run ago create assistant --name Helper --quick

# Load both agents  
uv run ago run DataMiner_workflow.spec
uv run ago run Helper_workflow.spec

# Send inter-agent message with auto-response
uv run ago send DataMiner Helper "Can you help organize my findings?"

# Monitor live message flow
uv run ago queues --follow
```

---

## 📁 **File Structure**

```
ago/vision/
├── pyproject.toml              # Pip installable package
├── README.md                   # This comprehensive guide
├── ROADMAP.md                  # Development roadmap and priorities
├── GLOBAL_ROADMAP.md           # High-level strategic direction
│
├── ago/
│   ├── cli/main.py            # 🌟 Main CLI with magic create (400+ lines)
│   ├── core/
│   │   ├── daemon.py          # Background daemon with PocketFlow agents
│   │   ├── daemon_client.py   # CLI-daemon communication
│   │   ├── config.py          # Configuration management system
│   │   ├── registry.py        # Template discovery and resolution
│   │   └── mcp_integration.py # Tool system integration
│   ├── agents/
│   │   └── agent_react_flow.py # PocketFlow ReAct agent factory
│   ├── templates/             # 5 specialized agent templates
│   │   ├── researcher_agent.prompt
│   │   ├── assistant_agent.prompt
│   │   ├── analyst_agent.prompt
│   │   ├── writer_agent.prompt
│   │   └── coordinator_agent.prompt
│   └── cookbook/
│       └── two_agent_research.spec # Multi-agent example
│
├── .ago/                   # Project configuration
│   ├── config.yaml            # Project-specific config
│   └── auth.env               # Authentication (git-ignored)
│
└── my-test-agent.agt           # Example local template
```

---

## 🚀 **Installation & Quick Start**

### Installation

```bash
# Install from source (PyPI coming soon)
cd /Users/sky/git/CodeSwarm/pocket/ago/vision
uv pip install -e .

# Or use directly with uv
uv run ago --help
```

### Quick Start

```bash
# 1. Create your first agent (interactive wizard)
uv run ago create

# 2. Or create quickly
uv run ago create assistant --name MyHelper --quick

# 3. Start chatting
uv run ago chat MyHelper

# 4. Check running agents  
uv run ago ps

# 5. Send messages between agents
uv run ago create researcher --name DataMiner --quick
uv run ago send MyHelper DataMiner "Please research AI trends for me"

# 6. Monitor communication
uv run ago queues --follow
```

---

## 🎯 **Use Cases**

### **For Developers**

- **Code Review Assistant** - Agent that knows your coding standards
- **Documentation Writer** - Understands your project structure  
- **Research Assistant** - Tracks technical decisions and references

### **For Researchers**

- **Literature Review** - Agent specialized in academic paper analysis
- **Data Analyst** - Focused on statistical analysis and visualization
- **Grant Writer** - Knows funding agency requirements

### **For Content Creators**

- **SEO Specialist** - Optimizes content for search engines
- **Social Media Manager** - Adapts content for different platforms
- **Editor** - Maintains consistent voice and style

### **Multi-Agent Collaboration**

- **Research Teams** - Coordinator delegates tasks to specialist agents
- **Content Pipeline** - Writer collaborates with editor in rapid iteration
- **Development Teams** - Code reviewer works with documentation agent

---

## 🎉 **Mission Accomplished!**

**Ago v1.1 delivers the complete "Docker for AI" vision:**

✅ **Magic Create Command** - Zero-config agent creation in under 2 minutes  
✅ **Full Docker Experience** - All commands working flawlessly  
✅ **Production Ready** - Pip installable with proper daemon architecture  
✅ **Intelligent Agents** - ReAct reasoning with tool usage and memory  
✅ **Multi-Agent Communication** - Bidirectional collaboration system  
✅ **Registry System** - Docker-like template management with .agt discovery
✅ **End-to-End Workflow** - From creation to conversation in 60 seconds

**Ago makes specialized AI agents as easy as running Docker containers, with the magical experience of creating them through an interactive wizard!** 🚀

---

*For detailed development roadmap, see [ROADMAP.md](ROADMAP.md)*  
*For high-level strategic direction, see [GLOBAL_ROADMAP.md](GLOBAL_ROADMAP.md)*

*Last Updated: August 19, 2025*

