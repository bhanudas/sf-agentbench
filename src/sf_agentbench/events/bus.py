"""Thread-safe event bus for pub/sub communication.

Provides the central communication hub between workers and REPL.
"""

import queue
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Any
import logging

from sf_agentbench.events.types import (
    Event,
    LogEvent,
    LogLevel,
    StatusEvent,
    CommandEvent,
    CommandType,
    MetricsEvent,
)


# Type alias for event handlers
EventHandler = Callable[[Event], None]


class EventBus:
    """Thread-safe pub/sub event bus.
    
    Features:
    - Type-based subscriptions
    - Wildcard subscriptions (receive all events)
    - Event history buffer
    - Thread-safe operations
    """
    
    def __init__(
        self,
        history_size: int = 1000,
        logger: logging.Logger | None = None,
    ):
        """Initialize the event bus.
        
        Args:
            history_size: Number of events to keep in history buffer
            logger: Optional logger for debugging
        """
        self._lock = threading.RLock()
        self._subscribers: dict[type, list[EventHandler]] = defaultdict(list)
        self._wildcard_subscribers: list[EventHandler] = []
        
        # Event history buffer (circular)
        self._history: list[Event] = []
        self._history_size = history_size
        
        # Event queue for async processing
        self._queue: queue.Queue[Event] = queue.Queue()
        self._processing = False
        self._processor_thread: threading.Thread | None = None
        
        self._logger = logger or logging.getLogger(__name__)
    
    def subscribe(
        self,
        event_type: type[Event] | None = None,
        handler: EventHandler | None = None,
    ) -> Callable[[EventHandler], EventHandler]:
        """Subscribe to events of a specific type.
        
        Can be used as a decorator or called directly.
        
        Args:
            event_type: Type of events to subscribe to (None for all)
            handler: Handler function (for direct calls)
        
        Returns:
            Decorator function if handler not provided
        """
        def decorator(fn: EventHandler) -> EventHandler:
            with self._lock:
                if event_type is None:
                    self._wildcard_subscribers.append(fn)
                else:
                    self._subscribers[event_type].append(fn)
            return fn
        
        if handler is not None:
            return decorator(handler)
        return decorator
    
    def unsubscribe(
        self,
        event_type: type[Event] | None,
        handler: EventHandler,
    ) -> bool:
        """Unsubscribe a handler from events.
        
        Args:
            event_type: Type of events (None for wildcard)
            handler: Handler function to remove
        
        Returns:
            True if handler was found and removed
        """
        with self._lock:
            if event_type is None:
                if handler in self._wildcard_subscribers:
                    self._wildcard_subscribers.remove(handler)
                    return True
            else:
                if handler in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(handler)
                    return True
        return False
    
    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers.
        
        This method is thread-safe and synchronous (blocks until handlers complete).
        
        Args:
            event: The event to publish
        """
        with self._lock:
            # Add to history
            self._history.append(event)
            if len(self._history) > self._history_size:
                self._history = self._history[-self._history_size:]
            
            # Get relevant handlers
            handlers: list[EventHandler] = []
            handlers.extend(self._wildcard_subscribers)
            handlers.extend(self._subscribers.get(type(event), []))
        
        # Call handlers outside lock to prevent deadlocks
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                self._logger.error(f"Event handler error: {e}", exc_info=True)
    
    def publish_async(self, event: Event) -> None:
        """Queue an event for async processing.
        
        Events are processed in order by a background thread.
        Call start_async() to begin processing.
        
        Args:
            event: The event to queue
        """
        self._queue.put(event)
    
    def start_async(self) -> None:
        """Start the async event processor thread."""
        if self._processing:
            return
        
        self._processing = True
        self._processor_thread = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="event-bus-processor",
        )
        self._processor_thread.start()
    
    def stop_async(self, timeout: float = 5.0) -> None:
        """Stop the async event processor.
        
        Args:
            timeout: Seconds to wait for processing to complete
        """
        self._processing = False
        if self._processor_thread and self._processor_thread.is_alive():
            self._processor_thread.join(timeout=timeout)
    
    def _process_queue(self) -> None:
        """Background thread for processing async events."""
        while self._processing:
            try:
                event = self._queue.get(timeout=0.1)
                self.publish(event)
                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self._logger.error(f"Queue processing error: {e}", exc_info=True)
    
    def get_history(
        self,
        event_type: type[Event] | None = None,
        limit: int | None = None,
        since: datetime | None = None,
        source_filter: str | None = None,
        level_filter: LogLevel | None = None,
    ) -> list[Event]:
        """Get events from history with optional filtering.
        
        Args:
            event_type: Filter by event type
            limit: Maximum number of events to return
            since: Only events after this timestamp
            source_filter: For LogEvents, filter by source
            level_filter: For LogEvents, filter by level
        
        Returns:
            List of matching events (newest first)
        """
        with self._lock:
            events = list(reversed(self._history))
        
        # Apply filters
        if event_type:
            events = [e for e in events if isinstance(e, event_type)]
        
        if since:
            events = [e for e in events if e.timestamp >= since]
        
        if source_filter:
            events = [
                e for e in events
                if isinstance(e, LogEvent) and source_filter.lower() in e.source.lower()
            ]
        
        if level_filter:
            events = [
                e for e in events
                if isinstance(e, LogEvent) and e.level == level_filter
            ]
        
        if limit:
            events = events[:limit]
        
        return events
    
    def get_log_history(
        self,
        limit: int = 100,
        level: LogLevel | None = None,
        source: str | None = None,
    ) -> list[LogEvent]:
        """Get log events from history.
        
        Args:
            limit: Maximum number of logs to return
            level: Filter by log level
            source: Filter by source
        
        Returns:
            List of log events (newest first)
        """
        return self.get_history(
            event_type=LogEvent,
            limit=limit,
            level_filter=level,
            source_filter=source,
        )
    
    def clear_history(self) -> None:
        """Clear the event history buffer."""
        with self._lock:
            self._history.clear()
    
    # Convenience methods for common events
    
    def log(
        self,
        level: LogLevel,
        source: str,
        message: str,
        work_unit_id: str | None = None,
        **details,
    ) -> None:
        """Publish a log event."""
        event = LogEvent(
            level=level,
            source=source,
            message=message,
            work_unit_id=work_unit_id,
            details=details,
        )
        self.publish(event)
    
    def log_debug(self, source: str, message: str, **kwargs) -> None:
        self.log(LogLevel.DEBUG, source, message, **kwargs)
    
    def log_info(self, source: str, message: str, **kwargs) -> None:
        self.log(LogLevel.INFO, source, message, **kwargs)
    
    def log_warn(self, source: str, message: str, **kwargs) -> None:
        self.log(LogLevel.WARN, source, message, **kwargs)
    
    def log_error(self, source: str, message: str, **kwargs) -> None:
        self.log(LogLevel.ERROR, source, message, **kwargs)
    
    def update_status(
        self,
        work_unit_id: str,
        status: str,
        progress: float | None = None,
        **metrics,
    ) -> None:
        """Publish a status event."""
        event = StatusEvent(
            work_unit_id=work_unit_id,
            status=status,
            progress=progress,
            metrics=metrics,
        )
        self.publish(event)
    
    def send_command(
        self,
        command: CommandType,
        work_unit_id: str | None = None,
        **payload,
    ) -> None:
        """Publish a command event."""
        event = CommandEvent(
            command=command,
            work_unit_id=work_unit_id,
            payload=payload,
        )
        self.publish(event)


# Global event bus instance
_global_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus


def reset_event_bus() -> None:
    """Reset the global event bus (for testing)."""
    global _global_bus
    if _global_bus:
        _global_bus.stop_async()
    _global_bus = None
