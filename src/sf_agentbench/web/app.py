"""FastAPI application for SF-AgentBench web interface."""

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from sf_agentbench import __version__
from sf_agentbench.web.routes import runs_router, qa_router, tasks_router, ws_router
from sf_agentbench.web.schemas import HealthResponse


def create_app(
    title: str = "SF-AgentBench API",
    debug: bool = False,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        title: The API title shown in docs
        debug: Enable debug mode
        cors_origins: List of allowed CORS origins (default allows localhost)

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title=title,
        description="REST API for SF-AgentBench benchmark management and monitoring",
        version=__version__,
        debug=debug,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Configure CORS
    if cors_origins is None:
        cors_origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(runs_router, prefix="/api")
    app.include_router(qa_router, prefix="/api")
    app.include_router(tasks_router, prefix="/api")
    app.include_router(ws_router, prefix="/api")

    # Health check endpoint
    @app.get("/api/health", response_model=HealthResponse, tags=["health"])
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(
            status="healthy",
            version=__version__,
            timestamp=datetime.utcnow(),
        )

    # Root API info
    @app.get("/api", tags=["info"])
    async def api_info():
        """Get API information."""
        return {
            "name": "SF-AgentBench API",
            "version": __version__,
            "docs_url": "/api/docs",
            "endpoints": {
                "runs": "/api/runs",
                "qa": "/api/qa",
                "tasks": "/api/tasks",
                "models": "/api/models",
                "agents": "/api/agents",
                "config": "/api/config",
                "health": "/api/health",
                "websocket": "/api/ws",
            },
        }

    return app


def create_app_with_static(
    static_dir: Path | str | None = None,
    **kwargs,
) -> FastAPI:
    """Create FastAPI app with static file serving for the frontend.

    Args:
        static_dir: Path to the built frontend files (default: web/dist)
        **kwargs: Additional arguments for create_app

    Returns:
        Configured FastAPI application with static file serving
    """
    app = create_app(**kwargs)

    # Determine static directory
    if static_dir is None:
        # Look for web/dist relative to the package
        package_root = Path(__file__).parent.parent.parent.parent
        static_dir = package_root / "web" / "dist"

    static_path = Path(static_dir)

    if static_path.exists() and static_path.is_dir():
        # Serve static files
        app.mount(
            "/assets",
            StaticFiles(directory=static_path / "assets"),
            name="assets",
        )

        # Serve index.html for SPA routing
        @app.get("/")
        @app.get("/{path:path}")
        async def serve_spa(path: str = ""):
            # Don't serve SPA for API routes
            if path.startswith("api"):
                return None

            index_file = static_path / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return {"error": "Frontend not built. Run 'npm run build' in the web directory."}

    return app


# Create default app instance
app = create_app()


def run_dev_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = True,
):
    """Run the development server.

    Args:
        host: Host to bind to
        port: Port to listen on
        reload: Enable auto-reload on code changes
    """
    import uvicorn

    uvicorn.run(
        "sf_agentbench.web.app:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    run_dev_server()
