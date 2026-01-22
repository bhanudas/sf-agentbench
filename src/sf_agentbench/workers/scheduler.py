"""Priority scheduler with resource-aware scheduling.

Schedules work units based on priority, type, and resource availability.
"""

import threading
import queue
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator, Callable
import logging

from sf_agentbench.domain.models import (
    WorkUnit,
    WorkUnitStatus,
    Test,
    TestType,
    Benchmark,
    Agent,
)
from sf_agentbench.events import EventBus, get_event_bus


@dataclass
class SchedulerConfig:
    """Configuration for the scheduler."""
    
    max_concurrent: int = 8  # Total parallel work units
    qa_slots: int = 6  # Slots for Q&A tests
    coding_slots: int = 2  # Slots for coding tests
    
    # Priority weights
    priority_qa: int = 0  # Default priority for Q&A
    priority_coding: int = 10  # Higher priority for coding (they take longer)
    
    # Resource constraints
    max_scratch_orgs: int = 2


@dataclass
class ScratchOrg:
    """A scratch org resource."""
    
    username: str
    org_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    in_use: bool = False
    work_unit_id: str | None = None


class ScratchOrgPool:
    """Pool of pre-warmed scratch orgs for coding tests.
    
    Manages the lifecycle of scratch orgs to reduce wait times.
    """
    
    def __init__(
        self,
        pool_size: int = 2,
        devhub_username: str = "",
        logger: logging.Logger | None = None,
    ):
        """Initialize the scratch org pool.
        
        Args:
            pool_size: Number of orgs to maintain
            devhub_username: DevHub for creating orgs
            logger: Logger instance
        """
        self.pool_size = pool_size
        self.devhub_username = devhub_username
        self.logger = logger or logging.getLogger("scratch_org_pool")
        
        self._orgs: list[ScratchOrg] = []
        self._lock = threading.RLock()
        self._available = threading.Condition(self._lock)
    
    @property
    def available_count(self) -> int:
        """Number of available (not in use) orgs."""
        with self._lock:
            return sum(1 for org in self._orgs if not org.in_use)
    
    @property
    def in_use_count(self) -> int:
        """Number of orgs currently in use."""
        with self._lock:
            return sum(1 for org in self._orgs if org.in_use)
    
    @property
    def total_count(self) -> int:
        """Total number of orgs in pool."""
        with self._lock:
            return len(self._orgs)
    
    def acquire(self, work_unit_id: str, timeout: float = 300.0) -> ScratchOrg | None:
        """Acquire a scratch org from the pool.
        
        Args:
            work_unit_id: ID of the work unit using the org
            timeout: Seconds to wait for an available org
        
        Returns:
            A scratch org, or None if timed out
        """
        with self._available:
            # Wait for an available org
            deadline = datetime.utcnow().timestamp() + timeout
            
            while True:
                # Check for available org
                for org in self._orgs:
                    if not org.in_use:
                        org.in_use = True
                        org.work_unit_id = work_unit_id
                        self.logger.debug(f"Acquired org {org.username} for {work_unit_id}")
                        return org
                
                # No org available, wait or timeout
                remaining = deadline - datetime.utcnow().timestamp()
                if remaining <= 0:
                    self.logger.warning(f"Timeout waiting for scratch org")
                    return None
                
                self._available.wait(timeout=min(remaining, 1.0))
    
    def release(self, org: ScratchOrg) -> None:
        """Release a scratch org back to the pool.
        
        Args:
            org: The org to release
        """
        with self._available:
            org.in_use = False
            org.work_unit_id = None
            self.logger.debug(f"Released org {org.username}")
            self._available.notify()
    
    def add_org(self, username: str, org_id: str) -> ScratchOrg:
        """Add an org to the pool.
        
        Args:
            username: Org username
            org_id: Org ID
        
        Returns:
            The added org
        """
        with self._lock:
            org = ScratchOrg(username=username, org_id=org_id)
            self._orgs.append(org)
            self.logger.info(f"Added org to pool: {username}")
            return org
    
    def remove_org(self, org: ScratchOrg) -> None:
        """Remove an org from the pool.
        
        Args:
            org: The org to remove
        """
        with self._lock:
            if org in self._orgs:
                self._orgs.remove(org)
                self.logger.info(f"Removed org from pool: {org.username}")
    
    def get_status(self) -> dict:
        """Get pool status."""
        with self._lock:
            return {
                "pool_size": self.pool_size,
                "total": self.total_count,
                "available": self.available_count,
                "in_use": self.in_use_count,
                "orgs": [
                    {
                        "username": org.username,
                        "in_use": org.in_use,
                        "work_unit_id": org.work_unit_id,
                    }
                    for org in self._orgs
                ],
            }


