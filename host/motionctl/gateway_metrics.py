"""有界网关统计，区分逻辑请求、底层发送和安全重试。"""

from __future__ import annotations

import statistics
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field

from .metrics import percentile


@dataclass
class GatewayCounters:
    device_frames: int = 0
    motion_published: int = 0
    health_published: int = 0
    mqtt_messages_published: int = 0
    telemetry_dropped: int = 0
    logical_requests: int = 0
    transport_attempts: int = 0
    safe_retries: int = 0
    command_success: int = 0
    command_errors: int = 0
    duplicate_commands: int = 0
    expired_commands: int = 0
    retained_rejected: int = 0
    mqtt_reconnects: int = 0
    serial_reconnects: int = 0
    command_queue_high_water: int = 0


class GatewayMetrics:
    def __init__(self, latency_capacity: int = 4096) -> None:
        self.started_monotonic = time.monotonic()
        self.counters = GatewayCounters()
        self._processing_ms = deque(maxlen=latency_capacity)
        self._command_ms = deque(maxlen=latency_capacity)
        self._lock = threading.Lock()

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            setattr(self.counters, name, getattr(self.counters, name) + amount)

    def high_water(self, name: str, value: int) -> None:
        with self._lock:
            setattr(self.counters, name, max(getattr(self.counters, name), value))

    def record_processing(self, value_ms: float) -> None:
        with self._lock: self._processing_ms.append(value_ms)

    def record_command(self, value_ms: float) -> None:
        with self._lock: self._command_ms.append(value_ms)

    @staticmethod
    def _latency(values) -> dict:
        rows = list(values)
        return {"count": len(rows), "mean": statistics.fmean(rows) if rows else None,
                "p50": percentile(rows, 50), "p95": percentile(rows, 95),
                "max": max(rows) if rows else None}

    def snapshot(self) -> dict:
        with self._lock:
            return {"uptime_s": time.monotonic() - self.started_monotonic,
                    **asdict(self.counters),
                    "gateway_processing_ms": self._latency(self._processing_ms),
                    "command_round_trip_ms": self._latency(self._command_ms)}
