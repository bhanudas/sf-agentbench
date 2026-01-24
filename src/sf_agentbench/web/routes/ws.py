"""WebSocket routes for real-time updates."""

import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


# =============================================================================
# Connection Manager
# =============================================================================


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, run_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        if run_id not in self.active_connections:
            self.active_connections[run_id] = []
        self.active_connections[run_id].append(websocket)

    def disconnect(self, websocket: WebSocket, run_id: str):
        """Remove a WebSocket connection."""
        if run_id in self.active_connections:
            if websocket in self.active_connections[run_id]:
                self.active_connections[run_id].remove(websocket)
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]

    async def send_message(self, run_id: str, message: dict):
        """Send a message to all connections for a run."""
        if run_id in self.active_connections:
            message_json = json.dumps(message, default=str)
            for connection in self.active_connections[run_id]:
                try:
                    await connection.send_text(message_json)
                except Exception:
                    # Connection might be closed
                    pass

    async def broadcast(self, message: dict):
        """Broadcast a message to all connections."""
        message_json = json.dumps(message, default=str)
        for run_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_text(message_json)
                except Exception:
                    pass


manager = ConnectionManager()


# =============================================================================
# WebSocket Routes
# =============================================================================


@router.websocket("/ws/runs/{run_id}")
async def websocket_run_events(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for run-specific events.

    Protocol:
    - Server -> Client events:
      - {"type": "event", "data": {...}}
      - {"type": "progress", "data": {...}}
      - {"type": "result", "data": {...}}
      - {"type": "error", "data": {...}}

    - Client -> Server commands:
      - {"command": "subscribe", "filters": {...}}
      - {"command": "pause"}
      - {"command": "resume"}
      - {"command": "cancel"}
    """
    from sf_agentbench.events.shared import get_shared_store

    await manager.connect(websocket, run_id)

    try:
        # Get the shared event store
        event_store = get_shared_store()
        last_event_id = 0

        # Send initial connection acknowledgment
        await websocket.send_json(
            {
                "type": "connected",
                "data": {
                    "run_id": run_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }
        )

        while True:
            # Check for new events
            events = event_store.get_events_since(since_id=last_event_id, limit=50)

            for event_id, event in events:
                last_event_id = event_id

                # Convert event to dict
                event_data = {
                    "type": "event",
                    "data": {
                        "id": event_id,
                        "event_type": type(event).__name__,
                        "timestamp": event.timestamp.isoformat(),
                        **_event_to_dict(event),
                    },
                }

                await websocket.send_json(event_data)

            # Check for client messages (non-blocking)
            try:
                # Wait for message with timeout
                data = await asyncio.wait_for(
                    websocket.receive_json(), timeout=0.5
                )

                # Handle client commands
                await _handle_client_command(websocket, run_id, data)

            except asyncio.TimeoutError:
                # No message received, continue polling
                pass
            except WebSocketDisconnect:
                break

            # Brief pause before next poll
            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, run_id)


@router.websocket("/ws/global")
async def websocket_global_events(websocket: WebSocket):
    """WebSocket endpoint for global events (all runs).

    Useful for the dashboard to show overall status.
    """
    await websocket.accept()

    try:
        from sf_agentbench.events.shared import get_shared_store

        event_store = get_shared_store()
        last_event_id = event_store.get_latest_id()

        await websocket.send_json(
            {
                "type": "connected",
                "data": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "latest_event_id": last_event_id,
                },
            }
        )

        while True:
            # Check for new events
            events = event_store.get_events_since(since_id=last_event_id, limit=100)

            for event_id, event in events:
                last_event_id = event_id

                event_data = {
                    "type": "event",
                    "data": {
                        "id": event_id,
                        "event_type": type(event).__name__,
                        "timestamp": event.timestamp.isoformat(),
                        **_event_to_dict(event),
                    },
                }

                await websocket.send_json(event_data)

            # Check for client messages
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(), timeout=1.0
                )
                # Handle ping/pong or other commands
                if data.get("command") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break

            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        pass


# =============================================================================
# Helper Functions
# =============================================================================


def _event_to_dict(event: Any) -> dict:
    """Convert an event object to a dictionary."""
    from sf_agentbench.events.types import (
        LogEvent,
        StatusEvent,
        ProgressEvent,
        MetricsEvent,
        CommandEvent,
    )

    data = {}

    if isinstance(event, LogEvent):
        data = {
            "level": event.level.value if hasattr(event.level, "value") else str(event.level),
            "source": event.source,
            "message": event.message,
            "work_unit_id": event.work_unit_id,
            "details": event.details,
        }
    elif isinstance(event, StatusEvent):
        data = {
            "work_unit_id": event.work_unit_id,
            "status": event.status,
            "progress": event.progress,
            "metrics": event.metrics,
        }
    elif isinstance(event, ProgressEvent):
        data = {
            "work_unit_id": event.work_unit_id,
            "current": event.current,
            "total": event.total,
            "message": event.message,
        }
    elif isinstance(event, MetricsEvent):
        data = {
            "work_unit_id": event.work_unit_id,
            "metrics": event.metrics,
        }
    elif isinstance(event, CommandEvent):
        data = {
            "command": event.command.value if hasattr(event.command, "value") else str(event.command),
            "work_unit_id": event.work_unit_id,
            "payload": event.payload,
        }

    return data


async def _handle_client_command(websocket: WebSocket, run_id: str, data: dict):
    """Handle a command from the WebSocket client."""
    command = data.get("command")

    if command == "ping":
        await websocket.send_json({"type": "pong"})

    elif command == "subscribe":
        # Client wants to filter events
        filters = data.get("filters", {})
        await websocket.send_json(
            {
                "type": "subscribed",
                "data": {"run_id": run_id, "filters": filters},
            }
        )

    elif command == "pause":
        # Send pause command to worker pool
        from sf_agentbench.events.types import CommandEvent, CommandType
        from sf_agentbench.events.shared import get_shared_store

        event = CommandEvent.pause(work_unit_id=run_id)
        get_shared_store().publish(event)

        await websocket.send_json(
            {"type": "command_sent", "data": {"command": "pause", "run_id": run_id}}
        )

    elif command == "resume":
        from sf_agentbench.events.types import CommandEvent
        from sf_agentbench.events.shared import get_shared_store

        event = CommandEvent.resume(work_unit_id=run_id)
        get_shared_store().publish(event)

        await websocket.send_json(
            {"type": "command_sent", "data": {"command": "resume", "run_id": run_id}}
        )

    elif command == "cancel":
        from sf_agentbench.events.types import CommandEvent
        from sf_agentbench.events.shared import get_shared_store

        event = CommandEvent.cancel(work_unit_id=run_id)
        get_shared_store().publish(event)

        await websocket.send_json(
            {"type": "command_sent", "data": {"command": "cancel", "run_id": run_id}}
        )

    else:
        await websocket.send_json(
            {"type": "error", "data": {"message": f"Unknown command: {command}"}}
        )
