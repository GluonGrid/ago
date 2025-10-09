#!/usr/bin/env python3
"""
Agent ReAct Flow Factory - Creates PocketFlow agents using nator's BaseAgentNode
Integrates existing ReAct patterns with Ago daemon architecture
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

from pocketflow import AsyncFlow, AsyncNode

# Import local modules using relative imports
from ..core.base_node import BaseAgentNode
from ..core.mcp_integration import call_tool_async
from ..core.supervisor import LLMService, YAMLParser
from ..core.tool_formatter import ToolFormatter


class EndNode(AsyncNode):
    """Simple end node to terminate ReAct flow cleanly"""
    pass


class AgentReActNode(BaseAgentNode):
    """
    ReAct Agent Node for Ago daemon
    Uses existing nator ReAct pattern with agent template specialization
    """

    def __init__(
        self,
        agent_name: str,
        agent_spec: Dict[str, Any],
        agent_template: str,
        max_iterations: int = 5,
    ):
        super().__init__(agent_name, max_iterations)
        self.agent_spec = agent_spec
        self.agent_template = agent_template

    async def prep_async(self, shared):
        """Prepare ReAct reasoning context"""

        # Process any inter-agent messages from inbox (like nator supervisor)
        while True:
            try:
                # Non-blocking get - process all available messages
                message = await self.get_message(timeout=0.1)
                if message:
                    message_content = f"INTER-AGENT MESSAGE from {message.get('from', 'unknown')}: {message.get('content', '')}"
                    shared["supervisor_scratchpad"] = (
                        shared.get("supervisor_scratchpad", "") + f"\n{message_content}"
                    )
                    self.logger.info(
                        f"{self.agent_name} received inter-agent message from {message.get('from')}"
                    )
                else:
                    break
            except:
                # No more messages
                break

        return {
            "user_message": shared.get("user_message", ""),
            "inter_agent_message": shared.get("inter_agent_message", {}),
            "scratchpad": shared.get("supervisor_scratchpad", ""),
            "tools": shared.get("tools", []),
            "conversation_history": shared.get("conversation_history", []),
        }

    async def exec_async(self, prep_res):
        """Execute ReAct reasoning using existing nator pattern"""
        user_message = prep_res["user_message"]
        inter_agent_msg = prep_res["inter_agent_message"]
        scratchpad = prep_res["scratchpad"]
        tools = prep_res["tools"]
        conversation_history = prep_res["conversation_history"]

        # Handle inter-agent messages
        if inter_agent_msg:
            message_content = inter_agent_msg.get("content", "")
            if message_content:
                user_message = f"[Inter-agent message from {inter_agent_msg.get('from', 'unknown')}]: {message_content}"

        if user_message.lower() in ["exit", "quit", "bye"]:
            return {"action": "end", "response": "Goodbye!"}

        # Format tools using existing nator pattern
        tool_list = ToolFormatter.format_tools(tools)

        # Format conversation history
        history_text = ""
        if conversation_history:
            history_text = "\n".join(
                [
                    f"User: {item.get('user', item.get('content', ''))}\nAssistant: {item.get('assistant', item.get('response', ''))}"
                    for item in conversation_history[-3:]  # Last 3 exchanges
                ]
            )

        # Create ReAct prompt using exact nator format for better reliability
        prompt = f"""{self.agent_template}

CONVERSATION HISTORY:
{history_text if history_text else "No previous conversation."}

CURRENT USER REQUEST: {user_message}

AVAILABLE TOOLS:
{tool_list}

SCRATCHPAD (your reasoning so far):
{scratchpad if scratchpad else "No previous reasoning."}

INSTRUCTIONS:
You must follow the ReAct pattern: Thought → Action → Observation → [repeat if needed] → Final Answer.

REQUIRED YAML OUTPUT FORMAT:
You MUST respond with exactly one YAML block using this format:

```yaml
thought: |
  Your step-by-step reasoning about what to do next
observation: |  
  IMPORTANT: Look at the SCRATCHPAD above and summarize what happened in previous actions. If you see TOOL_RESULT entries, describe what tools were used and their results. If this is the first step, write "This is the first step."
action: think OR use_tool OR final OR delegate_task
action_input:  # Only if action is use_tool or delegate_task
  tool_name: tool_name_here     # For use_tool
  parameters:                   # For use_tool
    param_name: value_here
  task_description: |                       # For delegate_task - use literal block
    Detailed task description without numbered lists
final_answer: |             # Only if action is final
  Your complete response to the user
```

ACTION TYPES:
1. think: Continue reasoning (no additional fields needed)
2. use_tool: Execute a specific tool (requires action_input with tool_name and parameters) 
3. final: Provide final answer (requires final_answer field)
4. delegate_task: Delegate task to another agent (requires action_input with task_description using literal block format)

