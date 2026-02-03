"""API routes for the web interface."""

from sf_agentbench.web.routes.runs import router as runs_router
from sf_agentbench.web.routes.qa import router as qa_router
from sf_agentbench.web.routes.tasks import router as tasks_router
from sf_agentbench.web.routes.ws import router as ws_router
from sf_agentbench.web.routes.prompt_runner import router as prompt_runner_router

__all__ = ["runs_router", "qa_router", "tasks_router", "ws_router", "prompt_runner_router"]
