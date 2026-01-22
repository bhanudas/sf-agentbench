"""Worker base class for executing work units.

Workers are the execution units that process work units from the queue.
"""

import threading
import queue
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Any
import uuid

from sf_agentbench.domain.models import WorkUnit, WorkUnitStatus, Result
from sf_agentbench.events import EventBus, LogEvent, StatusEvent, CommandEvent, CommandType


class WorkerState(str, Enum):
    """State of a worker."""
    
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class WorkerContext:
    """Context provided to work unit executors."""
    
    worker_id: str
    work_unit: WorkUnit
    event_bus: EventBus
    logger: logging.Logger
    scratch_org: str | None = None
    
    # Control signals
    should_pause: threading.Event = field(default_factory=threading.Event)
    should_cancel: threading.Event = field(default_factory=threading.Event)
    injected_prompts: queue.Queue = field(default_factory=queue.Queue)
    
    def log_info(self, message: str) -> None:
        """Log an info message."""
        self.event_bus.log_info(
            source=self.worker_id,
            message=message,
            work_unit_id=self.work_unit.id,
        )
    
    def log_error(self, message: str) -> None:
        """Log an error message."""
        self.event_bus.log_error(
            source=self.worker_id,
            message=message,
            work_unit_id=self.work_unit.id,
        )
    
    def update_status(self, status: str, progress: float | None = None) -> None:
        """Update work unit status."""
        self.event_bus.update_status(
            work_unit_id=self.work_unit.id,
            status=status,
            progress=progress,
        )
    
    def check_pause(self) -> bool:
        """Check if worker should pause. Returns True if paused."""
        if self.should_pause.is_set():
            self.update_status(WorkUnitStatus.PAUSED.value)
            while self.should_pause.is_set() and not self.should_cancel.is_set():
                threading.Event().wait(0.1)
            if not self.should_cancel.is_set():
                self.update_status(WorkUnitStatus.RUNNING.value)
            return True
        return False
    
    def check_cancel(self) -> bool:
        """Check if worker should cancel."""
        return self.should_cancel.is_set()
    
    def get_injected_prompt(self, timeout: float = 0.0) -> str | None:
        """Get an injected prompt if available."""
        try:
            return self.injected_prompts.get(block=False, timeout=timeout)
        except queue.Empty:
            return None


# Type alias for executor functions
WorkUnitExecutor = Callable[[WorkerContext], Result]


