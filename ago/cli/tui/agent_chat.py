#!/usr/bin/env python3
"""
Textual TUI for agent chat - inspired by Toad
Provides professional, flicker-free terminal interface with dynamic message widgets
"""

import re
import sys
from datetime import datetime

from rich.spinner import Spinner
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Input, Static, TextArea

# Import Ago components
from ...core.daemon_client import DaemonClient


class SpinnerWidget(Static):
    """A spinner widget using Rich's Spinner for smooth animation"""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._spinner = Spinner("dots", style="#e5c890")

    def on_mount(self) -> None:
        """Start the spinner animation when mounted"""
        self.update(self._spinner)
        self.update_timer = self.set_interval(1 / 60, self.refresh)


class MessageWidget(Container):
    """Individual message widget that can contain both text and code blocks"""

    def __init__(
        self,
        content: str,
        author: str,
        timestamp: str,
        message_type: str = "user",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.content = content
        self.author = author
        self.timestamp = timestamp
        self.message_type = message_type

        # Add CSS classes based on message type
        if message_type == "user":
            self.add_class("user-message")
        elif message_type == "agent":
            self.add_class("agent-message")
        elif message_type == "system":
            self.add_class("system-message")
        elif message_type == "error":
            self.add_class("error-message")
        elif message_type == "success":
            self.add_class("success-message")
        elif message_type == "thought":
            self.add_class("thought-message")
        elif message_type == "tool_use":
            self.add_class("tool-use-message")
        elif message_type == "tool_result":
            self.add_class("tool-result-message")

    def compose(self) -> ComposeResult:
        """Compose the message with text and code blocks"""
        if self.message_type == "agent":
            # Parse and create content with code blocks
            segments = self._parse_code_blocks(self.content)

            for segment in segments:
                if segment["type"] == "text" and segment["content"].strip():
                    # Regular text content
                    yield Static(segment["content"])
                elif segment["type"] == "code":
                    # Code block with syntax highlighting
                    lang_label = (
                        segment["language"].upper()
                        if segment["language"] != "text"
                        else "CODE"
                    )

                    # Add syntax-highlighted code
                    try:
                        # Map common language names to Textual's built-in languages
                        # Based on BUILTIN_LANGUAGES: python, markdown, json, toml, yaml,
                        # html, css, javascript, rust, go, regex, sql, java, bash, xml
                        language_map = {
                            "python": "python",
                            "py": "python",
                            "javascript": "javascript",
                            "js": "javascript",
                            "bash": "bash",
                            "sh": "bash",
                            "shell": "bash",
                            "json": "json",
                            "yaml": "yaml",
                            "yml": "yaml",
                            "toml": "toml",
                            "html": "html",
                            "css": "css",
                            "sql": "sql",
                            "xml": "xml",
                            "markdown": "markdown",
                            "md": "markdown",
                            "rust": "rust",
                            "go": "go",
                            "java": "java",
                            "regex": "regex",
                            "regexp": "regex",
                            # Unsupported languages - fallback to similar or None
                            "typescript": "javascript",  # Fallback to JavaScript
                            "ts": "javascript",
                            "c": None,  # Not supported
                            "cpp": None,
                            "c++": None,
                            "csharp": None,
                            "c#": None,
                            "php": None,
                            "ruby": None,
                            "swift": None,
                            "kotlin": "java",  # Fallback to Java (similar syntax)
                            "scala": "java",
                            "dockerfile": None,
                            "text": None,  # No highlighting for plain text
                        }

                        # Get the mapped language or use the original
                        mapped_language = language_map.get(
                            segment["language"].lower(), segment["language"]
                        )

                        # Use code_editor for all languages, with language=None for unsupported ones
                        if mapped_language and mapped_language in [
                            "python",
                            "markdown",
                            "json",
                            "toml",
                            "yaml",
                            "html",
                            "css",
                            "javascript",
                            "rust",
                            "go",
                            "regex",
                            "sql",
                            "java",
                            "bash",
                            "xml",
                        ]:
                            # Supported language - use syntax highlighting
                            language_param = mapped_language
                        else:
                            # Unsupported language - use code_editor appearance without highlighting
                            language_param = None

                        code_area = TextArea.code_editor(
                            segment["content"],
                            language=language_param,
                            read_only=True,
                            show_line_numbers=False,
                        )
                        # Make it compact
                        code_area.styles.height = "auto"
                        code_area.styles.max_height = 20  # Limit height
                        yield code_area
                    except Exception as e:
                        # Debug: Print what language failed
                        print(f"TextArea language '{segment['language']}' failed: {e}")
                        # Fallback to simple text display
                        yield Static(f"[on #2d3748]{segment['content']}[/on #2d3748]")

        else:
            # For non-agent messages, use simple text display
            yield Static(self._render_simple_message())

    def _parse_code_blocks(self, text: str) -> list:
        """Parse text to extract code blocks and regular text segments"""
        # Pattern to match code blocks: ```language\ncode\n``` or ```\ncode\n```
        pattern = r"```(?:(\w+))?(?:\r?\n)?(.*?)(?:\r?\n)?```"

        segments = []
        last_end = 0

        for match in re.finditer(pattern, text, re.DOTALL):
            # Add text before code block
            if match.start() > last_end:
                segments.append(
                    {"type": "text", "content": text[last_end : match.start()]}
                )

            # Add code block
            language = (
                match.group(1) or "text"
            )  # Default to 'text' if no language specified
            code = match.group(2).strip()

            segments.append({"type": "code", "language": language, "content": code})

            last_end = match.end()

        # Add remaining text after last code block
        if last_end < len(text):
            segments.append({"type": "text", "content": text[last_end:]})

        return segments

    def _render_simple_message(self) -> str:
        """Render non-agent messages using the original logic"""
        lines = []

        if self.message_type == "user":
            # User message - blue theme with background highlight
            # Content without text-based borders (CSS handles borders)
            for line in self.content.split("\n"):
                lines.append(f"[on #414559]{line}[/on #414559]")

        elif self.message_type == "system":
            # System message - gray theme
            lines.append(
                f"[#838ba7]{self.timestamp}[/#838ba7] [dim]{self.content}[/dim]"
            )

        elif self.message_type == "error":
            # Error message - red theme
            lines.append(f"[#e78284]✗ {self.content}[/#e78284]")

        elif self.message_type == "success":
            # Success message - green theme
            lines.append(f"[#a6d189]✓ {self.content}[/#a6d189]")

        elif self.message_type == "thought":
            # Agent thought - yellow/orange theme
            lines.append("[#e5c890]💭 Thought:[/#e5c890]")
            for line in self.content.split("\n"):
                lines.append(f"[dim]{line}[/dim]")

        elif self.message_type == "tool_use":
            # Tool usage - purple theme
            lines.append(
                f"[#c886f7]🔧 Using tool:[/#c886f7] [bold]{self.content}[/bold]"
            )

        return "\n".join(lines)


class AgoChatApp(App):
    """
    Toad-inspired chat interface with dynamic message widgets
    Features clean, modern design with individual message control
    """

    CSS = """
    /* Catppuccin Frappe color palette */
    
    #main-container {
        height: 100vh;
        background: #303446;
    }
    
    /* Messages container - scrollable area for dynamic widgets */
    #messages-container {
        height: 1fr;
        background: #303446;
        scrollbar-background: #414559;
        scrollbar-color: #8caaee;
        padding: 1;
    }
    
    /* Individual message widgets */
    MessageWidget {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }
    
    /* Message type-specific styling */
    .user-message {
        border-left: solid #8caaee;
        padding-left: 1;
    }
    
    .agent-message {
        border-left: solid #a6d189;
        padding-left: 1;
    }
    
    .system-message {
        /* No border for system messages */
    }
    
    .error-message {
        border-left: solid #e78284;
        padding-left: 1;
    }
    
    .success-message {
        border-left: solid #a6d189;
        padding-left: 1;
    }
    
    .thought-message {
        border-left: solid #e5c890;
        padding-left: 1;
        margin-top: 1;
    }
    
    .tool-use-message {
        border-left: solid #c886f7;
        padding-left: 1;
    }
    
    .tool-result-message {
        border-left: solid #8caaee;
        padding-left: 1;
        margin-bottom: 1;
    }
    
    /* Status bar - above input */
    #status-bar {
        dock: bottom;
        height: 5;
        layout: horizontal;
    }
    
    #status-spinner {
        width: auto;
        color: #e5c890;
    }
    
    #status-text {
        width: 1fr;
        color: #e5c890;
        content-align: left middle;
        padding: 0 1;
    }
    
    /* Input at the very bottom */
    #input-section {
        dock: bottom;
        height: 4;
        border: heavy #c886f7;
    }
    
    #message-input {
        width: 100%;
        border: none;
        background: #303446;
    }
    
    Input > .input--cursor {
        background: #8caaee;
        color: #303446;
    }
    
    Input > .input--placeholder {
        text-style: italic;
    }
    """

    TITLE = "Ago Chat"

    def __init__(self, agent_name: str):
        super().__init__()
        self.agent_name = agent_name
        self.daemon_client = DaemonClient()
        self.connected = False

    def compose(self) -> ComposeResult:
        """Build the chat interface layout"""

        with Container(id="main-container"):
            # Messages container - where dynamic message widgets will be mounted
            with VerticalScroll(id="messages-container"):
                pass  # Messages will be added dynamically here

            # Status bar (above input)
            with Horizontal(id="status-bar"):
                yield SpinnerWidget(id="status-spinner")
                yield Static("Ready", id="status-text")

            # Input section (at bottom)
            with Container(id="input-section"):
                yield Input(
                    placeholder=f"Message {self.agent_name}...", id="message-input"
                )

    async def add_message(
        self, content: str, author: str, message_type: str = "user"
    ) -> None:
        """Add a new message widget to the messages container"""
        timestamp = datetime.now().strftime("%H:%M")

        message_widget = MessageWidget(
            content=content,
            author=author,
            timestamp=timestamp,
            message_type=message_type,
        )

        messages_container = self.query_one("#messages-container")
        await messages_container.mount(message_widget)

        # Auto-scroll to bottom to show new message
        messages_container.scroll_end(animate=True)

    async def parse_and_display_react_steps(
        self, response: dict, agent_display_name: str
    ) -> str:
        """Parse the daemon response and display ReAct reasoning steps"""

        # Get the scratchpad from response if available
        scratchpad = response.get("scratchpad", "")
        agent_response = response.get("response", "No response received")

        if not scratchpad:
            # No scratchpad available, just return the response
            return agent_response

        # Parse scratchpad for ReAct steps
        lines = scratchpad.split("\n")
        current_thought = ""
        current_tool_use = ""

        for line in lines:
            line = line.strip()

            if line.startswith("THOUGHT:"):
                if current_thought:
                    # Display previous thought
                    await self.add_message(
                        current_thought, agent_display_name, "thought"
                    )
                current_thought = line[8:].strip()  # Remove "THOUGHT: "

            elif line.startswith("OBSERVATION:"):
                # Skip observations as they're displayed with tool results
                continue

            elif line.startswith("ACTION:"):
                if current_thought:
                    # Display the thought before the action
                    await self.add_message(
                        current_thought, agent_display_name, "thought"
                    )
                    current_thought = ""

                # Extract tool name from action line
                action_text = line[7:].strip()  # Remove "ACTION: "
                if "use_tool" in action_text:
                    tool_name = action_text.replace("use_tool", "").strip()
                    current_tool_use = tool_name
                    if tool_name:
                        await self.add_message(
                            tool_name, agent_display_name, "tool_use"
                        )

            elif line.startswith("TOOL_RESULT:"):
                # Display tool result
                result_text = line[12:].strip()  # Remove "TOOL_RESULT: "
                # Clean up the result text (remove type='text' text='...' formatting)
                if "text='" in result_text:
                    start = result_text.find("text='") + 6
                    end = result_text.rfind("'")
                    if start < end:
                        result_text = result_text[start:end]

                await self.add_message(result_text, agent_display_name, "tool_result")

        # Display any remaining thought
        if current_thought:
            await self.add_message(current_thought, agent_display_name, "thought")

        return agent_response

    async def on_mount(self) -> None:
        """Initialize the chat interface"""

        spinner = self.query_one("#status-spinner", SpinnerWidget)
        status_text = self.query_one("#status-text", Static)

        # Welcome message using message widgets
        await self.add_message(
            "╭─────────────────────────────────╮\n│  Welcome to Ago Chat Interface  │\n╰─────────────────────────────────╯",
            "System",
            "system",
        )

        await self.add_message(
            f"Connecting to agent: {self.agent_name}", "System", "system"
        )

        # Show connecting status
        status_text.update("[#e5c890]Connecting...[/#e5c890]")

        # Connect to agent
        try:
            response = await self.daemon_client.list_agents()
            if isinstance(response, dict):
                agents = response.get("agents", {})

                agent_found = False
                for instance_id, agent_info in agents.items():
                    agent_name = agent_info.get("agent_name", "")
                    if agent_name == self.agent_name or instance_id == self.agent_name:
                        agent_found = True
                        self.agent_name = instance_id
                        break

                if agent_found:
                    self.connected = True
                    await self.add_message(
                        "Connected successfully", "System", "success"
                    )
                    spinner.display = False
                    status_text.update("[#a6d189]🤖 Ready[/#a6d189]")
                else:
                    await self.add_message(
                        f"Agent '{self.agent_name}' not found", "System", "error"
                    )

                    available_agents = []
                    for instance_id, agent_info in agents.items():
                        agent_name = agent_info.get("agent_name", instance_id)
                        available_agents.append(f"  • {agent_name} ({instance_id})")

                    await self.add_message(
                        "Available agents:\n" + "\n".join(available_agents),
                        "System",
                        "system",
                    )
                    spinner.display = False
                    status_text.update("[#e78284]❌ Not Connected[/#e78284]")
            else:
                await self.add_message("Could not connect to daemon", "System", "error")
                spinner.display = False
                status_text.update("[#e78284]❌ Daemon Error[/#e78284]")

        except Exception as e:
            await self.add_message(f"Connection error: {e}", "System", "error")
            spinner.display = False
            status_text.update("[#e78284]❌ Connection Error[/#e78284]")

        self.query_one("#message-input", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user message submission"""

        message = event.value.strip()
        if not message:
            return

        event.input.value = ""

        if not self.connected:
            await self.add_message("Not connected to agent", "System", "error")
            return

        spinner = self.query_one("#status-spinner", SpinnerWidget)
        status_text = self.query_one("#status-text", Static)

        # Add user message widget
        await self.add_message(message, "You", "user")

        # Show thinking status with spinner
        spinner.display = True
        status_text.update("[#e5c890]Thinking...[/#e5c890]")

        try:
            agent_display_name = (
                self.agent_name.split("-")[0]
                if "-" in self.agent_name
                else self.agent_name
            )

            # Use streaming chat message
            async for step in self.daemon_client.chat_message_streaming(
                self.agent_name, message
            ):
                if step.get("status") == "error":
                    error_msg = step.get("message", "Unknown error")
                    await self.add_message(f"Error: {error_msg}", "System", "error")
                    spinner.display = False
                    status_text.update("[#e78284]❌ Error[/#e78284]")
                    break

                # Display each streaming step in real-time
                step_type = step.get("type", "unknown")
                content = step.get("content", "")
                is_final = step.get("is_final", False)

                # Debug: Log step types to understand what we're receiving
                print(
                    f"🔍 DEBUG: Received step_type='{step_type}', is_final={is_final}"
                )

                if step_type == "thought":
                    await self.add_message(content, agent_display_name, "thought")
                elif step_type == "tool_use":
                    # Handle tool_use steps (when agent decides to use a tool)
                    if isinstance(content, dict):
                        thought = content.get("thought", "")
                        tool_name = content.get("tool_name", "Unknown tool")
                        if thought:
                            await self.add_message(
                                thought, agent_display_name, "thought"
                            )
                        await self.add_message(
                            f"Using {tool_name}", agent_display_name, "tool_use"
                        )
                    else:
                        await self.add_message(
                            f"Using tool: {content}", agent_display_name, "tool_use"
                        )
                elif step_type == "tool_result":
                    # Handle tool_result steps (complete cycle with thought + tool use + result)
                    if isinstance(content, dict):
                        thought = content.get("thought", "")
                        tool_name = content.get("tool_name", "Unknown tool")
                        if thought:
                            await self.add_message(
                                thought, agent_display_name, "thought"
                            )
                        if tool_name:
                            await self.add_message(
                                f"Using {tool_name}", agent_display_name, "tool_use"
                            )
                        # Don't display the actual tool result as requested by user
                    else:
                        await self.add_message(
                            "Tool executed", agent_display_name, "tool_use"
                        )
                elif step_type == "final":
                    await self.add_message(content, agent_display_name, "agent")

                # Update status during streaming
                if not is_final:
                    if step_type == "thought":
                        status_text.update("[#e5c890]💭 Thought [/#e5c890]")
                    elif step_type == "tool_use":
                        status_text.update("[#c886f7]🔧 Using tool...[/#c886f7]")
                else:
                    # Final step - hide spinner and show ready
                    spinner.display = False
                    status_text.update("[#a6d189]🤖 Ready[/#a6d189]")
                    break

        except Exception as e:
            await self.add_message(f"Error: {e}", "System", "error")
            spinner.display = False
            status_text.update("[#e78284]❌ Error[/#e78284]")

        self.query_one("#message-input", Input).focus()

    def on_key(self, event: events.Key) -> None:
        """Handle key presses"""
        if event.key in ("ctrl+c", "escape"):
            self.exit()


def run_chat_tui(agent_name: str) -> None:
    """
    Run the Textual chat interface

    Args:
        agent_name: Name of the agent to chat with
    """

    if not sys.stdout.isatty():
        print("❌ TUI mode requires a terminal environment")
        return

    try:
        app = AgoChatApp(agent_name)
        app.run()

    except KeyboardInterrupt:
        print(f"\n👋 Chat with {agent_name} ended")
    except Exception as e:
        print(f"❌ TUI Error: {e}")
        print("Falling back to simple chat mode...")
