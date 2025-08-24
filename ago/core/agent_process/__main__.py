#!/usr/bin/env python3
"""
Ago Agent Process Main Entry Point
"""

import asyncio

from .main import main

if __name__ == "__main__":
    asyncio.run(main())

