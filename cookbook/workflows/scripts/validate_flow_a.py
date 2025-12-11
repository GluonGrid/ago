#!/usr/bin/env python3
"""
Validation script for Flow A (fast path)
"""
import sys
import json

def main():
    # Read input from stdin
    input_data = sys.stdin.read()

    try:
        data = json.loads(input_data) if input_data else {}
    except json.JSONDecodeError:
        data = {}

    result = data.get("result", "")

    # Simple validation - check if result is short (fast path)
    is_valid = len(result) < 500

    output = {
        "status": "valid" if is_valid else "invalid",
        "flow": "A (fast path)",
        "result_length": len(result),
        "message": f"Flow A completed: {'✓ Fast summary' if is_valid else '✗ Too long for fast path'}"
    }

    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
