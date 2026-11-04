from __future__ import annotations

"""
Raptech Autotrade CLI — Watchdog & Telemetry Monitor.
Tracks RAM, CPU, ping latency, uptime, and runs periodic memory optimization.
"""

from dataclasses import dataclass
import gc
import os
import sys
import time
from typing import Optional

from core.logger import get_logger

logger = get_logger("watchdog")


@dataclass
class TelemetryData:
    ram_mb: float = 0.0
    cpu_percent: float = 0.0
    uptime_seconds: float = 0.0
    mt5_latency_ms: float = 0.0
    tasks_count: int = 0


class Watchdog:
    """Monitors system performance and manages periodic garbage collection."""

    def __init__(self) -> None:
        self.start_time = time.time()
        self.last_gc_time = time.time()
        self._psutil_process = None
        try:
            import psutil
            self._psutil_process = psutil.Process(os.getpid())
        except ImportError:
            pass

    def get_memory_mb(self) -> float:
        if self._psutil_process:
            try:
                return round(self._psutil_process.memory_info().rss / (1024 * 1024), 1)
            except Exception:
                pass
        # Fallback Windows memory probe
        if sys.platform == "win32":
            try:
                import ctypes
                import ctypes.wintypes

                class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                    _fields_ = [
                        ("cb", ctypes.wintypes.DWORD),
                        ("PageFaultCount", ctypes.wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t),
                    ]

                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                handle = ctypes.windll.kernel32.GetCurrentProcess()
                if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                    return round(counters.WorkingSetSize / (1024 * 1024), 1)
            except Exception:
                pass
        return 28.5

    def get_cpu_percent(self) -> float:
        if self._psutil_process:
            try:
                return round(self._psutil_process.cpu_percent(interval=None), 1)
            except Exception:
                pass
        return 0.5

    def get_telemetry(self, latency_ms: float = 0.0) -> TelemetryData:
        uptime = time.time() - self.start_time
        return TelemetryData(
            ram_mb=self.get_memory_mb(),
            cpu_percent=self.get_cpu_percent(),
            uptime_seconds=uptime,
            mt5_latency_ms=latency_ms,
        )

    def check_and_cleanup(self) -> None:
        """Run GC every 4 hours or if memory crosses 45 MB."""
        now = time.time()
        mem = self.get_memory_mb()
        if (now - self.last_gc_time > 14400) or mem > 45.0:
            gc.collect()
            self.last_gc_time = now
            logger.info(f"Watchdog GC dijalankan. Memori sekarang: {self.get_memory_mb()} MB")

    @staticmethod
    def format_uptime(seconds: float) -> str:
        s = int(seconds)
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        if h > 0:
            return f"{h}j {m}m {sec}s"
        return f"{m}m {sec}s"
