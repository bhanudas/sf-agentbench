"""Shared event storage for cross-process communication.

Uses SQLite for persistence so multiple processes can communicate.
"""

import json
import sqlite3
import threading
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterator

from sf_agentbench.events.types import (
    Event,
    LogEvent,
    LogLevel,
    StatusEvent,
    ProgressEvent,
    MetricsEvent,
    CommandEvent,
    CommandType,
)


class SharedEventStore:
    """SQLite-based event storage for cross-process communication.
    
    Multiple processes can write events, and the REPL can poll for new events.
    Uses a simple append-only log with sequence numbers.
    """
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        event_type TEXT NOT NULL,
        source TEXT,
        work_unit_id TEXT,
        data JSON NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
    CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);
    CREATE INDEX IF NOT EXISTS idx_events_work_unit ON events(work_unit_id);
    """
    
    def __init__(self, db_path: Path | str | None = None):
        """Initialize the shared event store.
        
        Args:
            db_path: Path to SQLite database (default: results/events.db)
        """
        if db_path is None:
            db_path = Path("results") / "events.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._local = threading.local()
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=10.0,
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_conn()
        conn.executescript(self.SCHEMA)
        conn.commit()
    
    def publish(self, event: Event) -> int:
        """Publish an event to the shared store.
        
        Args:
            event: Event to publish
            
        Returns:
            Event ID (sequence number)
        """
        conn = self._get_conn()
        
        # Serialize event data
        event_type = type(event).__name__
        source = getattr(event, 'source', None)
        work_unit_id = getattr(event, 'work_unit_id', None)
        
        # Convert event to dict
        data = self._event_to_dict(event)
        
        cursor = conn.execute(
            """
            INSERT INTO events (timestamp, event_type, source, work_unit_id, data)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event.timestamp.isoformat(),
                event_type,
                source,
                work_unit_id,
                json.dumps(data),
            )
        )
        conn.commit()
        
        return cursor.lastrowid
    
    def _event_to_dict(self, event: Event) -> dict:
        """Convert event to dictionary for JSON storage."""
        data = {
            "timestamp": event.timestamp.isoformat(),
            "type": type(event).__name__,
        }
        
        if isinstance(event, LogEvent):
            data.update({
                "level": event.level.value,
                "source": event.source,
                "message": event.message,
                "work_unit_id": event.work_unit_id,
                "details": event.details,
            })
        elif isinstance(event, StatusEvent):
            data.update({
                "work_unit_id": event.work_unit_id,
                "status": event.status,
                "progress": event.progress,
                "metrics": event.metrics,
            })
        elif isinstance(event, ProgressEvent):
            data.update({
                "work_unit_id": event.work_unit_id,
                "current": event.current,
                "total": event.total,
                "message": event.message,
            })
        elif isinstance(event, MetricsEvent):
            data.update({
                "work_unit_id": event.work_unit_id,
                "metrics": event.metrics,
            })
        elif isinstance(event, CommandEvent):
            data.update({
                "command": event.command.value,
                "work_unit_id": event.work_unit_id,
                "payload": event.payload,
            })
        
        return data
    
    def _dict_to_event(self, data: dict) -> Event:
        """Convert dictionary back to event object."""
        event_type = data.get("type", "LogEvent")
        timestamp = datetime.fromisoformat(data["timestamp"])
        
        if event_type == "LogEvent":
            return LogEvent(
                timestamp=timestamp,
                level=LogLevel(data.get("level", "info")),
                source=data.get("source", "unknown"),
                message=data.get("message", ""),
                work_unit_id=data.get("work_unit_id"),
                details=data.get("details", {}),
            )
        elif event_type == "StatusEvent":
            return StatusEvent(
                timestamp=timestamp,
                work_unit_id=data.get("work_unit_id", ""),
                status=data.get("status", ""),
                progress=data.get("progress"),
                metrics=data.get("metrics", {}),
            )
        elif event_type == "ProgressEvent":
            return ProgressEvent(
                timestamp=timestamp,
                work_unit_id=data.get("work_unit_id", ""),
                current=data.get("current", 0),
                total=data.get("total", 0),
                message=data.get("message", ""),
            )
        elif event_type == "MetricsEvent":
            return MetricsEvent(
                timestamp=timestamp,
                work_unit_id=data.get("work_unit_id", ""),
                metrics=data.get("metrics", {}),
            )
        elif event_type == "CommandEvent":
            return CommandEvent(
                timestamp=timestamp,
                command=CommandType(data.get("command", "status")),
                work_unit_id=data.get("work_unit_id"),
                payload=data.get("payload", {}),
            )
        else:
            # Default to LogEvent
            return LogEvent(
                timestamp=timestamp,
                level=LogLevel.INFO,
                source="unknown",
                message=str(data),
            )
    
    def get_events_since(
        self,
        since_id: int = 0,
        limit: int = 100,
        source_filter: str | None = None,
    ) -> list[tuple[int, Event]]:
        """Get events since a specific ID.
        
        Args:
            since_id: Get events with ID > since_id
            limit: Maximum number of events
            source_filter: Filter by source
            
        Returns:
            List of (id, event) tuples
        """
        conn = self._get_conn()
        
        query = "SELECT id, data FROM events WHERE id > ?"
        params: list = [since_id]
        
        if source_filter:
            query += " AND source LIKE ?"
            params.append(f"%{source_filter}%")
        
        query += " ORDER BY id ASC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, params).fetchall()
        
        results = []
        for row in rows:
            data = json.loads(row["data"])
            event = self._dict_to_event(data)
            results.append((row["id"], event))
        
        return results
    
    def get_latest_id(self) -> int:
        """Get the latest event ID."""
        conn = self._get_conn()
        row = conn.execute("SELECT MAX(id) as max_id FROM events").fetchone()
        return row["max_id"] or 0
    
    def poll(
        self,
        since_id: int = 0,
        timeout: float = 30.0,
        poll_interval: float = 0.5,
    ) -> Iterator[tuple[int, Event]]:
        """Poll for new events continuously.
        
        Args:
            since_id: Start from this ID
            timeout: Stop after this many seconds
            poll_interval: How often to check for new events
            
        Yields:
            (id, event) tuples as they arrive
        """
        current_id = since_id
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            events = self.get_events_since(current_id, limit=50)
            
            for event_id, event in events:
                current_id = event_id
                yield event_id, event
            
            if not events:
                time.sleep(poll_interval)
    
    def clear(self, before_id: int | None = None) -> int:
        """Clear old events.
        
        Args:
            before_id: Clear events with ID < before_id (None = clear all)
            
        Returns:
            Number of events deleted
        """
        conn = self._get_conn()
        
        if before_id is None:
            cursor = conn.execute("DELETE FROM events")
        else:
            cursor = conn.execute("DELETE FROM events WHERE id < ?", (before_id,))
        
        conn.commit()
        return cursor.rowcount
    
    def get_active_work_units(self) -> list[dict]:
        """Get currently active work units based on status events.
        
        Returns:
            List of work unit info dicts
        """
        conn = self._get_conn()
        
        # Get latest status for each work unit
        rows = conn.execute("""
            SELECT 
                work_unit_id,
                data,
                MAX(id) as latest_id
            FROM events
            WHERE event_type = 'StatusEvent' AND work_unit_id IS NOT NULL
            GROUP BY work_unit_id
            ORDER BY latest_id DESC
            LIMIT 50
        """).fetchall()
        
        work_units = []
        for row in rows:
            data = json.loads(row["data"])
            status = data.get("status", "unknown")
            
            # Only include non-completed work units
            if status not in ("completed", "failed", "cancelled"):
                work_units.append({
                    "work_unit_id": row["work_unit_id"],
                    "status": status,
                    "progress": data.get("progress"),
                    "metrics": data.get("metrics", {}),
                })
        
        return work_units


# Global shared store instance
_shared_store: SharedEventStore | None = None


def get_shared_store() -> SharedEventStore:
    """Get the global shared event store."""
    global _shared_store
    if _shared_store is None:
        _shared_store = SharedEventStore()
    return _shared_store


def reset_shared_store() -> None:
    """Reset the shared store (for testing)."""
    global _shared_store
    _shared_store = None
