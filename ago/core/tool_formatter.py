#!/usr/bin/env python3
"""
Tool formatter for displaying tool schemas in a human-readable format
Handles arrays, objects, enums, and other complex parameter types
"""

from typing import Any, Dict, List


class ToolFormatter:
    """Format tool schemas for LLM consumption with comprehensive parameter details"""

    @staticmethod
    def format_tools(tools: List[Dict[str, Any]]) -> str:
        """Format multiple tools into a readable string"""
        if not tools:
            return "No tools available"

        formatted = []
        for tool in tools:
            formatted_tool = ToolFormatter.format_single_tool(tool)
            formatted.append(formatted_tool)

        return "\n\n".join(formatted)

    @staticmethod
    def format_single_tool(tool: Dict[str, Any]) -> str:
        """Format a single tool with all its parameters"""
        name = tool.get("name", "unknown")
        desc = tool.get("description", "No description")
        params = tool.get("parameters", {})

        param_info = []
        for param_name, param_details in params.items():
            param_line = ToolFormatter._format_parameter(param_name, param_details)
            param_info.append(param_line)

        param_str = "\n".join(param_info) if param_info else "  - No parameters"
        return f"• {name}: {desc}\n{param_str}"

    @staticmethod
    def _format_parameter(
        param_name: str, param_details: Dict[str, Any], indent: str = "  "
    ) -> str:
        """Format a single parameter with all its details"""
        param_type = param_details.get("type", "unknown")
        param_desc = param_details.get("description", "")
        default_value = param_details.get("default")

        # Handle complex types
        formatted_type = ToolFormatter._format_parameter_type(param_details)

        # Build parameter line
        param_line = f"{indent}- {param_name}: {formatted_type}"

        # Add default value if present
        if default_value is not None:
            param_line += f" (default: {default_value})"

        # Add description
        if param_desc:
            param_line += f" - {param_desc}"

        return param_line

    @staticmethod
    def _format_parameter_type(param_details: Dict[str, Any]) -> str:
        """Format the parameter type with special handling for complex types"""
        param_type = param_details.get("type", "unknown")

        if param_type == "array":
            return ToolFormatter._format_array_type(param_details)
        elif param_type == "object":
            return ToolFormatter._format_object_type(param_details)
        elif param_type == "string" and "enum" in param_details:
            return ToolFormatter._format_enum_type(param_details)
        elif param_type == "boolean":
            return "boolean"
        elif param_type == "number":
            return "number"
        elif param_type == "integer":
            return "integer"
        else:
            return param_type

    @staticmethod
    def _format_array_type(param_details: Dict[str, Any]) -> str:
        """Format array parameter type"""
        items = param_details.get("items", {})
        items_type = items.get("type", "unknown")

        if items_type == "object" and "properties" in items:
            # Array of objects - show object structure
            properties = items["properties"]
            required = items.get("required", [])

            # Show first few properties with required markers
            prop_examples = []
            for prop_name in list(properties.keys())[:3]:
                prop_type = properties[prop_name].get("type", "unknown")
                required_marker = "*" if prop_name in required else ""
                prop_examples.append(f"{prop_name}{required_marker}: {prop_type}")

            prop_str = ", ".join(prop_examples)
            if len(properties) > 3:
                prop_str += "..."

            return f"array of objects (each with: {prop_str})"
        else:
            return f"array of {items_type}"

    @staticmethod
    def _format_object_type(param_details: Dict[str, Any]) -> str:
        """Format object parameter type"""
        properties = param_details.get("properties", {})
        if not properties:
            return "object"

        required = param_details.get("required", [])

        # Show first few properties with required markers
        prop_examples = []
        for prop_name in list(properties.keys())[:3]:
            prop_type = properties[prop_name].get("type", "unknown")
            required_marker = "*" if prop_name in required else ""
            prop_examples.append(f"{prop_name}{required_marker}: {prop_type}")

        prop_str = ", ".join(prop_examples)
        if len(properties) > 3:
            prop_str += "..."

        return f"object ({prop_str})"

    @staticmethod
    def _format_enum_type(param_details: Dict[str, Any]) -> str:
        """Format enum parameter type"""
        enum_values = param_details.get("enum", [])
        enum_str = " | ".join(str(v) for v in enum_values)
        return f"string (one of: {enum_str})"

