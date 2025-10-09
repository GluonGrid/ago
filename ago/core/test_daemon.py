#!/usr/bin/env python3
"""
Quick test script to debug daemon startup issues
"""

import sys
from pathlib import Path

# Test if we can import daemon components
try:
    from .daemon import AgoDaemon

    print("✅ Successfully imported daemon components")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

# Test if we can create daemon instance
try:
    daemon = AgoDaemon()
    print("✅ Successfully created daemon instance")
    print(f"Daemon dir: {daemon.daemon_dir}")
    print(f"Socket file: {daemon.socket_file}")
    print(f"PID file: {daemon.pid_file}")
except Exception as e:
    print(f"❌ Daemon creation error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Test if we have all required dependencies
try:
    import yaml

    print("✅ yaml imported")
except ImportError:
    print("❌ Missing yaml dependency")

try:
    from rich.console import Console

    print("✅ rich imported")
except ImportError:
    print("❌ Missing rich dependency")

# Test ago components
try:
    from agents.supervisor import LLMService, YAMLParser

    print("✅ Ago components imported")
except ImportError as e:
    print(f"❌ Ago import error: {e}")

print("\n🧪 All basic imports successful. Try running daemon manually:")
print(f"python {Path(__file__).parent / 'daemon.py'}")
