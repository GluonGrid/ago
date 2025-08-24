apiVersion: v1
kind: AgentWorkflow
metadata:
  name: two-agent-research
  description: Simple two-agent system with researcher and assistant using async queue communication

spec:
  agents:
    - name: researcher
      prompt_file: templates/researcher_agent.prompt
      model: claude-3-5-sonnet-20241022
      tools:
        - "web"
        - "file" 
        - "search"
      description: "Research specialist that gathers and analyzes information"
      
    - name: assistant  
      prompt_file: templates/assistant_agent.prompt
      model: claude-3-5-haiku-20241022
      tools:
        - "file"
        - "read"
        - "write"
      description: "General assistant that helps with tasks and organization"

  communication:
    type: "async_queue"
    description: "Agents communicate via asyncio.Queue for message passing"

  workflow:
    description: |
      A simple two-agent research system where:
      1. Agents communicate through shared async queues
      2. The researcher can send tasks to the assistant via queue
      3. The assistant can respond back through the queue system
      4. Both agents can work independently or collaboratively
      
  examples:
    - name: "Queue-based Research Collaboration"
      scenario: |
        User asks researcher: "Research the latest trends in AI agent systems"
        Researcher puts message in assistant's queue: {"task": "organize_findings", "data": "..."}
        Assistant processes queue message and responds back
        
    - name: "Async Information Synthesis" 
      scenario: |
        Researcher gathers data from multiple sources asynchronously
        Assistant receives structured tasks via queue and processes them
        Results flow back through the queue system