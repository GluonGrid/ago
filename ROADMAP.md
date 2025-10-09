# Ago Development Roadmap

*Detailed technical implementation plan and priorities*

## 🎯 **Current Status: v1.2 COMPLETE**

Ago has successfully implemented multi-registry support with full GitHub & GitLab integration!

### **✅ v1.0 COMPLETE - Magic Create Command + Full Docker Experience**

- ✅ **Interactive Agent Creation Wizard** - Beautiful terminal interface with 5 specialized agent types
- ✅ **All Docker Commands Working** - run, ps, chat, logs, stop, daemon with full functionality
- ✅ **Background Daemon Process** - Unix socket communication, persistent state, graceful shutdown
- ✅ **ReAct Intelligence System** - Complete reasoning cycle (Thought→Action→Observation→Answer)
- ✅ **Bidirectional Inter-Agent Communication** - AsyncIO queue-based messaging with auto-responses
- ✅ **Production Package** - Pip installable with proper entry points and dependencies
- ✅ **End-to-End Workflow** - From agent creation to conversation in under 60 seconds

### **✅ v1.1 COMPLETE - Docker Registry Pattern Implementation**

- ✅ **Template Auto-Discovery** - `.agt` files discovered automatically from configured paths
- ✅ **Configuration System** - Global (`~/.ago/config.yaml`) + project (`.ago/config.yaml`) hierarchy
- ✅ **Registry Management** - CLI commands for adding, listing, removing template registries
- ✅ **Template Resolution** - Configurable resolution order (local → builtin → remote)
- ✅ **Docker-like Commands** - `up/down` for workflows, `run template name` for direct execution
- ✅ **All Integration Working** - Registry templates work in daemon, chat, and workflow systems

### **✅ v1.2 COMPLETE - Multi-Registry Support**

- ✅ **GitHub Registry Integration** - Private repository support with token authentication
- ✅ **GitLab Registry Integration** - Full API support with project ID resolution and proper encoding
- ✅ **HTTP Registry Support** - Generic HTTP endpoint support for public repositories
- ✅ **Template Pull System** - `ago pull registry:template` downloads to global cache
- ✅ **Registry Configuration** - Multiple registry types (github, gitlab, http) with priorities
- ✅ **End-to-End Testing** - Successfully pulled and used templates from GitLab private repositories
- ✅ **Embedded Prompt Migration** - Removed all `.prompt` file dependencies, everything in `.agt` files

---

## ✅ **v1.3 COMPLETE - UNIX Multi-Process Architecture + Message Formatting Fixes**

**MAJOR MILESTONE ACHIEVED!** 🎉 Ago now has true process isolation, scalability, and clean inter-agent communication!

### **✅ 1. UNIX Multi-Process Architecture** 🏗️

**Problem**: ~~Current architecture runs all agents in single daemon process, limiting scalability and reliability.~~ **SOLVED!**

**Solution**: ✅ **IMPLEMENTED** - Proper UNIX process isolation with IPC communication.

#### **✅ COMPLETED Implementation**

1. **✅ Process Architecture Design**
   - ✅ Individual agent processes spawned by daemon (`ProcessManager`)
   - ✅ Parent daemon manages child agent processes with unique instance IDs
   - ✅ IPC communication via Unix sockets
   - ✅ Complete process lifecycle management (start, stop, restart, health checks)

2. **✅ Agent Process Structure**

   ```
   Daemon Process v2 (Parent) - PID: 76308
   ├── ResearchAgent-abc12345 Process (Child) - PID: 78901
   ├── HelperAgent-def67890 Process (Child) - PID: 78902
   └── CoordinatorAgent-ghi34567 Process (Child) - PID: 78903
   ```

3. **✅ Communication Layer**
   - ✅ Replaced in-memory communication with Unix socket IPC
   - ✅ JSON message passing between daemon and agent processes
   - ✅ Inter-agent communication through daemon coordination
   - ✅ Preserved bidirectional messaging and auto-responses

4. **✅ State Management**
   - ✅ Agent conversation history isolated per process
   - ✅ Individual log files per instance (`~/.ago/logs/ResearchAgent-abc12345.log`)
   - ✅ Separate socket files per instance (`~/.ago/processes/ResearchAgent-abc12345.sock`)

5. **✅ Error Handling & Recovery**
   - ✅ Agent process crash detection via health checks
   - ✅ Graceful shutdown with SIGTERM → forceful termination fallback
   - ✅ Orphaned process cleanup and registry management
   - ✅ Socket cleanup on process termination

