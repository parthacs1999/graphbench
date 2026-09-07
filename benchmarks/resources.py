import os
import threading
from collections.abc import Callable
from time import perf_counter
from typing import Any

import psutil

BYTES_PER_MEGABYTE = 1024 * 1024


def measure_resources(
    operation: Callable[[], Any],
    sampling_interval: float = 0.001,
) -> dict:
    process = psutil.Process(os.getpid())

    memory_before = process.memory_info().rss

    cpu_before = process.cpu_times()
    cpu_time_before = cpu_before.user + cpu_before.system

    peak_memory = memory_before
    stop_sampling = threading.Event()

    def sample_memory() -> None:
        nonlocal peak_memory

        while not stop_sampling.wait(sampling_interval):
            current_memory = process.memory_info().rss
            peak_memory = max(peak_memory, current_memory)

    sampling_thread = threading.Thread(
        target=sample_memory,
        daemon=True,
    )

    sampling_thread.start()

    start_time = perf_counter()

    try:
        result = operation()
    finally:
        elapsed_seconds = perf_counter() - start_time

        stop_sampling.set()
        sampling_thread.join()

    memory_after = process.memory_info().rss
    peak_memory = max(peak_memory, memory_after)

    cpu_after = process.cpu_times()
    cpu_time_after = cpu_after.user + cpu_after.system
    cpu_seconds = cpu_time_after - cpu_time_before

    cpu_utilization = (
        (cpu_seconds / elapsed_seconds) * 100 if elapsed_seconds > 0 else 0
    )

    return {
        "result": result,
        "elapsed_ms": elapsed_seconds * 1000,
        "memory_before_mb": (memory_before / BYTES_PER_MEGABYTE),
        "memory_after_mb": (memory_after / BYTES_PER_MEGABYTE),
        "peak_memory_mb": (peak_memory / BYTES_PER_MEGABYTE),
        "additional_peak_memory_mb": (
            max(0, peak_memory - memory_before) / BYTES_PER_MEGABYTE
        ),
        "cpu_seconds": cpu_seconds,
        "cpu_utilization_percent": cpu_utilization,
    }