class Worker:
    """A worker that processes work units from a queue.
    
    Workers run in their own thread and process work units one at a time.
    They communicate progress and status via the event bus.
    """
    
    def __init__(
        self,
        worker_id: str | None = None,
        event_bus: EventBus | None = None,
        executor: WorkUnitExecutor | None = None,
        logger: logging.Logger | None = None,
    ):
        """Initialize the worker.
        
        Args:
            worker_id: Unique identifier for this worker
            event_bus: Event bus for communication
            executor: Function to execute work units
            logger: Logger instance
        """
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:6]}"
        self.event_bus = event_bus or EventBus()
        self.executor = executor
        self.logger = logger or logging.getLogger(f"worker.{self.worker_id}")
        
        self._state = WorkerState.IDLE
        self._thread: threading.Thread | None = None
        self._work_queue: queue.Queue[WorkUnit] = queue.Queue()
        self._current_work_unit: WorkUnit | None = None
        self._current_context: WorkerContext | None = None
        
        # Control signals
        self._should_stop = threading.Event()
        self._should_pause = threading.Event()
        
        # Subscribe to command events
        self.event_bus.subscribe(CommandEvent, self._handle_command)
    
    @property
    def state(self) -> WorkerState:
        return self._state
    
    @property
    def current_work_unit(self) -> WorkUnit | None:
        return self._current_work_unit
    
    @property
    def is_busy(self) -> bool:
        return self._state == WorkerState.RUNNING
    
    def start(self) -> None:
        """Start the worker thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        
        self._should_stop.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name=self.worker_id,
        )
        self._thread.start()
        self._state = WorkerState.IDLE
        
        self.event_bus.log_info(self.worker_id, "Worker started")
    
    def stop(self, timeout: float = 5.0) -> None:
        """Stop the worker thread.
        
        Args:
            timeout: Seconds to wait for thread to stop
        """
        self._should_stop.set()
        self._state = WorkerState.STOPPING
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        
        self._state = WorkerState.STOPPED
        self.event_bus.log_info(self.worker_id, "Worker stopped")
    
    def submit(self, work_unit: WorkUnit) -> None:
        """Submit a work unit for processing.
        
        Args:
            work_unit: The work unit to process
        """
        self._work_queue.put(work_unit)
    
    def pause(self) -> None:
        """Pause the current work unit."""
        self._should_pause.set()
        if self._current_context:
            self._current_context.should_pause.set()
    
    def resume(self) -> None:
        """Resume a paused work unit."""
        self._should_pause.clear()
        if self._current_context:
            self._current_context.should_pause.clear()
    
    def cancel_current(self) -> None:
        """Cancel the current work unit."""
        if self._current_context:
            self._current_context.should_cancel.set()
    
    def inject_prompt(self, prompt: str) -> None:
        """Inject a prompt into the current work unit."""
        if self._current_context:
            self._current_context.injected_prompts.put(prompt)
    
    def _run_loop(self) -> None:
        """Main worker loop."""
        while not self._should_stop.is_set():
            try:
                # Wait for work
                work_unit = self._work_queue.get(timeout=0.5)
                
                # Process work unit
                self._process_work_unit(work_unit)
                
                self._work_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Worker loop error: {e}", exc_info=True)
    
    def _process_work_unit(self, work_unit: WorkUnit) -> None:
        """Process a single work unit."""
        self._current_work_unit = work_unit
        self._state = WorkerState.RUNNING
        
        # Create context
        self._current_context = WorkerContext(
            worker_id=self.worker_id,
            work_unit=work_unit,
            event_bus=self.event_bus,
            logger=self.logger,
        )
        
        # Mark work unit as started
        work_unit.start()
        self.event_bus.update_status(
            work_unit_id=work_unit.id,
            status=WorkUnitStatus.RUNNING.value,
        )
        
        self.event_bus.log_info(
            self.worker_id,
            f"Starting work unit: {work_unit.test.name}",
            work_unit_id=work_unit.id,
        )
        
        try:
            # Execute the work unit
            if self.executor:
                result = self.executor(self._current_context)
            else:
                # No executor, just mark as complete
                result = Result(score=1.0)
            
            # Check if cancelled
            if self._current_context.should_cancel.is_set():
                work_unit.cancel()
                self.event_bus.log_warn(
                    self.worker_id,
                    f"Work unit cancelled: {work_unit.id}",
                    work_unit_id=work_unit.id,
                )
            else:
                work_unit.complete(result)
                self.event_bus.log_info(
                    self.worker_id,
                    f"Work unit complete: {work_unit.id} (score: {result.score:.2f})",
                    work_unit_id=work_unit.id,
                )
            
        except Exception as e:
            self.logger.error(f"Work unit error: {e}", exc_info=True)
            work_unit.fail(str(e))
            self.event_bus.log_error(
                self.worker_id,
                f"Work unit failed: {work_unit.id} - {e}",
                work_unit_id=work_unit.id,
            )
        
        finally:
            self.event_bus.update_status(
                work_unit_id=work_unit.id,
                status=work_unit.status.value,
            )
            self._current_work_unit = None
            self._current_context = None
            self._state = WorkerState.IDLE
    
    def _handle_command(self, event: CommandEvent) -> None:
        """Handle command events."""
        # Check if command is for this worker's current work unit
        if event.work_unit_id:
            if not self._current_work_unit:
                return
            if event.work_unit_id != self._current_work_unit.id:
                return
        
        if event.command == CommandType.PAUSE:
            self.pause()
        elif event.command == CommandType.RESUME:
            self.resume()
        elif event.command == CommandType.CANCEL:
            self.cancel_current()
        elif event.command == CommandType.INJECT_PROMPT:
            prompt = event.payload.get("prompt", "")
            if prompt:
                self.inject_prompt(prompt)
        elif event.command == CommandType.SHUTDOWN:
            self.stop()
