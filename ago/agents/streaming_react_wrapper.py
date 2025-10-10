#!/usr/bin/env python3
"""
Streaming ReAct Wrapper - Adds streaming capability to existing PocketFlow ReAct flows
Works with our existing single-node self-looping ReAct flow
"""

import logging
from typing import Any, Dict, AsyncGenerator, Optional, Callable
from pocketflow import AsyncFlow


class StreamingFlow:
    """
    Streaming wrapper around existing PocketFlow AsyncFlow
    Intercepts each node completion and streams the results in real-time
    """
    
    def __init__(self, original_flow: AsyncFlow, stream_callback: Optional[Callable] = None):
        self.original_flow = original_flow
        self.stream_callback = stream_callback
        self.logger = logging.getLogger(f"StreamingFlow.{original_flow.start_node.agent_name if hasattr(original_flow.start_node, 'agent_name') else 'unknown'}")
    
    async def run_with_streaming(self, shared: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Run the flow with streaming - yields each ReAct step as it completes
        """
        try:
            # Debug: Check what we're working with
            self.logger.info(f"🔍 Original flow type: {type(self.original_flow)}")
            self.logger.info(f"🔍 Start node type: {type(self.original_flow.start_node)}")
            
            current_node = self.original_flow.start_node
            iteration = 0
            
            while current_node and iteration < 10:  # Safety limit
                iteration += 1
                self.logger.info(f"🔄 Streaming iteration {iteration}")
                
                try:
                    # Capture state before node execution
                    scratchpad_before = shared.get("supervisor_scratchpad", "")
                    
                    # Run the node using PocketFlow's internal method
                    # For AsyncNode, use _run_async; for regular Node, use _run
                    if hasattr(current_node, '_run_async'):
                        # AsyncNode - use internal async method
                        action = await current_node._run_async(shared)
                    else:
                        # Regular Node - use internal sync method
                        action = current_node._run(shared)
                    
                    self.logger.info(f"🎯 Node returned action: {action}")
                    
                    # Extract what happened in this iteration
                    step_data = self._extract_react_step(shared, action, scratchpad_before, iteration)
                    
                    # Stream the step immediately
                    if self.stream_callback:
                        await self.stream_callback(step_data)
                    
                    # Yield for async generator
                    yield step_data
                    
                    # Follow PocketFlow transitions to get next node
                    next_node = self._get_next_node(current_node, action)
                    self.logger.info(f"🔗 Next node: {type(next_node) if next_node else 'None'}")
                    
                    current_node = next_node
                    
                    # End the flow if we get "end" action or no next node
                    if action == "end" or not next_node:
                        self.logger.info(f"🏁 Flow ending: action={action}, next_node={next_node is not None}")
                        break
                        
                except Exception as e:
                    self.logger.error(f"Error in streaming iteration {iteration}: {e}")
                    import traceback
                    self.logger.error(f"Full traceback: {traceback.format_exc()}")
                    
                    error_step = {
                        "type": "error",
                        "content": str(e),
                        "iteration": iteration,
                        "is_final": True
                    }
                    
                    if self.stream_callback:
                        await self.stream_callback(error_step)
                        
                    yield error_step
                    break
            
            self.logger.info(f"✅ Streaming completed after {iteration} iterations")
            
        except Exception as e:
            self.logger.error(f"Fatal error in streaming: {e}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            
            yield {
                "type": "error",
                "content": f"Fatal streaming error: {str(e)}",
                "iteration": 0,
                "is_final": True
            }
    
    def _extract_react_step(self, shared: Dict[str, Any], action: str, scratchpad_before: str, iteration: int) -> Dict[str, Any]:
        """
        Extract meaningful content from the ReAct step that just completed
        """
        scratchpad_after = shared.get("supervisor_scratchpad", "")
        assistant_response = shared.get("assistant_response", "")
        
        # Determine what happened by analyzing scratchpad changes
        step_type, content = self._analyze_scratchpad_changes(scratchpad_before, scratchpad_after, assistant_response, action)
        
        return {
            "type": step_type,
            "content": content,
            "action": action,
            "iteration": iteration,
            "is_final": action == "end",
            "agent": getattr(self.original_flow.start, 'agent_name', 'unknown')
        }
    
    def _analyze_scratchpad_changes(self, before: str, after: str, assistant_response: str, action: str) -> tuple:
        """
        Analyze what happened by comparing scratchpad before/after
        Returns (step_type, content)
        """
        
        # If action is "end", this is the final response
        if action == "end":
            return "final", assistant_response or "Conversation completed"
        
        # Find what was added to scratchpad
        if len(after) > len(before):
            new_content = after[len(before):].strip()
            
            # Parse the new content to determine step type
            lines = new_content.split('\n')
            
            thought_content = ""
            tool_name = ""
            tool_result = ""
            current_section = None
            
            for line in lines:
                line = line.strip()
                if line.startswith("THOUGHT:"):
                    thought_content = line[8:].strip()
                    current_section = "thought"
                elif line.startswith("ACTION: use_tool"):
                    # Extract tool name from action line
                    tool_name = line.replace("ACTION: use_tool", "").strip()
                    current_section = "action"
                elif line.startswith("TOOL_RESULT:"):
                    tool_result = line[12:].strip()
                    current_section = "result"
                elif line.startswith("OBSERVATION:"):
                    # Skip observation lines - they're internal ReAct processing
                    current_section = "observation"
                elif current_section == "thought" and line and not line.startswith(("ACTION:", "TOOL_RESULT:", "OBSERVATION:")):
                    # Continue multi-line thought (but skip OBSERVATION lines)
                    thought_content += "\n" + line
            
            # Determine step type based on what we found
            if tool_result:
                # This iteration included tool execution
                return "tool_result", {
                    "thought": thought_content,
                    "tool_name": tool_name, 
                    "result": tool_result
                }
            elif tool_name:
                # This iteration decided to use a tool
                return "tool_use", {
                    "thought": thought_content,
                    "tool_name": tool_name
                }
            elif thought_content:
                # This iteration was just thinking
                return "thought", thought_content
        
        # Fallback - just thinking or continuing
        return "think", "Agent is reasoning..."
    
    def _get_next_node(self, current_node, action: str):
        """
        Follow PocketFlow transitions to get the next node
        Uses PocketFlow's successors dict structure
        """
        # Our ReAct flow structure:
        # agent_node - "continue" >> agent_node  (self-loop)
        # agent_node - "end" >> end_node
        
        # PocketFlow stores transitions in node.successors dict
        if hasattr(current_node, 'successors'):
            # Look for specific action first
            if action in current_node.successors:
                return current_node.successors[action]
            # Try default if action not found
            elif "default" in current_node.successors:
                return current_node.successors["default"]
        
        # No transition found
        return None
    
    # Compatibility methods to make this work like AsyncFlow
    
    async def run_async(self, shared: Dict[str, Any]) -> None:
        """
        Compatibility method - runs without streaming (like normal PocketFlow)
        """
        async for _ in self.run_with_streaming(shared):
            pass  # Just consume the stream without yielding
    
    def set_params(self, params: Dict[str, Any]) -> None:
        """Forward params to original flow"""
        self.original_flow.set_params(params)


def create_streaming_react_flow(agent_name: str, agent_spec: Dict[str, Any], agent_template: str, tools: list) -> StreamingFlow:
    """
    Create a streaming version of our existing ReAct flow
    
    Args:
        agent_name: Name of the agent
        agent_spec: Agent specification 
        agent_template: Agent prompt template
        tools: Available tools
        
    Returns:
        StreamingFlow wrapper around the ReAct flow
    """
    # Import the existing ReAct flow factory
    from .agent_react_flow import create_agent_flow
    
    # Create the original flow
    original_flow = create_agent_flow(agent_name, agent_spec, agent_template, tools)
    
    # Wrap it with streaming capability
    streaming_flow = StreamingFlow(original_flow)
    
    return streaming_flow


# Convenience function for quick testing
async def test_streaming_flow():
    """Test the streaming flow with a simple example"""
    from .agent_react_flow import create_agent_flow
    
    # Mock data for testing
    agent_spec = {"model": "claude-3-5-haiku-20241022"}
    agent_template = "You are a helpful assistant that can use tools."
    tools = []
    
    # Create streaming flow
    streaming_flow = create_streaming_react_flow("test-agent", agent_spec, agent_template, tools)
    
    # Test shared store
    shared = {
        "conversation_history": [],
        "tools": tools,
        "supervisor_scratchpad": "",
        "user_message": "Hello, can you help me?",
        "assistant_response": "",
    }
    
    print("🚀 Testing streaming flow...")
    async for step in streaming_flow.run_with_streaming(shared):
        print(f"📝 Step [{step['type']}]: {step['content']}")
        if step['is_final']:
            print("🏁 Final step reached")
            break


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_streaming_flow())