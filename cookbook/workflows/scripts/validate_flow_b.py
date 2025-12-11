#!/usr/bin/env python3
"""
Validation script for Flow B (deep analysis path)
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

    # Different validation - check if result is detailed (deep path)
    is_valid = len(result) > 100

    output = {
        "status": "valid" if is_valid else "invalid",
        "flow": "B (deep analysis path)",
        "result_length": len(result),
        "message": f"Flow B completed: {'✓ Detailed analysis' if is_valid else '✗ Not detailed enough'}"
    }

    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
