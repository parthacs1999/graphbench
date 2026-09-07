from collections.abc import Callable
from statistics import mean, median
from time import perf_counter
from typing import Any


def percentile(values: list[float], percentage: float) -> float:
    if not values:
        raise ValueError("values cannot be empty")

    if not 0 <= percentage <= 1:
        raise ValueError("percentage must be between 0 and 1")

    sorted_values = sorted(values)
    index = round((len(sorted_values) - 1) * percentage)

    return sorted_values[index]


def measure_operation(
    operation: Callable[[], Any],
    repetitions: int = 20,
    warmup_runs: int = 3,
) -> dict:
    if repetitions <= 0:
        raise ValueError("repetitions must be greater than zero")

    if warmup_runs < 0:
        raise ValueError("warmup_runs cannot be negative")

    for _ in range(warmup_runs):
        operation()

    durations_ms = []
    result = None

    for _ in range(repetitions):
        start_time = perf_counter()

        result = operation()

        end_time = perf_counter()

        duration_ms = (end_time - start_time) * 1000
        durations_ms.append(duration_ms)

    average_duration = mean(durations_ms)

    return {
        "result": result,
        "repetitions": repetitions,
        "mean_ms": average_duration,
        "median_ms": median(durations_ms),
        "minimum_ms": min(durations_ms),
        "maximum_ms": max(durations_ms),
        "p95_ms": percentile(durations_ms, 0.95),
        "p99_ms": percentile(durations_ms, 0.99),
        "throughput_per_second": (
            1000 / average_duration if average_duration > 0 else float("inf")
        ),
        "durations_ms": durations_ms,
    }