6. **✅ Instance ID System** (MAJOR ENHANCEMENT)
   - ✅ Unique instance IDs prevent duplicate name collisions (`researcher-abc12345`)
   - ✅ Support for multiple instances of same agent type (horizontal scaling ready)
   - ✅ Process registry tracks both instance IDs and agent types
   - ✅ CLI commands work with both instance IDs and agent type names

**✅ ACHIEVED Benefits**:

- ✅ **True process isolation** - Agent failures don't affect other agents ✓ TESTED
- ✅ **Better resource management** - Memory and CPU isolation per agent ✓ VERIFIED  
- ✅ **Improved reliability** - Individual agent crashes don't crash daemon ✓ CONFIRMED
- ✅ **Scalability foundation** - Ready for horizontal scaling and distributed deployment ✓ READY
- ✅ **No more orphaned processes** - Proper cleanup prevents resource leaks ✓ SOLVED

### **✅ 2. Inter-Agent Communication Fixes** 🔧

**Problem**: ~~Agent communication was breaking due to JSON parsing errors and agents rejecting multi-agent scenarios as "role-play".~~ **SOLVED!**

**Solution**: ✅ **IMPLEMENTED** - Clean message formatting and msgpack communication protocol.

#### **✅ COMPLETED Fixes**

1. **✅ JSON Parsing Issues Fixed**
   - ✅ Replaced JSON with msgpack for binary-safe large message handling
   - ✅ Updated all IPC communication (daemon ↔ agents) to use msgpack
   - ✅ Fixed buffer size issues that caused "Unterminated string" errors
   - ✅ Proper 64KB buffer handling for large agent responses

2. **✅ Message Format Cleaning**
   - ✅ Removed complex nested JSON objects from inter-agent messages
   - ✅ Agents now receive clean, natural text messages instead of metadata-heavy objects
   - ✅ Fixed message prefixes (removed confusing `[Response]: {complex_object}`)
   - ✅ Messages now look like: `"Hello, can you help me organize some data?"` instead of structured objects

3. **✅ Agent Identity Confusion Fixed**
   - ✅ Fixed agents using `self.agent_name` instead of `self.instance_id` in responses
   - ✅ Agents now properly identify themselves with unique instance IDs
   - ✅ Prevents message routing failures between agent instances

4. **✅ Conversation History Enhancement**
   - ✅ Added outgoing inter-agent messages to sender's conversation history as assistant messages
   - ✅ Agents now have context of what they've sent to other agents
   - ✅ Prevents confusion about previous statements in multi-turn conversations

5. **✅ Template System Reorganization**
   - ✅ Reorganized template structure: `registry/templates/builtin/` and `registry/templates/pulled/`
   - ✅ Updated registry to create `.agt` files instead of separate `template.yaml` + `prompt.txt`
   - ✅ Updated template pulling to save to `registry/templates/pulled/` directory
   - ✅ Maintains auto-discovery from current working directory (pwd)

**✅ ACHIEVED Benefits**:

- ✅ **Clean Inter-Agent Communication** - Agents receive natural messages, not metadata objects ✓ IMPLEMENTED
- ✅ **No More JSON Parsing Errors** - msgpack handles large messages without "unterminated string" issues ✓ SOLVED  
- ✅ **Proper Agent Identity** - Unique instance IDs prevent message routing confusion ✓ FIXED
- ✅ **Better Conversation Context** - Agents remember their own outgoing messages ✓ ENHANCED
- ✅ **Organized Template Structure** - Clear separation of built-in vs pulled templates ✓ REORGANIZED

**⏳ v1.5 PRIORITIES - Template System Architecture Refactoring:**

**Template System Simplification (High Priority):**

- ⏳ **Remove Version Complexity** - Simplify template system by removing version handling:
  - Fix `rm` command to work without version matching (currently fails with `latest` vs `1.0.0`)
  - Remove version logic from template discovery and loading
  - Keep version field in YAML as purely informational for users
  - Templates treated as simple config files, not versioned artifacts
- ⏳ **Simple Template Management Commands**:
  - `ago template list` - Rename current `ago templates` command for consistency
  - `ago template copy <template_name> [destination]` - Copy template .agt file to current directory
  - `ago template edit <template_name>` - Open template in editor (create local copy if needed)
- ⏳ **Template Discovery Issues**:
  - **Remove Hardcoded Templates** - Built-in templates should not be hardcoded in package initialization
  - **Official Repository Integration** - Builtin templates should be pulled from official ago GitHub repository
  - **Fix Local Discovery** - "Local" should mean current working directory, not machine-wide paths
  - **Template Auto-Discovery** - Ensure pulled templates are discovered properly by templates command
  - **Discovery Path Configuration** - Fix `get_local_discovery_paths()` to search correct locations:
    - `./` - Current working directory (user custom templates)
    - `~/.ago/registry/templates/builtin/` - Official ago templates
    - `~/.ago/registry/templates/pulled/` - User-pulled templates