IMPORTANT: 
1. Always include thought and observation fields
2. The observation field MUST summarize what happened in previous actions based on the SCRATCHPAD content above
3. Only use ONE action per response
4. Use exact field names as shown above
5. Use proper indentation (4 spaces) for all multi-line fields
6. Use the | character for multi-line text fields
7. For task_description in delegate_task: use literal block (|) and avoid numbered lists or special characters that break YAML parsing
8. Keep single-line fields without the | character"""

        try:
            # Make LLM call using existing nator service
            self.logger.info(
                f"ReAct iteration {self.iteration + 1} for {self.agent_name}"
            )
            response = await LLMService.call_llm(prompt, self.agent_name)

            # Parse response using existing nator parser
            parsed = YAMLParser.parse_response(response, tools)
            self.logger.info(f"{self.agent_name} decision: {parsed['action']}")

            return parsed

        except Exception as e:
            self.logger.error(f"{self.agent_name} LLM call failed: {e}")
            return {
                "thought": f"Error calling LLM: {str(e)}",
                "observation": "",
                "action": "final",
                "tool_name": "",
                "tool_params": {},
                "final_answer": "I'm having trouble processing that right now. Please try again.",
            }

    async def post_async(self, shared, prep_res, exec_res):
        """Handle ReAct decision and execute actions using nator pattern"""
        decision = exec_res
        action = decision.get("action", "think")

        # Update scratchpad with current thought and observation (nator pattern)
        thought = decision.get("thought", "")
        observation = decision.get("observation", "")
        shared["supervisor_scratchpad"] = shared.get("supervisor_scratchpad", "")
        shared["supervisor_scratchpad"] += f"\nTHOUGHT: {thought}"
        if observation:
            shared["supervisor_scratchpad"] += f"\nOBSERVATION: {observation}"

        if action == "final":
            # Provide final answer and end flow
            response = decision.get(
                "final_answer", "I'm not sure how to respond to that."
            )

            # Store response for daemon to return
            shared["assistant_response"] = response

            # Update conversation history
            user_msg = prep_res.get("user_message", "")
            inter_agent_msg = prep_res.get("inter_agent_message")
            if inter_agent_msg:
                user_msg = f"[From {inter_agent_msg.get('from', 'unknown')}]: {inter_agent_msg.get('content', '')}"

                # Store just the clean response content for sending back
                shared["response_to_send"] = response

            shared["conversation_history"].append(
                {
                    "user": user_msg,
                    "assistant": response,
                    "timestamp": self._get_timestamp(),
                    "thought": thought,
                    "observation": observation,
                }
            )

            # Clear scratchpad for next conversation
            shared["supervisor_scratchpad"] = ""
            self.iteration = 0
            return "end"  # End this flow

        elif action == "use_tool":
            # Execute tool using existing nator pattern
            tool_name = decision.get("tool_name", "")
            tool_params = decision.get("tool_params", {})

            if not tool_name:
                shared["supervisor_scratchpad"] += (
                    "\nACTION: use_tool (failed - no tool specified)"
                )
                shared["supervisor_scratchpad"] += (
                    "\nTOOL_RESULT: Error - no tool name provided"
                )
            else:
                try:
                    self.logger.info(
                        f"{self.agent_name} using tool: {tool_name} with params: {tool_params}"
                    )
                    shared["supervisor_scratchpad"] += f"\nACTION: use_tool {tool_name}"

                    tool_result = await call_tool_async(tool_name, tool_params)
                    self.logger.info(
                        f"{self.agent_name} tool result: {str(tool_result)[:100]}..."
                    )

                    # Add tool result to scratchpad
                    if isinstance(tool_result, list) and len(tool_result) > 0:
                        result_text = str(tool_result[0])
                    else:
                        result_text = str(tool_result)

                    shared["supervisor_scratchpad"] += f"\nTOOL_RESULT: {result_text}"

                except Exception as e:
                    self.logger.error(f"{self.agent_name} tool execution failed: {e}")
                    shared["supervisor_scratchpad"] += (
                        f"\nTOOL_RESULT: Tool error - {str(e)}"
                    )

            # Continue ReAct loop
            self.iteration += 1
            if self.iteration >= self.max_iterations:
                self.logger.info(
                    f"{self.agent_name} reached max iterations, forcing final answer"
                )
                shared["supervisor_scratchpad"] += (
                    "\nTHOUGHT: Maximum iterations reached, providing final answer"
                )
                self.iteration = 0

            return "continue"

        elif action == "think":
            # Continue reasoning
            self.iteration += 1
            if self.iteration >= self.max_iterations:
                self.logger.info(f"{self.agent_name} max thinking iterations reached")
                shared["supervisor_scratchpad"] += (
                    "\nTHOUGHT: Maximum iterations reached, providing final answer"
                )
                self.iteration = 0

            return "continue"

        elif action == "delegate_task":
            # Task delegation to another agent
            task_desc = decision.get("task_description", "")

            self.logger.info(
                f"{self.agent_name} attempting task delegation: {task_desc[:50]}..."
            )
            shared["supervisor_scratchpad"] += (
                f"\nACTION: delegation attempted: {task_desc}"
            )

            # Store delegation request for daemon to handle
            shared["delegation_request"] = {
                "task_description": task_desc,
                "from_agent": self.agent_name,
            }

            self.iteration += 1
            return "continue"

        else:
            # Unknown action - treat as think
            self.iteration += 1
            return "continue"

    def _get_timestamp(self):
        """Get current timestamp for conversation history"""
        from datetime import datetime

        return datetime.now().isoformat()


def create_agent_flow(
    agent_name: str, agent_spec: Dict[str, Any], agent_template: str, tools: List[Dict]
) -> AsyncFlow:
    """
    Create PocketFlow ReAct agent using existing nator infrastructure

    Args:
        agent_name: Name of the agent
        agent_spec: Agent specification from workflow.spec
        agent_template: Agent role/specialization prompt template
        tools: Available tools for this agent

    Returns:
        AsyncFlow with ReAct agent node
    """
    # Create ReAct node with agent template
    agent_node = AgentReActNode(agent_name, agent_spec, agent_template)
    end_node = EndNode()

    # Set up ReAct loop and end transition
    agent_node - "continue" >> agent_node  # Self-loop for ReAct iterations
    agent_node - "end" >> end_node          # End transition for completion

    # Create flow
    flow = AsyncFlow(start=agent_node)

    return flow


def load_agent_template(template_file: Path) -> str:
    """Load agent template from file"""
    try:
        with open(template_file, "r") as f:
            return f.read()
    except Exception as e:
        logging.error(f"Failed to load agent template {template_file}: {e}")
        return "You are a helpful AI assistant."  # Fallback template

