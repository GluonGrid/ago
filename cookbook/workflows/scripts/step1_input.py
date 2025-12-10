#!/usr/bin/env python3
import json
import sys

# Simple hardcoded input (for non-interactive workflows)
# In production, you could read from args or environment
name = sys.argv[1] if len(sys.argv) > 1 else "Alice"
topic = sys.argv[2] if len(sys.argv) > 2 else "AI and Machine Learning"

# Output as JSON
print(json.dumps({"name": name, "topic": topic}))