**Architecture Decisions Captured:**
- **Builtin Templates**: Should be pulled from ago/templates GitHub repo, not embedded in package
- **Local Templates**: User's custom templates in current working directory only
- **Pulled Templates**: Templates from any remote registry saved to global cache
- **Discovery**: All three locations should be auto-discovered by all commands

**Additional UX Improvements:**

- ⏳ **Config View Command** - Add `ago config show` subcommand to view current configuration
- ⏳ **User-Friendly Agent Names** - Remove instance IDs from CLI, use `agent-name-N` format for duplicates
- ⏳ **Registry Management** - Add priority/status editing for registries

**Testing & Validation:**

- ⏳ **Full Communication Testing** - End-to-end inter-agent communication with proper system prompts
- ⏳ **Queues Command** - Test `queues --follow` functionality for real-time monitoring

### **2. Enhanced Prompt Architecture** 🧩

**Problem**: Current prompts are monolithic blocks, making it hard to dynamically inject tool info, agent awareness, and structured output patterns.

**Solution**: Implement modular prompt composition with prefix + custom + suffix architecture.

#### **Prompt Structure Design**

```yaml
# Template prompt structure
prompt_structure:
  prefix:    # System initialization and role definition
  custom:    # Template-specific instructions with variable injection
  suffix:    # ReAct pattern and output formatting requirements
```

#### **Implementation Plan**

1. **Prefix Component** - System-level initialization
   - Agent role and identity establishment
   - Universal behavioral guidelines
   - Security and safety instructions
   - Inter-agent communication protocols

2. **Custom Component** - Template-specific with variable injection
   - **Tool Awareness**: Dynamically inject available tool descriptions
   - **Agent Awareness**: List other agents and their capabilities for collaboration
   - **Task-Specific Instructions**: Core template functionality
   - **Domain Expertise**: Specialized knowledge and approaches

3. **Suffix Component** - Structured output and ReAct formatting
   - ReAct reasoning pattern requirements (Thought→Action→Observation→Answer)
   - YAML output format specifications
   - Tool usage syntax and conventions
   - Inter-agent message formatting

4. **Template Variable System**:

   ```yaml
   # Enhanced .agt template format
   prompt_variables:
     available_tools: "{{AVAILABLE_TOOLS}}"      # Auto-injected tool list
     agent_network: "{{AGENT_NETWORK}}"          # Other agents in system
     task_context: "{{TASK_CONTEXT}}"            # Current task information
   
   prompt_custom: |
     You specialize in {{domain}} with access to:
     
     ## Available Tools
     {{AVAILABLE_TOOLS}}
     
     ## Agent Network  
     {{AGENT_NETWORK}}
     
     ## Your Specialized Approach
     {{template_specific_instructions}}
   ```

5. **Dynamic Prompt Assembly**
   - Runtime composition of prefix + custom + suffix
   - Variable substitution with current system state
   - Tool and agent discovery for injection
   - Context-aware prompt optimization

**Benefits**:

- ✅ **Modular Design** - Reusable prompt components across templates
- ✅ **Dynamic Tool Integration** - Automatically inform agents of available tools
- ✅ **Agent Collaboration** - Built-in awareness of other agents
- ✅ **Consistent Output Format** - Standardized ReAct and YAML patterns
- ✅ **Template Maintainability** - Easier to update and extend prompts
- ✅ **Context Adaptation** - Prompts adapt to current system configuration

### **3. GitHub Registry Integration** 🌐

**Current**: Built-in and local template registries only
**Target**: Full GitHub repository integration with authentication

#### **Implementation Steps**

1. **GitHub API Integration**
   - Implement GitHub API calls in `registry.py`
   - Repository browsing and template discovery
   - Branch/tag support for versioned templates
   - Rate limiting and error handling

2. **Authentication System**
   - Personal Access Token support
   - Token storage in config system
   - Secure credential management
   - Environment variable fallbacks

3. **Template Downloading**
   - GitHub repository cloning/fetching
   - Template caching and versioning
   - Dependency resolution for template requirements
   - Update mechanisms and conflict resolution

