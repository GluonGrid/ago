#!/usr/bin/env python3
"""
Ago Daemon Main Entry Point - Switch between v1 and v2 architectures
"""

import asyncio
import os
import sys

from rich.console import Console

console = Console()


async def main():
    """Main entry point for daemon"""
    try:
        # Check for architecture version flag (v2 is default)
        use_v2 = os.environ.get("AGO_DAEMON_V2", "true").lower() == "true"

        if use_v2:
            console.print("🚀 Starting Ago daemon v2 (Multi-Process Architecture)")
            from .daemon_v2 import AgoDaemonV2 as DaemonClass
        else:
            console.print("🚀 Starting Ago daemon v1 (Single-Process Architecture)")
            from .daemon import AgoDaemon as DaemonClass

        daemon = DaemonClass()
        await daemon.start()

    except KeyboardInterrupt:
        console.print("\n🛑 Daemon interrupted by user")
    except Exception as e:
        console.print(f"❌ [red]Daemon failed: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

