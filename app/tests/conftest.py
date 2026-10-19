"""Cross-platform test runtime configuration."""

import asyncio
import sys


# OpenAI/httpx MockTransport streaming can crash CPython's Windows Proactor
# during overlapping async-stream and self-pipe teardown.  Selector exercises
# the same application code and deterministic offline transport without that
# native teardown race.  Production runtime policy is intentionally untouched.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