4. **CLI Commands Enhancement**

   ```bash
   # GitHub registry management
   uv run ago registry add github-repo https://github.com/user/repo --type github --token xxx
   uv run ago pull github-repo/template-name
   uv run ago pull user/repo/template-name:v1.0
   
   # Template publishing (future)
   uv run ago push my-template github-repo
   ```

### **4. Tool Reliability Fixes** 🔧

**Current**: MCP tool execution sometimes hangs or fails
**Target**: Robust, reliable tool execution with proper error handling

#### **Critical Issues to Fix**

1. **MCP Tool Execution Hanging**
   - Debug tool call timeouts and hanging issues
   - Implement proper async/await handling for tool calls
   - Add tool execution timeouts and cancellation
   - Improve MCP server connection reliability

2. **Error Handling Enhancement**
   - Comprehensive error handling for tool failures
   - Retry mechanisms with exponential backoff
   - Graceful degradation when tools are unavailable
   - User-friendly error messages and suggestions

3. **Tool Integration Testing**
   - Comprehensive test suite for all MCP tools
   - Integration tests for tool chains and workflows
   - Performance testing and optimization
   - Tool compatibility verification

### **5. Built-in Template Creator Agent** 🤖➡️🤖

**Vision**: Built-in agent that helps users create custom templates through guided conversation and validation.

#### **Implementation Plan**

1. **Built-in Template Creator** (`template-creator.agt`)
   - Add to the 5 built-in templates: researcher, assistant, analyst, writer, coordinator, **template-creator**
   - Specialized in template creation workflow and .agt format expertise
   - Interactive template design through conversational interface
   - Template validation and best practices guidance

2. **Custom Tool: `validate_template`**

   ```yaml
   # Custom MCP tool for template validation
   validate_template:
     description: "Validates .agt template files for correctness and completeness"
     parameters:
       - template_content: "YAML content of the template file"
       - validation_level: "basic|strict|comprehensive" 
     returns:
       - is_valid: boolean
       - errors: list of validation errors
       - warnings: list of recommendations
       - suggestions: improvement suggestions
   ```

3. **Template Creation Workflow**

   ```bash
   # Start template creation session
   uv run ago create template-creator --name TemplateHelper --quick
   uv run ago chat TemplateHelper
   
   # Interactive conversation flow:
   > "I want to create a legal contract review agent"
   
   # TemplateHelper guides through:
   # 1. Domain expertise requirements
   # 2. Tool selection and justification  
   # 3. Model recommendation based on task complexity
   # 4. Prompt structure design with prefix/custom/suffix
   # 5. Template validation using validate_template tool
   # 6. File generation and saving to local/global templates
   ```

4. **Template Creator Capabilities**
   - **Domain Analysis**: Ask clarifying questions about the agent's purpose
   - **Tool Recommendation**: Suggest appropriate tools based on requirements
   - **Model Selection**: Recommend optimal model based on task complexity and cost
   - **Prompt Engineering**: Guide user through effective prompt design
   - **Template Validation**: Use `validate_template` tool to ensure correctness
   - **File Generation**: Create properly formatted .agt files
   - **Testing Guidance**: Suggest testing approaches for the new template

5. **Conversational Template Creation Flow**:

   ```yaml
   # Example interaction flow
   TemplateHelper: "What type of agent would you like to create?"
   User: "A legal contract review agent that flags risky clauses"
   
   TemplateHelper: "Excellent! Let me ask some questions to design the perfect template:
   
   1. What types of contracts will it review? (employment, vendor, NDA, etc.)
   2. What specific risks should it identify? 
   3. Do you need it to suggest alternative language?
   4. Should it integrate with document storage systems?"
   
   # After gathering requirements:
   TemplateHelper: "Based on your needs, I recommend:
   - Model: claude-3-5-sonnet (better for legal reasoning)
   - Tools: file_manager, web_search, legal_database
   - Template structure: specialist + domain expertise + risk assessment
   
   Let me generate the template and validate it..."
   
   # Uses validate_template tool, then generates final .agt file
   ```

6. **Enhanced Built-in Templates List**:
   - 🔬 **researcher** - Information gathering and analysis
   - 🤖 **assistant** - General purpose helper
   - 📊 **analyst** - Data analysis and insights  
   - ✍️ **writer** - Content creation and documentation
   - 🎯 **coordinator** - Project management and orchestration
   - 🏗️ **template-creator** - Interactive template design and validation

**Benefits**:

- ✅ **Self-Improving System** - Ago can help users create better agents
- ✅ **Guided Template Creation** - No need to learn .agt format manually
- ✅ **Best Practices Integration** - Built-in template validation and recommendations
- ✅ **Conversational UX** - Natural language template specification
- ✅ **Quality Assurance** - Validation tool ensures template correctness
- ✅ **Rapid Prototyping** - Quick iteration on template designs

