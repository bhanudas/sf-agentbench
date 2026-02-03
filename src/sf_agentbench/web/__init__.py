"""Web interface for SF-AgentBench.

Provides a FastAPI backend and React frontend for viewing benchmark results,
launching runs, and monitoring progress in real-time.
"""

from sf_agentbench.web.app import create_app

__all__ = ["create_app"]
