"""Performance metrics for benchmark runs.

Provides unified metrics tracking for latency, throughput, and accuracy.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import statistics


@dataclass
class LatencyMetrics:
    """Latency measurements for operations."""
    
    samples: list[float] = field(default_factory=list)
    
    def add(self, duration_seconds: float) -> None:
        """Add a latency sample."""
        self.samples.append(duration_seconds)
    
    @property
    def count(self) -> int:
        return len(self.samples)
    
    @property
    def total(self) -> float:
        return sum(self.samples)
    
    @property
    def mean(self) -> float:
        if not self.samples:
            return 0.0
        return statistics.mean(self.samples)
    
    @property
    def median(self) -> float:
        if not self.samples:
            return 0.0
        return statistics.median(self.samples)
    
    @property
    def min(self) -> float:
        if not self.samples:
            return 0.0
        return min(self.samples)
    
    @property
    def max(self) -> float:
        if not self.samples:
            return 0.0
        return max(self.samples)
    
    @property
    def stdev(self) -> float:
        if len(self.samples) < 2:
            return 0.0
        return statistics.stdev(self.samples)
    
    @property
    def p95(self) -> float:
        """95th percentile latency."""
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    @property
    def p99(self) -> float:
        """99th percentile latency."""
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * 0.99)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    def to_dict(self) -> dict[str, float]:
        return {
            "count": self.count,
            "total": self.total,
            "mean": self.mean,
            "median": self.median,
            "min": self.min,
            "max": self.max,
            "stdev": self.stdev,
            "p95": self.p95,
            "p99": self.p99,
        }


@dataclass
class AccuracyMetrics:
    """Accuracy measurements for test results."""
    
    correct: int = 0
    incorrect: int = 0
    skipped: int = 0
    
    def add_correct(self) -> None:
        self.correct += 1
    
    def add_incorrect(self) -> None:
        self.incorrect += 1
    
    def add_skipped(self) -> None:
        self.skipped += 1
    
    @property
    def total(self) -> int:
        return self.correct + self.incorrect + self.skipped
    
    @property
    def attempted(self) -> int:
        return self.correct + self.incorrect
    
    @property
    def accuracy(self) -> float:
        if self.attempted == 0:
            return 0.0
        return self.correct / self.attempted
    
    @property
    def accuracy_percent(self) -> float:
        return self.accuracy * 100
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "correct": self.correct,
            "incorrect": self.incorrect,
            "skipped": self.skipped,
            "total": self.total,
            "accuracy": self.accuracy,
            "accuracy_percent": self.accuracy_percent,
        }


@dataclass
class ThroughputMetrics:
    """Throughput measurements."""
    
    items_processed: int = 0
    duration_seconds: float = 0.0
    
    def add(self, items: int, duration: float) -> None:
        self.items_processed += items
        self.duration_seconds += duration
    
    @property
    def items_per_second(self) -> float:
        if self.duration_seconds == 0:
            return 0.0
        return self.items_processed / self.duration_seconds
    
    @property
    def seconds_per_item(self) -> float:
        if self.items_processed == 0:
            return 0.0
        return self.duration_seconds / self.items_processed
    
    def to_dict(self) -> dict[str, float]:
        return {
            "items_processed": self.items_processed,
            "duration_seconds": self.duration_seconds,
            "items_per_second": self.items_per_second,
            "seconds_per_item": self.seconds_per_item,
        }


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics for a benchmark run."""
    
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    
    # Component metrics
    latency: LatencyMetrics = field(default_factory=LatencyMetrics)
    accuracy: AccuracyMetrics = field(default_factory=AccuracyMetrics)
    throughput: ThroughputMetrics = field(default_factory=ThroughputMetrics)
    
    # Breakdown by category
    by_domain: dict[str, AccuracyMetrics] = field(default_factory=dict)
    by_tier: dict[str, AccuracyMetrics] = field(default_factory=dict)
    
    def complete(self) -> None:
        """Mark metrics as complete."""
        self.completed_at = datetime.utcnow()
    
    @property
    def duration_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()
    
    def add_result(
        self,
        correct: bool,
        duration: float,
        domain: str | None = None,
        tier: str | None = None,
    ) -> None:
        """Add a test result to metrics."""
        # Update latency
        self.latency.add(duration)
        
        # Update accuracy
        if correct:
            self.accuracy.add_correct()
        else:
            self.accuracy.add_incorrect()
        
        # Update throughput
        self.throughput.add(1, duration)
        
        # Update domain breakdown
        if domain:
            if domain not in self.by_domain:
                self.by_domain[domain] = AccuracyMetrics()
            if correct:
                self.by_domain[domain].add_correct()
            else:
                self.by_domain[domain].add_incorrect()
        
        # Update tier breakdown
        if tier:
            if tier not in self.by_tier:
                self.by_tier[tier] = AccuracyMetrics()
            if correct:
                self.by_tier[tier].add_correct()
            else:
                self.by_tier[tier].add_incorrect()
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "latency": self.latency.to_dict(),
            "accuracy": self.accuracy.to_dict(),
            "throughput": self.throughput.to_dict(),
            "by_domain": {k: v.to_dict() for k, v in self.by_domain.items()},
            "by_tier": {k: v.to_dict() for k, v in self.by_tier.items()},
        }
    
    def format_summary(self) -> str:
        """Format a human-readable summary."""
        lines = [
            "Performance Metrics:",
            f"  Duration: {self.duration_seconds:.1f}s",
            f"  Accuracy: {self.accuracy.correct}/{self.accuracy.total} ({self.accuracy.accuracy_percent:.1f}%)",
            f"  Throughput: {self.throughput.items_per_second:.2f} items/sec",
            f"  Latency (mean): {self.latency.mean:.2f}s",
            f"  Latency (p95): {self.latency.p95:.2f}s",
        ]
        
        if self.by_domain:
            lines.append("  By Domain:")
            for domain, metrics in sorted(self.by_domain.items()):
                lines.append(
                    f"    {domain}: {metrics.correct}/{metrics.total} ({metrics.accuracy_percent:.1f}%)"
                )
        
        return "\n".join(lines)
