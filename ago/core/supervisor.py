#!/usr/bin/env python3
"""
SupervisorNode - LLM-powered supervisor with proper ReAct pattern
Includes: Thought -> Action -> Observation -> [repeat] -> Final Answer
"""

import asyncio
import os
from datetime import datetime

import aiohttp
import yaml

# Import local modules
from .base_node import BaseAgentNode
from .mcp_integration import call_tool_async
from .tool_formatter import ToolFormatter


class LLMService:
    """Unified LLM service"""

    @staticmethod
    async def call_llm(
        prompt: str, agent_name: str = "Supervisor", max_retries: int = 3
    ) -> str:
        """Make LLM call with retry logic"""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise Exception(f"ANTHROPIC_API_KEY is required for {agent_name}")

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        data = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 64000,
            "messages": [{"role": "user", "content": prompt}],
        }

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as session:
                    async with session.post(
                        url, headers=headers, json=data
                    ) as response:
                        if response.status in [529, 429]:  # Rate limit errors
                            wait_time = 3 + (attempt * 2)  # 3s, 5s, 7s
                            print(
                                f"      ⏳ {agent_name} API rate limit, waiting {wait_time}s..."
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        elif response.status != 200:
                            raise Exception(
                                f"LLM API call failed with status {response.status}"
                            )

                        response_data = await response.json()
                        return response_data["content"][0]["text"]

            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                await asyncio.sleep(1)

        raise Exception(f"LLM call failed after {max_retries} attempts")


class YAMLParser:
    """YAML parser for ReAct responses with observation support"""

    @staticmethod
    def parse_response(response: str, available_tools: list = None) -> dict:
        """Parse YAML response from LLM"""
        try:
            if "```yaml" in response:
                # Find first ```yaml and last ``` to capture entire YAML block
                start_idx = response.find("```yaml") + 7  # Skip "```yaml"
                end_idx = response.rfind("```")  # Find LAST ``` in entire response

                if end_idx > start_idx:  # Make sure last ``` comes after ```yaml
                    yaml_block = response[start_idx:end_idx].strip()
                else:
                    # Fallback: no closing ``` found, take everything after ```yaml
                    yaml_block = response[start_idx:].strip()
                # Debug: log the exact YAML block being parsed
                import logging

                logger = logging.getLogger("nator.YAMLParser")
                # Debug logging (can be removed in production)
                logger.info(f"YAML BLOCK LENGTH: {len(yaml_block)}")
                parsed = yaml.safe_load(yaml_block)

                action = parsed.get("action", "think")
                thought = parsed.get("thought", "AI reasoning in progress...")
                observation = parsed.get("observation", "")  # New: observation field

                # Handle different action types
                if action == "final":
                    return {
                        "thought": thought,
                        "observation": observation,
                        "action": "final",
                        "tool_name": "",
                        "tool_params": {},
                        "final_answer": parsed.get("final_answer", ""),
                    }
                elif action == "use_tool":
                    action_input = parsed.get("action_input", {})
                    tool_name = action_input.get("tool_name", "")
                    tool_params = action_input.get("parameters", {})

                    return {
                        "thought": thought,
                        "observation": observation,
                        "action": "use_tool",
                        "tool_name": tool_name,
                        "tool_params": tool_params,
                        "final_answer": "",
                    }
                elif action == "delegate_task":
                    action_input = parsed.get("action_input", {})
                    return {
                        "thought": thought,
                        "observation": observation,
                        "action": "delegate_task",
                        "task_description": action_input.get("task_description", ""),
                        "final_answer": "",
                    }
                else:
                    # think or unknown action - default to think
                    return {
                        "thought": thought,
                        "observation": observation,
                        "action": "think",
                        "tool_name": "",
                        "tool_params": {},
                        "final_answer": "",
                    }
            else:
                # No YAML block found - treat as final answer
                return {
                    "thought": "No structured response found",
                    "observation": "",
                    "action": "final",
                    "tool_name": "",
                    "tool_params": {},
                    "final_answer": response,
                }
        except Exception as e:
            # YAML parsing failed
            return {
                "thought": f"Failed to parse response: {str(e)}",
                "observation": "",
                "action": "final",
                "tool_name": "",
                "tool_params": {},
                "final_answer": "I had trouble understanding that. Could you rephrase?",
            }


class SupervisorNode(BaseAgentNode):
    """LLM-powered supervisor with proper ReAct pattern"""

    def __init__(self, max_iterations: int = 5):
        super().__init__("Supervisor", max_iterations)

    async def prep_async(self, shared):
        """Prepare for ReAct reasoning - user_input provided by terminal interface"""

        # Process any coordinator messages
        while True:
            try:
                # Non-blocking get - process all available messages
                message = await asyncio.wait_for(self.inbox.get(), timeout=0.1)

                if message.get("type") == "coordination_plan":
                    # Add coordination plan to scratchpad for LLM to see
                    plan_info = f"COORDINATOR RESPONSE: Task analysis: {message.get('task_analysis', 'N/A')}"
                    plan_info += f"\nComplexity: {message.get('complexity', 'N/A')}"
                    subtasks = message.get("subtasks", [])
                    if subtasks:
                        plan_info += f"\nSubtasks ({len(subtasks)}):"
                        for i, subtask in enumerate(subtasks, 1):
                            plan_info += f"\n  {i}. {subtask.get('name', 'Unnamed')}: {subtask.get('description', 'No description')}"

                    shared["supervisor_scratchpad"] = (
                        shared.get("supervisor_scratchpad", "") + f"\n{plan_info}"
                    )
                    shared["coordination_plan_received"] = (
                        True  # Flag to indicate plan received
                    )
                    self.logger.info(
                        "Supervisor received coordination plan from coordinator"
                    )

            except asyncio.TimeoutError:
                # No more messages in inbox
                break

        return {
            "user_input": shared.get("user_input", ""),
            "scratchpad": shared.get("supervisor_scratchpad", ""),
            "tools": shared.get("tools", []),
            "conversation_history": shared.get("conversation_history", []),
            "coordination_plan_received": shared.get(
                "coordination_plan_received", False
            ),
        }

    async def exec_async(self, prep_res):
        """ReAct reasoning with LLM"""
        user_input = prep_res["user_input"]
        scratchpad = prep_res["scratchpad"]
        tools = prep_res["tools"]
        conversation_history = prep_res["conversation_history"]
        coordination_plan_received = prep_res.get("coordination_plan_received", False)

        if user_input.lower() in ["exit", "quit", "bye"]:
            return {"action": "end", "response": "Goodbye!"}

        # If we received a coordination plan, provide final answer instead of delegating again
        if coordination_plan_received and "COORDINATOR RESPONSE:" in scratchpad:
            self.logger.info("Supervisor has coordination plan, providing final answer")
            return {
                "thought": "I have received the coordination plan from the coordinator and can now provide a comprehensive response.",
                "action": "final",
                "final_answer": "I've successfully delegated your REST API implementation task to our coordinator. Here's the coordination plan that was created:\n\n"
                + scratchpad.split("COORDINATOR RESPONSE:")[-1],
            }

        # Format ALL tools with detailed parameters for prompt
        tool_list = ToolFormatter.format_tools(tools)

        # Format conversation history
        history_text = ""
        if conversation_history:
            history_text = "\n".join(
                [f"User: {item['user']}" for item in conversation_history[-5:]]
            )  # Last 5 exchanges

        # Create ReAct prompt with standard format Claude Sonnet knows
        prompt = f"""You are a Supervisor AI agent using the ReAct (Reasoning and Acting) pattern.

CONVERSATION HISTORY:
{history_text if history_text else "No previous conversation."}

CURRENT USER REQUEST: {user_input}

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
  What you observed from previous actions (empty if first step)
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
4. delegate_task: Delegate complex coding task to coordinator (requires action_input with task_description using literal block format)

IMPORTANT: 
1. Always include thought and observation fields
2. Only use ONE action per response
3. Use exact field names as shown above
4. Use proper indentation (4 spaces) for all multi-line fields
5. Use the | character for multi-line text fields
6. For task_description in delegate_task: use literal block (|) and avoid numbered lists or special characters that break YAML parsing
7. Keep single-line fields without the | character"""

        try:
            # Make LLM call
            self.logger.info(f"ReAct iteration {self.iteration + 1}")
            response = await LLMService.call_llm(prompt, self.agent_name)

            # Parse response
            self.logger.info(
                f"RAW LLM RESPONSE: {response[-500:]}"
            )  # Last 500 chars to see how it ends
            parsed = YAMLParser.parse_response(response, tools)
            self.logger.info(f"LLM decision: {parsed['action']}")
            self.logger.info(f"PARSER: {parsed}")

            return parsed

        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            return {
                "thought": f"Error calling LLM: {str(e)}",
                "observation": "",
                "action": "final",
                "tool_name": "",
                "tool_params": {},
                "final_answer": "I'm having trouble processing that right now. Please try again.",
            }

    async def post_async(self, shared, prep_res, exec_res):
        """Handle ReAct decision and execute actions"""
        decision = exec_res
        action = decision.get("action", "think")

        # Update scratchpad with current thought and observation
        thought = decision.get("thought", "")
        observation = decision.get("observation", "")
        shared["supervisor_scratchpad"] = shared.get("supervisor_scratchpad", "")
        shared["supervisor_scratchpad"] += f"\nTHOUGHT: {thought}"
        if observation:
            shared["supervisor_scratchpad"] += f"\nOBSERVATION: {observation}"

        if action == "final":
            # Provide final answer and end this flow
            response = decision.get(
                "final_answer", "I'm not sure how to respond to that."
            )
            print(f"Agent: {response}")
            # Clear scratchpad and flags for next conversation
            shared["supervisor_scratchpad"] = ""
            shared["task_delegated"] = False
            shared["coordination_plan_received"] = False
            self.iteration = 0
            return "end"  # End this flow

        elif action == "use_tool":
            # Execute tool and add observation
            tool_name = decision.get("tool_name", "")
            tool_params = decision.get("tool_params", {})

            if not tool_name:
                # Add failed action to scratchpad
                shared["supervisor_scratchpad"] += (
                    "\nACTION: use_tool (failed - no tool specified)"
                )
                shared["supervisor_scratchpad"] += (
                    "\nTOOL_RESULT: Error - no tool name provided"
                )
            else:
                try:
                    self.logger.info(
                        f"Using tool: {tool_name} with params: {tool_params}"
                    )
                    shared["supervisor_scratchpad"] += f"\nACTION: use_tool {tool_name}"

                    tool_result = await call_tool_async(tool_name, tool_params)
                    self.logger.info(f"TOOLRESULTS: {tool_result}")

                    # Add tool result to scratchpad (this will be used in next observation)
                    if isinstance(tool_result, list) and len(tool_result) > 0:
                        result_text = str(tool_result[0])
                    else:
                        result_text = f"Tool error - {str(tool_result)}"

                    shared["supervisor_scratchpad"] += f"\nTOOL_RESULT: {result_text}"

                except Exception as e:
                    self.logger.error(f"Tool execution failed: {e}")
                    shared["supervisor_scratchpad"] += (
                        f"\nTOOL_RESULT: Tool error - {str(e)}"
                    )

            # Continue ReAct loop
            self.iteration += 1
            if self.iteration >= self.max_iterations:
                print(
                    "Agent: I've reached my maximum reasoning steps. Let me provide what I have so far."
                )
                # Force final answer on next iteration
                shared["supervisor_scratchpad"] += (
                    "\nTHOUGHT: Maximum iterations reached, providing final answer"
                )
                self.iteration = 0
                return "continue"

            return "continue"  # Continue ReAct loop

        elif action == "think":
            # Continue reasoning
            self.iteration += 1
            if self.iteration >= self.max_iterations:
                print(
                    "Agent: I've been thinking long enough. Let me give you an answer."
                )
                shared["supervisor_scratchpad"] += (
                    "\nTHOUGHT: Maximum iterations reached, providing final answer"
                )
                self.iteration = 0

            return "continue"  # Continue ReAct loop

        elif action == "delegate_task":
            # Task delegation - send message to coordinator via AsyncQueue
            task_desc = decision.get("task_description", "")

            # Check if we already delegated this task to avoid loops
            if shared.get("task_delegated"):
                self.logger.info(
                    "Task already delegated, waiting for coordinator response..."
                )
                self.iteration += 1
                if self.iteration >= self.max_iterations:
                    print("Agent: Waiting too long for coordinator response.")
                    return "end"
                return "continue"

            print(f"Agent: I'm delegating this task to the coordinator: {task_desc}")

            # Send delegation message to coordinator
            coordinator_node = shared.get("coordinator_node")
            if coordinator_node:
                delegation_message = {
                    "type": "task_delegation",
                    "content": task_desc,
                    "from": "supervisor",
                    "timestamp": datetime.now().isoformat(),
                }
                await self.send_message(coordinator_node, delegation_message)

                # Mark task as delegated to prevent re-delegation
                shared["task_delegated"] = True
                shared["supervisor_scratchpad"] += (
                    f"\nACTION: delegated task to coordinator: {task_desc}"
                )
                print(
                    "Agent: Task delegated to coordinator. Waiting for coordination plan..."
                )

                self.iteration += 1
                return "continue"  # Continue to wait for coordinator response
            else:
                print("Agent: No coordinator available for delegation")
                shared["supervisor_scratchpad"] += (
                    "\nACTION: delegation failed - no coordinator"
                )
                return "continue"

        else:
            # Unknown action - treat as think
            self.iteration += 1
            return "continue"