---

## 🔄 **v1.4 NEXT - Template System Completion + Enhanced Features**

**Priority**: HIGH - Complete the template system and test full inter-agent communication

### **Next Development Priorities**

1. **✅ Multi-Process Architecture** - COMPLETED v1.3
2. **✅ Inter-Agent Communication Fixes** - COMPLETED v1.3 (msgpack, clean formatting, conversation history)
3. **✅ Template System Completion** - COMPLETED v1.4
   - ✅ Organized structure (`builtin/`, `pulled/`)
   - ✅ Updated pulling to correct directory
   - ✅ Converted to `.agt` format  
   - ✅ **FIXED**: Template loading working correctly - rich prompts loading properly
   - ✅ Inter-agent communication tested with proper researcher/writer system prompts
4. **✅ Performance & Reliability Fixes** - COMPLETED v1.4
   - ✅ **FIXED**: Send command performance - implemented fire-and-forget (returns immediately)
   - ✅ **IMPROVED**: Background message delivery using asyncio.create_task()
   - ✅ Message queues working properly for async communication
5. **✅ User Experience Improvements** - COMPLETED v1.4
   - ✅ **DOCKER-LIKE COMMANDS**: Complete refactor to Docker-style interface
     - `ago run researcher` → runs agent from template (like `docker run nginx`)
     - `ago run researcher --name my-researcher` → runs named agent
     - `ago create` only saves configs (no auto-run, like `docker build`)
     - `ago up workflow.spec` → runs multi-agent workflows (like `docker-compose up`)
   - ✅ **AGENT NAME RESOLUTION**: Simple names work in all commands
     - `ago chat researcher` works instead of requiring full instance ID
     - `ago logs my-agent`, `ago stop my-agent`, `ago send from to` all support simple names
   - ✅ **AUTO-PULL FRAMEWORK**: Template not found detection with helpful guidance
6. **⏳ Full System Testing** - PENDING
   - Test complete workflows with rich system prompts
   - Verify agents understand their roles (researcher vs assistant specialization)
   - Test `queues --follow` for real-time monitoring
7. **⏳ Agent-to-Agent Role Mapping** - FUTURE (ADK-inspired role handling)
8. **⏳ Enhanced Prompt Architecture** - FUTURE (prefix/custom/suffix system)
9. **⏳ Built-in Template Creator Agent** - FUTURE (6th template with validation)

---

## 🎭 **Agent-to-Agent Role Mapping Architecture** 

**Inspiration**: Analysis of Google's Agent Development Kit (ADK) reveals sophisticated role mapping patterns for LLM compatibility.

### **The Challenge**

Current AI agents communicate using ad-hoc role systems (e.g., "agent" role in A2A protocol), but LLMs only support standard roles:
- `user` - Human or external input
- `assistant` - AI agent responses  
- `system` - Configuration and context

**Problem**: How do agents maintain context about who they're talking to while staying LLM-compatible?

### **ADK's Solution**

Google ADK solves this through **role mapping with context preservation**:

```python
# A2A Protocol Level (agent-to-agent)
{
  "role": "agent",
  "content": "Research AI trends",
  "sender": "CoordinatorAgent"
}

# LLM Level (after mapping)
{
  "role": "user",  # ← Mapped for compatibility
  "content": "Message from CoordinatorAgent: Research AI trends"
}
```

### **Implementation Strategy for Ago**

#### **1. Role Mapping Function**
```python
def map_agent_message_for_llm(message, receiving_agent_context):
    if message.sender_type == "agent":
        return {
            "role": "user",
            "content": f"Message from {message.sender}: {message.content}"
        }
    elif message.sender_type == "human":
        return {
            "role": "user", 
            "content": message.content
        }
```

#### **2. Context Preservation Techniques**
- **System Message Updates**: "You are ResearchAgent. You're collaborating with WriterAgent."
- **Content Enrichment**: Prefix messages with sender context
- **Session State**: Track conversation mode (human-to-agent vs agent-to-agent)

#### **3. Agent Identity Awareness**
Agents should understand:
- Who they are (their role and capabilities)
- Who they're talking to (human vs specific agent type)
- Conversation context (task delegation vs collaboration)

### **Benefits for Ago**

1. **LLM Compatibility**: Works with Claude, GPT-4, Gemini, etc.
2. **Rich Context**: Agents understand collaboration dynamics
3. **Clean Architecture**: Separate protocol layer from LLM layer
4. **Future-Proof**: Compatible with any LLM provider

