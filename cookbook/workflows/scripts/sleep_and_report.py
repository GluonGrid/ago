#!/usr/bin/env python3
"""
Sleep for specified seconds and report progress
"""
import sys
import json
import time

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: sleep_and_report.py <seconds> <flow_name>"}))
        sys.exit(1)

    seconds = int(sys.argv[1])
    flow_name = sys.argv[2]

    start_time = time.time()

    print(f"[{flow_name}] Starting {seconds}s processing...", file=sys.stderr)

    # Simulate processing
    time.sleep(seconds)

    end_time = time.time()
    actual_duration = end_time - start_time

    output = {
        "flow": flow_name,
        "status": "completed",
        "expected_duration": seconds,
        "actual_duration": round(actual_duration, 2),
        "timestamp": int(end_time)
    }

    print(json.dumps(output, indent=2))
    print(f"[{flow_name}] Completed after {actual_duration:.2f}s", file=sys.stderr)

if __name__ == "__main__":
    main()
