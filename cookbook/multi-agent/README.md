# Ago Cookbook 🧑‍🍳

This folder contains example workflows and multi-agent system configurations for testing Ago capabilities.

## 📖 Available Examples

### 1. Two-Agent Research System (`two_agent_research.spec`)

A simple multi-agent system demonstrating async queue-based communication between two Claude-powered agents:

- **Researcher Agent** (Claude Sonnet): Specializes in information gathering and analysis
- **Assistant Agent** (Claude Haiku): Handles organization, formatting, and task processing

**Communication**: Uses `asyncio.Queue` for inter-agent message passing

**Usage**:

```bash
# Start the two-agent system
ago run cookbook/two_agent_research.spec

# List running agents
ago ps

# Chat with the researcher
ago chat researcher

# Chat with the assistant  
ago chat assistant

# Start just one agent from the spec
ago start researcher
ago start assistant
```

## 🔧 How Multi-Agent Communication Works

1. **Async Queue System**: Agents communicate through `asyncio.Queue` objects managed by the daemon
2. **Message Format**: Structured JSON messages with task types, data, and metadata
3. **Non-blocking**: Agents can send messages and continue processing without waiting
4. **Coordinated**: The daemon manages message routing between agents

## 🎯 Testing Scenarios

### Scenario 1: Basic Research Delegation

1. Ask researcher: "Research the latest developments in AI agent systems"
2. Researcher should delegate organization tasks to assistant
3. Assistant processes and structures the information
4. Both agents collaborate to provide comprehensive results

### Scenario 2: Queue Message Processing

1. Send complex multi-part research request to researcher
2. Researcher breaks it down and sends sub-tasks via queue to assistant
3. Assistant processes queue messages asynchronously
4. Results flow back through queue system

### Scenario 3: Live Queue Monitoring

```bash
# Terminal 1: Start live queue monitoring (like docker logs -f)
ago queues --follow

# Terminal 2: Send test messages between agents
ago send researcher assistant "Please organize this research data"
ago send assistant researcher "Task completed - data organized"

# Terminal 3: Chat with agents (generates more messages)  
ago chat researcher

# View agent inbox status
ago queues

# View specific agent's message history
ago queues researcher --tail 10
```

**Expected Live Output**:

```
📨 Following inter-agent messages in real-time...
Press Ctrl+C to stop

🔴 Live messages:
--------------------------------------------------
🤖 2024-08-15T10:30:15 researcher → assistant: Please organize this research data
🤖 2024-08-15T10:30:18 assistant → researcher: Task completed - data organized
🤖 2024-08-15T10:30:25 researcher → assistant: Analyze this data  
🤖 2024-08-15T10:30:30 assistant → researcher: Analysis complete
```

## 🚀 Creating New Cookbook Examples

To create new examples:

1. **Create Agent Templates**: Add new `.prompt` files in `templates/`
2. **Define Workflow Spec**: Create a new `.spec` file in `cookbook/`
3. **Specify Models**: Use Claude models (`claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022`)
4. **Design Communication**: Plan how agents will use async queues
5. **Test**: Use `ago run` to test your workflow

## 📝 Template Structure

```yaml
apiVersion: v1
kind: AgentWorkflow
metadata:
  name: your-workflow-name
  description: Brief description

spec:
  agents:
    - name: agent_name
      prompt_file: templates/your_template.prompt
      model: claude-3-5-sonnet-20241022
      tools: ["web", "file", "search"]
      description: "Agent description"
  
  communication:
    type: "async_queue"
    description: "Communication method"
    
  workflow:
    description: |
      Detailed workflow description
```

## 🎯 Next Steps

1. Test the two-agent research system
2. Create more specialized agent templates
3. Add more complex multi-agent workflows
4. Implement hierarchical agent delegation
5. Add workflow orchestration patterns

Happy agent cooking! 👨‍🍳🤖

