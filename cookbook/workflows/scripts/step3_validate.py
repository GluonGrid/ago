#!/usr/bin/env python3
import json
import sys

# Read from stdin
data = json.loads(sys.stdin.read())

# Validate
if "content" in data and len(data["content"]) > 10:
    print(json.dumps({"status": "valid"}))
    sys.exit(0)
else:
    print(json.dumps({"status": "invalid"}))
    sys.exit(1)
