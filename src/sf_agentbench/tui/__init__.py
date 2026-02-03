"""Terminal User Interface for SF-AgentBench."""

from sf_agentbench.tui.app import SFAgentBenchApp


def run() -> None:
    """Run the TUI application."""
    app = SFAgentBenchApp()
    app.run()


__all__ = ["SFAgentBenchApp", "run"]