class Scheduler:
    """Resource-aware scheduler for work units.
    
    Schedules work units based on:
    - Priority (higher = more urgent)
    - Test type (Q&A vs Coding)
    - Resource availability (scratch orgs)
    """
    
    def __init__(
        self,
        config: SchedulerConfig | None = None,
        event_bus: EventBus | None = None,
        scratch_org_pool: ScratchOrgPool | None = None,
        logger: logging.Logger | None = None,
    ):
        """Initialize the scheduler.
        
        Args:
            config: Scheduler configuration
            event_bus: Event bus for communication
            scratch_org_pool: Pool of scratch orgs
            logger: Logger instance
        """
        self.config = config or SchedulerConfig()
        self.event_bus = event_bus or get_event_bus()
        self.scratch_org_pool = scratch_org_pool
        self.logger = logger or logging.getLogger("scheduler")
        
        self._pending: list[WorkUnit] = []
        self._running_qa: list[WorkUnit] = []
        self._running_coding: list[WorkUnit] = []
        
        self._lock = threading.RLock()
    
    def schedule(self, work_units: list[WorkUnit]) -> None:
        """Add work units to be scheduled.
        
        Args:
            work_units: Work units to schedule
        """
        with self._lock:
            for work_unit in work_units:
                # Set default priority based on type
                if work_unit.priority == 0:
                    if work_unit.test.type == TestType.QA:
                        work_unit.priority = self.config.priority_qa
                    else:
                        work_unit.priority = self.config.priority_coding
                
                self._pending.append(work_unit)
            
            # Sort by priority (descending)
            self._pending.sort(key=lambda w: -w.priority)
    
    def get_next(self) -> WorkUnit | None:
        """Get the next work unit to execute.
        
        Returns:
            Next work unit, or None if none available
        """
        with self._lock:
            if not self._pending:
                return None
            
            # Check resource constraints
            for i, work_unit in enumerate(self._pending):
                if self._can_run(work_unit):
                    # Remove from pending and mark as running
                    self._pending.pop(i)
                    self._mark_running(work_unit)
                    return work_unit
            
            return None
    
    def mark_complete(self, work_unit: WorkUnit) -> None:
        """Mark a work unit as complete and free resources.
        
        Args:
            work_unit: The completed work unit
        """
        with self._lock:
            if work_unit.test.type == TestType.QA:
                if work_unit in self._running_qa:
                    self._running_qa.remove(work_unit)
            else:
                if work_unit in self._running_coding:
                    self._running_coding.remove(work_unit)
    
    def _can_run(self, work_unit: WorkUnit) -> bool:
        """Check if a work unit can be run given current resources."""
        if work_unit.test.type == TestType.QA:
            # Check Q&A slot limit
            return len(self._running_qa) < self.config.qa_slots
        else:
            # Check coding slot limit and scratch org availability
            if len(self._running_coding) >= self.config.coding_slots:
                return False
            if self.scratch_org_pool:
                return self.scratch_org_pool.available_count > 0
            return True
    
    def _mark_running(self, work_unit: WorkUnit) -> None:
        """Mark a work unit as running."""
        if work_unit.test.type == TestType.QA:
            self._running_qa.append(work_unit)
        else:
            self._running_coding.append(work_unit)
    
    def get_status(self) -> dict:
        """Get scheduler status."""
        with self._lock:
            return {
                "pending": len(self._pending),
                "running_qa": len(self._running_qa),
                "running_coding": len(self._running_coding),
                "qa_slots": f"{len(self._running_qa)}/{self.config.qa_slots}",
                "coding_slots": f"{len(self._running_coding)}/{self.config.coding_slots}",
            }
    
    def create_work_units(
        self,
        benchmark: Benchmark,
        agents: list[Agent],
    ) -> list[WorkUnit]:
        """Create work units for a benchmark.
        
        Creates one work unit per (test, agent) combination.
        
        Args:
            benchmark: The benchmark to run
            agents: Agents to test
        
        Returns:
            List of work units
        """
        work_units = []
        
        for test in benchmark.tests:
            for agent in agents:
                work_unit = WorkUnit(
                    id="",  # Will be auto-generated
                    test=test,
                    agent=agent,
                )
                work_units.append(work_unit)
        
        return work_units