### **Development Priority**

- **v1.4 Research**: Prototype role mapping system
- **v1.5 Implementation**: Full agent-to-agent context preservation
- **v2.0 Advanced**: Dynamic role negotiation and collaboration patterns

---

## 🎯 **v1.5 PLANNED - Advanced Agent Reasoning + TUI Interface**

### **Priority: Transform Agent Interactions and Reasoning Capabilities**

**Inspired by**: Toad TUI (Will McGugan) and Claude-Flow architecture patterns

### **1. Toad-Inspired Terminal User Interface (TUI)** 🖥️

**Vision**: Professional, flicker-free terminal interface for agent interaction

#### **Phase 1: Enhanced Chat Command**
```bash
ago chat <agent>  # Launch Textual TUI instead of simple CLI
```

**TUI Features**:
- **Split-screen Layout**: Conversation + Agent thinking process
- **Real-time Updates**: Live ReAct reasoning display (Thought→Action→Observation)
- **Text Selection**: Copy agent responses and reasoning
- **Smooth Scrolling**: Navigate long conversations effortlessly
- **Delegation Tracking**: Visual display of task delegations between agents
- **Tool Usage Display**: Real-time tool execution monitoring

**Technical Implementation**:
```python
# ago/cli/tui/agent_chat.py
from textual.app import App
from textual.widgets import Input, RichLog, Static
from textual.containers import Horizontal, Vertical

class AgoChatApp(App):
    """Toad-inspired chat interface with live agent reasoning"""
    
    def compose(self):
        yield Vertical(
            Static(f"🤖 Ago Chat - {self.agent_name}", id="header"),
            Horizontal(
                RichLog(id="conversation", auto_scroll=True),    # Main chat
                RichLog(id="agent-thinking", auto_scroll=True),  # ReAct process
                id="main-split"
            ),
            Input(placeholder="Message...", id="input"),
            id="chat-container"
        )
```

#### **Phase 2: Dashboard Command**
```bash
ago dashboard  # Launch comprehensive system TUI
```

**Dashboard Features**:
- **Agent Status Panel**: Running agents with health indicators
- **Message Flow Visualization**: Inter-agent communication in real-time
- **System Logs**: Filterable log viewer with search
- **Performance Metrics**: Resource usage and message rates
- **Quick Actions**: Start/stop agents, send messages directly

### **2. Specialized Reasoning Agent Templates** 🧠

**Inspired by**: Claude-Flow's swarm intelligence and specialized agent types

#### **New Built-in Templates**:

1. **🗂️ planner.agt** - Strategic Planning Specialist
   - Breaks complex problems into structured, actionable steps
   - Identifies dependencies and potential blockers
   - Creates detailed project plans with validation

2. **🤔 socratic.agt** - Critical Thinking Specialist  
   - Challenges assumptions through probing questions
   - Explores alternative perspectives and edge cases
   - Deepens understanding before action

3. **🌳 tree-of-thought.agt** - Multi-Path Reasoning Specialist
   - Explores multiple solution approaches simultaneously
   - Evaluates different strategies and trade-offs
   - Recommends optimal paths based on analysis

#### **Enhanced Delegation System**:
Current agents can now delegate to reasoning specialists:

```yaml
action: delegate_task
action_input:
  task_description: "Create a comprehensive market analysis plan"
  target_agent: "planner"
  wait_for_response: true
```

**Delegation Benefits**:
- ✅ **Specialized Expertise**: Each reasoning agent optimized for its domain
- ✅ **Composable Intelligence**: Combine different reasoning approaches
- ✅ **Visible Process**: See reasoning agents' internal thinking
- ✅ **Flexible Routing**: Choose appropriate reasoning approach per task

### **3. WebSocket Communication Foundation** 🌐

**Vision**: Prepare for distributed agents while enhancing current system

#### **Phase 1: WebSocket Hub (Foundation)**
```python
# ago/core/websocket_hub.py
class AgentWebSocketHub:
    """Central WebSocket coordination for agents"""
    
    def __init__(self):
        self.agents = {}          # agent_id -> websocket
        self.message_history = [] # Persistent message log
        self.tui_connections = {} # TUI clients for real-time updates
        
    async def route_message(self, from_agent: str, to_agent: str, message: dict):
        """Route messages between agents with TUI updates"""
        
    async def broadcast_to_tui(self, event: dict):
        """Send real-time updates to TUI interfaces"""
```

#### **Phase 2: Persistent Storage (SQLite)**
**Inspired by**: Claude-Flow's sophisticated memory architecture

