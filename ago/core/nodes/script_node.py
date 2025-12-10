#!/usr/bin/env python3
"""
ScriptNode: Execute shell scripts with JSON input/output
"""
import json
import subprocess
from typing import Any, Dict

from pocketflow import AsyncNode

from .utils import resolve_inputs, store_node_output


class ScriptNode(AsyncNode):
    """Execute a script and pass output to next step"""

    def __init__(
        self,
        name: str,
        script_cmd: str,
        input_mapping: Dict = None,
        output_mapping: Dict = None,
    ):
        super().__init__()
        self.name = name
        self.script_cmd = script_cmd
        self.input_mapping = input_mapping or {}
        self.output_mapping = output_mapping or {}

    async def prep_async(self, shared):
        """Get input from previous step with field mapping"""
        if self.input_mapping:
            # Use dotted notation: sentiment.content, node.field, etc.
            input_data = resolve_inputs(self.input_mapping, shared)
        else:
            # No mapping - pass empty dict
            input_data = {}

        return {"input": input_data}

    async def exec_async(self, prep_res):
        """Execute script"""
        input_data = prep_res.get("input")

        print(f"[ScriptNode:{self.name}] Executing: {self.script_cmd}")
        print(f"[ScriptNode:{self.name}] Input: {input_data}")

        # Run script
        proc = subprocess.run(
            self.script_cmd,
            shell=True,
            capture_output=True,
            text=True,
            input=json.dumps(input_data) if input_data else "",
        )

        print(f"[ScriptNode:{self.name}] Return code: {proc.returncode}")
        print(f"[ScriptNode:{self.name}] Stdout: {proc.stdout}")
        print(f"[ScriptNode:{self.name}] Stderr: {proc.stderr}")

        if proc.returncode != 0:
            return {"error": proc.stderr, "success": False}

        # Parse output
        try:
            output = json.loads(proc.stdout.strip())
        except json.JSONDecodeError:
            output = {"result": proc.stdout.strip()}

        print(f"[ScriptNode:{self.name}] Output: {output}")
        return {"output": output, "success": True}

    async def post_async(self, shared, prep_res, exec_res):
        """Store output with dotted notation support"""
        output = exec_res.get("output")

        # Store output under node name: shared[node_name] = output
        # Also create optional shortcuts via output_mapping
        store_node_output(self.name, output, self.output_mapping, shared)

        shared["success"] = exec_res.get("success", True)
        return "default"  # PocketFlow uses "default" for >> edges
