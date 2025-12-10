#!/usr/bin/env python3
"""
ScriptNode: Execute shell scripts with JSON input/output
"""
import json
import subprocess
from typing import Dict, Optional

from .base_ago_node import AgoNode


class ScriptNode(AgoNode):
    """Execute a script and pass output to next step"""

    def __init__(
        self,
        name: str,
        script_cmd: str,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
    ):
        super().__init__(name, input_mapping, output_mapping)
        self.script_cmd = script_cmd

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