```python
# ago/storage/sqlite_storage.py  
class AgentMemoryDB:
    """Persistent storage for agent interactions and learning"""
    
    tables = {
        "conversations": "agent interactions and history",
        "delegations": "task delegation patterns and success rates", 
        "reasoning_sessions": "agent thinking processes and outcomes",
        "agent_performance": "metrics and learning data",
        "workflows": "multi-agent workflow definitions",
        "templates": "agent template usage and effectiveness"
    }
```

### **4. Web-Based Workflow Builder** 🎨

**Vision**: Visual workflow design with React Flow

#### **Future Web Commands**:
```bash
ago web <agent>      # Web chat interface for specific agent
ago dashboard --web  # Web-based system dashboard  
ago builder          # Visual workflow builder
```

**Builder Features** (React Flow):
- **Drag-and-Drop**: Agent nodes with visual connections
- **Delegation Flows**: Draw task routing between agents
- **Parameter Configuration**: Visual agent setup
- **Spec Export**: Generate .spec files from visual designs
- **Template Gallery**: Browse and customize pre-built workflows

### **5. Implementation Timeline**

#### **Week 1-2: TUI Foundation**
- ✅ Install and configure Textual
- ✅ Create basic AgoChatApp with split-screen layout
- ✅ Integrate with current agent communication
- ✅ Add real-time ReAct process display

#### **Week 3: Reasoning Agent Templates**  
- ✅ Implement planner.agt, socratic.agt, tree-of-thought.agt
- ✅ Enhance delegation routing to reasoning agents
- ✅ Test delegation workflows with specialized reasoning

#### **Week 4: WebSocket Foundation**
- ✅ Implement basic WebSocket hub for agent communication
- ✅ Add TUI real-time updates via WebSocket
- ✅ Begin SQLite storage design for persistent memory

#### **Week 5-6: Dashboard TUI**
- ✅ Create comprehensive dashboard with agent status
- ✅ Add message flow visualization
- ✅ Implement system monitoring and metrics

#### **Week 7-8: Web UI Foundation**
- ✅ FastAPI backend with WebSocket support
- ✅ Basic React frontend for chat interface
- ✅ Web-based agent dashboard prototype

### **6. Technical Architecture Evolution**

#### **Current (v1.4)**:
```
CLI → Daemon → Agent Process → ReAct → Response
```

#### **Target (v1.5)**:
```
Textual TUI ↗
CLI --------→ WebSocket Hub → Agent Process → ReAct → SQLite
Web UI -----↗                     ↓
                            Reasoning Agents
```

### **Benefits of This Approach**:

✅ **Professional UX**: Toad-inspired TUI eliminates terminal jank  
✅ **Specialized Intelligence**: Reasoning agents enhance problem-solving  
✅ **Real-time Visibility**: Watch agents think and collaborate  
✅ **Future-Proof Architecture**: WebSocket foundation for distributed agents  
✅ **Persistent Learning**: SQLite storage for agent memory and improvement  
✅ **Visual Workflow Design**: Web-based builder for complex agent workflows  

---

## 🎯 **v1.6 PLANNED - MCP Management + Custom Tools**

### **1. MCP Server Management System** 🛠️

Complete MCP server lifecycle management with CLI commands.

#### **Implementation Plan**

1. **MCP Configuration System**
   - Global MCP config (`~/.ago/mcp_server.yaml`)
   - Local MCP config (`.ago/mcp_server.yaml`)
   - Config merging and resolution priority
   - Environment variable resolution

2. **MCP Server Lifecycle**

   ```bash
   # MCP server management
   uv run ago mcp list                    # Show all servers with status
   uv run ago mcp add filesystem npx -y @modelcontextprotocol/server-filesystem .
   uv run ago mcp add brave_search npx -y @modelcontextprotocol/server-brave-search
   uv run ago mcp remove filesystem       # Remove server
   uv run ago mcp enable/disable filesystem
   uv run ago mcp edit --global          # Edit config with vim
   uv run ago mcp status                 # Show server health
   ```

3. **Tool Capability Discovery**
   - Automatic tool discovery from MCP servers
   - Tool capability validation and testing
   - Dynamic tool availability in agent creation
   - Tool compatibility checking

4. **MCP Configuration Structure**

   ```yaml
   # ~/.ago/mcp_server.yaml
   servers:
     filesystem:
       command: "npx"
       args: ["-y", "@modelcontextprotocol/server-filesystem", "."]
       env: {}
       description: "File and directory operations"
       enabled: true
     
     brave_search:
       command: "npx"
       args: ["-y", "@modelcontextprotocol/server-brave-search"]
       env:
         BRAVE_API_KEY: "$BRAVE_API_KEY"
       description: "Web search capabilities"
       enabled: true
   ```

