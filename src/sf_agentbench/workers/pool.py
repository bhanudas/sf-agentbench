"""Worker pool with configurable concurrency.

Manages a pool of workers for parallel execution of work units.
"""

import threading
import queue
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable
import logging

from sf_agentbench.domain.models import WorkUnit, WorkUnitStatus
from sf_agentbench.events import EventBus, MetricsEvent, get_event_bus
from sf_agentbench.workers.base import Worker, WorkerState, WorkUnitExecutor


@dataclass
class PoolConfig:
    """Configuration for the worker pool."""
    
    max_workers: int = 4  # Total number of workers
    qa_workers: int = 4  # Workers for Q&A tests
    coding_workers: int = 2  # Workers for coding tests (limited by scratch orgs)
    scratch_org_pool_size: int = 2  # Pre-warmed scratch orgs
    
    def __post_init__(self):
        # Ensure coding_workers doesn't exceed scratch_org_pool_size
        if self.coding_workers > self.scratch_org_pool_size:
            self.coding_workers = self.scratch_org_pool_size


class WorkerPool:
    """Pool of workers for parallel execution.
    
    Features:
    - Dynamic worker scaling
    - Work unit queuing
    - Priority-based scheduling
    - Metrics tracking
    """
    
    def __init__(
        self,
        config: PoolConfig | None = None,
        event_bus: EventBus | None = None,
        executor: WorkUnitExecutor | None = None,
        logger: logging.Logger | None = None,
    ):
        """Initialize the worker pool.
        
        Args:
            config: Pool configuration
            event_bus: Event bus for communication
            executor: Default executor for work units
            logger: Logger instance
        """
        self.config = config or PoolConfig()
        self.event_bus = event_bus or get_event_bus()
        self.default_executor = executor
        self.logger = logger or logging.getLogger("worker_pool")
        
        self._workers: list[Worker] = []
        self._work_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._active_work_units: dict[str, WorkUnit] = {}
        self._completed_work_units: list[WorkUnit] = []
        
        self._lock = threading.RLock()
        self._running = False
        self._dispatcher_thread: threading.Thread | None = None
        
        # Metrics
        self._total_submitted = 0
        self._total_completed = 0
        self._total_failed = 0
        self._started_at: datetime | None = None
    
    @property
    def worker_count(self) -> int:
        """Number of workers in the pool."""
        return len(self._workers)
    
    @property
    def active_workers(self) -> int:
        """Number of workers currently processing work."""
        return sum(1 for w in self._workers if w.is_busy)
    
    @property
    def idle_workers(self) -> int:
        """Number of idle workers."""
        return self.worker_count - self.active_workers
    
    @property
    def queue_size(self) -> int:
        """Number of work units waiting in queue."""
        return self._work_queue.qsize()
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    def start(self) -> None:
        """Start the worker pool."""
        if self._running:
            return
        
        self._running = True
        self._started_at = datetime.utcnow()
        
        # Create workers
        for i in range(self.config.max_workers):
            worker = Worker(
                worker_id=f"worker-{i}",
                event_bus=self.event_bus,
                executor=self._create_worker_executor(),
                logger=self.logger,
            )
            worker.start()
            self._workers.append(worker)
        
        # Start dispatcher thread
        self._dispatcher_thread = threading.Thread(
            target=self._dispatch_loop,
            daemon=True,
            name="pool-dispatcher",
        )
        self._dispatcher_thread.start()
        
        self.event_bus.log_info(
            "pool",
            f"Worker pool started with {self.config.max_workers} workers",
        )
    
    def stop(self, timeout: float = 10.0) -> None:
        """Stop the worker pool.
        
        Args:
            timeout: Seconds to wait for workers to stop
        """
        if not self._running:
            return
        
        self._running = False
        
        # Wait for dispatcher to stop
        if self._dispatcher_thread and self._dispatcher_thread.is_alive():
            self._dispatcher_thread.join(timeout=1.0)
        
        # Stop all workers
        for worker in self._workers:
            worker.stop(timeout=timeout / len(self._workers))
        
        self._workers.clear()
        
        self.event_bus.log_info("pool", "Worker pool stopped")
    
    def submit(self, work_unit: WorkUnit, priority: int = 0) -> None:
        """Submit a work unit for processing.
        
        Args:
            work_unit: The work unit to process
            priority: Higher priority = processed first (negative = low priority)
        """
        with self._lock:
            self._total_submitted += 1
            work_unit.priority = priority
            
            # Use negative priority so higher priority comes first in the queue
            self._work_queue.put((-priority, datetime.utcnow(), work_unit))
        
        self.event_bus.log_debug(
            "pool",
            f"Submitted work unit: {work_unit.id} (priority: {priority})",
            work_unit_id=work_unit.id,
        )
    
    def submit_batch(
        self,
        work_units: list[WorkUnit],
        priority: int = 0,
    ) -> None:
        """Submit multiple work units.
        
        Args:
            work_units: List of work units to process
            priority: Priority for all work units
        """
        for work_unit in work_units:
            self.submit(work_unit, priority)
    
    def wait_for_completion(self, timeout: float | None = None) -> bool:
        """Wait for all submitted work to complete.
        
        Args:
            timeout: Maximum seconds to wait (None = wait forever)
        
        Returns:
            True if all work completed, False if timed out
        """
        start = datetime.utcnow()
        
        while True:
            with self._lock:
                pending = self._work_queue.qsize() + len(self._active_work_units)
                if pending == 0:
                    return True
            
            if timeout is not None:
                elapsed = (datetime.utcnow() - start).total_seconds()
                if elapsed >= timeout:
                    return False
            
            threading.Event().wait(0.1)
    
    def cancel_all(self) -> int:
        """Cancel all pending and running work units.
        
        Returns:
            Number of work units cancelled
        """
        cancelled = 0
        
        with self._lock:
            # Clear queue
            while not self._work_queue.empty():
                try:
                    _, _, work_unit = self._work_queue.get_nowait()
                    work_unit.cancel()
                    cancelled += 1
                except queue.Empty:
                    break
            
            # Cancel active work
            for worker in self._workers:
                if worker.current_work_unit:
                    worker.cancel_current()
                    cancelled += 1
        
        return cancelled
    
    def pause_all(self) -> None:
        """Pause all running work units."""
        for worker in self._workers:
            worker.pause()
    
    def resume_all(self) -> None:
        """Resume all paused work units."""
        for worker in self._workers:
            worker.resume()
    
    def get_status(self) -> dict:
        """Get current pool status."""
        with self._lock:
            return {
                "running": self._running,
                "workers_total": self.worker_count,
                "workers_active": self.active_workers,
                "workers_idle": self.idle_workers,
                "queue_size": self.queue_size,
                "total_submitted": self._total_submitted,
                "total_completed": self._total_completed,
                "total_failed": self._total_failed,
                "active_work_units": list(self._active_work_units.keys()),
            }
    
    def get_metrics_event(self) -> MetricsEvent:
        """Get a metrics event with current status."""
        with self._lock:
            return MetricsEvent(
                total_work_units=self._total_submitted,
                completed_work_units=self._total_completed,
                failed_work_units=self._total_failed,
                running_work_units=len(self._active_work_units),
                pending_work_units=self.queue_size,
                workers_active=self.active_workers,
                workers_total=self.worker_count,
            )
    
    def _dispatch_loop(self) -> None:
        """Dispatcher loop that assigns work to idle workers."""
        while self._running:
            try:
                # Find an idle worker
                idle_worker = None
                for worker in self._workers:
                    if worker.state == WorkerState.IDLE:
                        idle_worker = worker
                        break
                
                if idle_worker is None:
                    threading.Event().wait(0.1)
                    continue
                
                # Get next work unit
                try:
                    _, _, work_unit = self._work_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Assign to worker
                with self._lock:
                    self._active_work_units[work_unit.id] = work_unit
                
                idle_worker.submit(work_unit)
                self._work_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Dispatch error: {e}", exc_info=True)
    
    def _create_worker_executor(self) -> WorkUnitExecutor:
        """Create an executor that wraps the default executor with tracking."""
        def executor(context):
            work_unit = context.work_unit
            
            try:
                # Call the actual executor
                if self.default_executor:
                    result = self.default_executor(context)
                else:
                    from sf_agentbench.domain.models import Result
                    result = Result(score=1.0)
                
                with self._lock:
                    if work_unit.status == WorkUnitStatus.COMPLETED:
                        self._total_completed += 1
                    elif work_unit.status == WorkUnitStatus.FAILED:
                        self._total_failed += 1
                    
                    if work_unit.id in self._active_work_units:
                        del self._active_work_units[work_unit.id]
                    
                    self._completed_work_units.append(work_unit)
                
                return result
                
            except Exception as e:
                with self._lock:
                    self._total_failed += 1
                    if work_unit.id in self._active_work_units:
                        del self._active_work_units[work_unit.id]
                raise
        
        return executor