### **2. Custom Tools Support** 🔌

Framework for non-MCP custom tools alongside MCP integration.

#### **Custom Tools Architecture**

1. **Plugin System Design**
   - Custom tool registration mechanism
   - Tool interface specification
   - Plugin discovery and loading
   - Tool execution sandboxing

2. **Tool Development Framework**
   - Tool SDK for custom tool development
   - Documentation and examples
   - Testing utilities and validation
   - Tool packaging and distribution

3. **Integration with Existing System**
   - Seamless integration with MCP tools
   - Unified tool discovery and selection
   - Consistent tool execution interface
   - Mixed tool usage in agent workflows

---

## 🌐 **v2.0 PLANNED - RAG Integration + Knowledge Bases**

### **Knowledge System Implementation**

- Document indexing and processing (txt, md, pdf)
- Vector database integration (ChromaDB for local, Pinecone for production)
- Agent-knowledge integration in responses
- Cross-agent knowledge sharing

### **RAG Pipeline**

- Automatic document processing and chunking
- Embedding generation and storage
- Semantic search and retrieval
- Context injection in agent responses

---

## 🎨 **v2.5 PLANNED - Web UI & Visual Dashboard**

### **Browser-Based Interface**

- Web UI for agent interaction and monitoring
- Visual ReAct reasoning flow display
- Real-time inter-agent message visualization
- Agent creation and management interface

### **FastAPI HTTP Endpoints**

- HTTP API endpoints for all CLI commands (chat, send, ps, queues, logs)
- RESTful agent management and communication
- Easy VPS deployment with web access
- Cross-platform agent interaction via HTTP

### **Technical Foundation**

- Built on existing web monitor patterns
- Modern web stack integration
- Real-time updates and monitoring
- Mobile-responsive design
- FastAPI backend with configurable port

---

## 🌍 **v3.0 VISION - Distributed Multi-Agent Orchestration**

### **Network Architecture**

- Multi-machine agent deployment
- Distributed communication protocols
- Agent discovery and registry services
- Load balancing and fault tolerance

### **Enterprise Features**

- Advanced workflow orchestration
- Enterprise security and compliance
- Team collaboration and permissions
- Analytics and performance monitoring

---

## 🔬 **Technical Implementation Details**

### **Current Architecture (v1.1)**

```
CLI → DaemonClient → Unix Socket → Daemon → PocketFlow Agent → ReAct → Response
```

### **Target Architecture (v1.2)**

```
CLI → DaemonClient → Unix Socket → Daemon → IPC → Agent Process → PocketFlow → ReAct → Response
```

### **Key Files for v1.2 Development**

1. **`ago/core/daemon.py`** - Main daemon process management
2. **`ago/core/daemon_client.py`** - CLI-daemon communication
3. **`ago/core/registry.py`** - Template discovery and GitHub integration
4. **`ago/core/config.py`** - Configuration system enhancements
5. **`ago/agents/agent_react_flow.py`** - Agent process wrapper

### **Development Environment Setup**

```bash
cd /Users/sky/git/CodeSwarm/pocket/ago/vision
uv pip install -e .

# Test current functionality
uv run ago create assistant --name TestAgent --quick
uv run ago run TestAgent_workflow.spec
uv run ago chat TestAgent
```

---

## 📊 **Progress Tracking**

- ✅ **v1.0**: Magic create + full Docker experience (100% complete)
- ✅ **v1.1**: Docker registry pattern + configuration system (100% complete) 
- ✅ **v1.2**: UNIX multi-process + remote registries + tool fixes (100% complete)
- ✅ **v1.3**: Multi-process architecture + inter-agent communication (100% complete)
- ✅ **v1.4**: Docker-like UX + performance fixes + agent name resolution (100% complete)
- 🎯 **v1.5**: Advanced agent reasoning + TUI interface (current priority)
- 🛠️ **v1.6**: MCP management + custom tools (next major release)
- 🌐 **v2.0+**: RAG, web UI, distributed architecture (future)

**🎉 Major Milestone Achieved**: Ago v1.4 now provides a complete Docker-like experience for AI agents with excellent performance, true process isolation, and intuitive command structure. The system is production-ready for local agent orchestration.

**Current Developer Focus**: Transforming agent interaction with Toad-inspired TUI, specialized reasoning agents (planner/socratic/tree-of-thought), and WebSocket foundation for future distributed architecture.

---

*Last Updated: January 2, 2025*

