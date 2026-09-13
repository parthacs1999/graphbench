import csv
import gc
import math
import random
from collections.abc import Callable
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

from backends.ladybug_backend import LadybugBackend
from backends.networkx_backend import NetworkXBackend
from graph_generator import generate_edges

GRAPH_SIZES = [
    (1_000, 5_000),
    (10_000, 50_000),
    (100_000, 500_000),
]

BATCH_SIZES = [
    1,
    10,
    100,
    1_000,
]

QUERY_WARMUP_RUNS = 5
QUERY_REPETITIONS = 30
SEED = 42

RESULTS_DIRECTORY = Path("results")
RESULTS_FILE = RESULTS_DIRECTORY / "query_scalability.csv"


def timed_call(
    operation: Callable[[], Any],
) -> tuple[Any, float]:
    """
    Execute an operation and return its result together with
    elapsed wall-clock time in milliseconds.
    """
    start_time = perf_counter()
    result = operation()
    elapsed_ms = (perf_counter() - start_time) * 1000

    return result, elapsed_ms


def percentile(
    values: list[float],
    percentage: float,
) -> float:
    """
    Return the nearest-rank percentile.

    For example, percentage=0.95 returns the P95 value.
    """
    if not values:
        raise ValueError("values cannot be empty")

    if not 0 <= percentage <= 1:
        raise ValueError("percentage must be between 0 and 1")

    sorted_values = sorted(values)

    rank = math.ceil(percentage * len(sorted_values))

    index = max(0, rank - 1)

    return sorted_values[index]


def validate_graph(
    networkx_backend: NetworkXBackend,
    ladybug_backend: LadybugBackend,
    expected_nodes: int,
    expected_edges: int,
) -> None:
    """
    Validate graph counts before measuring queries.
    """
    networkx_nodes = networkx_backend.node_count()
    ladybug_nodes = ladybug_backend.node_count()

    networkx_edges = networkx_backend.edge_count()
    ladybug_edges = ladybug_backend.edge_count()

    if networkx_nodes != expected_nodes:
        raise RuntimeError(
            f"NetworkX expected {expected_nodes} nodes, " f"received {networkx_nodes}"
        )

    if ladybug_nodes != expected_nodes:
        raise RuntimeError(
            f"LadybugDB expected {expected_nodes} nodes, " f"received {ladybug_nodes}"
        )

    if networkx_edges != expected_edges:
        raise RuntimeError(
            f"NetworkX expected {expected_edges} edges, " f"received {networkx_edges}"
        )

    if ladybug_edges != expected_edges:
        raise RuntimeError(
            f"LadybugDB expected {expected_edges} edges, " f"received {ladybug_edges}"
        )


def create_query_nodes(
    number_of_nodes: int,
    batch_size: int,
    seed: int,
) -> list[int]:
    """
    Select deterministic random query nodes.
    """
    actual_batch_size = min(
        batch_size,
        number_of_nodes,
    )

    random_generator = random.Random(seed + number_of_nodes + batch_size)

    query_nodes = random_generator.sample(
        range(number_of_nodes),
        actual_batch_size,
    )

    return sorted(query_nodes)


def measure_query(
    operation: Callable[[], dict[int, list[int]]],
) -> dict:
    """
    Measure cold and warm query latency.

    The cold query is the first execution after graph construction.
    Warm measurements happen after several untimed executions.
    """
    cold_result, cold_ms = timed_call(operation)

    for _ in range(QUERY_WARMUP_RUNS):
        operation()

    warm_times = []
    final_result = None

    for _ in range(QUERY_REPETITIONS):
        final_result, elapsed_ms = timed_call(operation)
        warm_times.append(elapsed_ms)

    warm_median_ms = median(warm_times)
    warm_p95_ms = percentile(
        warm_times,
        0.95,
    )

    return {
        "cold_result": cold_result,
        "final_result": final_result,
        "cold_ms": cold_ms,
        "warm_median_ms": warm_median_ms,
        "warm_p95_ms": warm_p95_ms,
        "minimum_ms": min(warm_times),
        "maximum_ms": max(warm_times),
    }


def total_returned_neighbors(
    result: dict[int, list[int]],
) -> int:
    """
    Count all neighbor IDs returned by a batch query.
    """
    return sum(len(neighbors) for neighbors in result.values())


def winner_details(
    networkx_time: float,
    ladybug_time: float,
) -> tuple[str, float]:
    """
    Determine the faster backend and its speedup ratio.
    """
    if networkx_time <= 0 or ladybug_time <= 0:
        return "Unavailable", 0.0

    if networkx_time < ladybug_time:
        return (
            "NetworkX",
            ladybug_time / networkx_time,
        )

    if ladybug_time < networkx_time:
        return (
            "LadybugDB",
            networkx_time / ladybug_time,
        )

    return "Tie", 1.0


def save_results(results: list[dict]) -> None:
    """
    Save query scalability results to CSV.
    """
    RESULTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    with RESULTS_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=list(results[0].keys()),
        )

        writer.writeheader()
        writer.writerows(results)


def main() -> None:
    results = []

    for number_of_nodes, number_of_edges in GRAPH_SIZES:
        print()
        print("=" * 88)
        print(
            f"Preparing graph with "
            f"{number_of_nodes:,} nodes and "
            f"{number_of_edges:,} edges..."
        )

        edges = list(
            generate_edges(
                number_of_nodes=number_of_nodes,
                number_of_edges=number_of_edges,
                seed=SEED,
            )
        )

        if len(edges) != number_of_edges:
            raise RuntimeError(
                f"Generator produced {len(edges)} edges, " f"expected {number_of_edges}"
            )

        networkx_backend = NetworkXBackend()
        ladybug_backend = LadybugBackend()

        try:
            print("Building NetworkX graph...")

            networkx_backend.build_graph(
                number_of_nodes=number_of_nodes,
                edges=edges,
            )

            print("Building optimized LadybugDB graph " "and running ANALYZE...")

            ladybug_backend.build_graph(
                number_of_nodes=number_of_nodes,
                edges=edges,
            )

            validate_graph(
                networkx_backend=networkx_backend,
                ladybug_backend=ladybug_backend,
                expected_nodes=number_of_nodes,
                expected_edges=number_of_edges,
            )

            for batch_size in BATCH_SIZES:
                actual_batch_size = min(
                    batch_size,
                    number_of_nodes,
                )

                print()
                print(f"Measuring batch size " f"{actual_batch_size:,}...")

                query_nodes = create_query_nodes(
                    number_of_nodes=number_of_nodes,
                    batch_size=actual_batch_size,
                    seed=SEED,
                )

                # Alternate execution order to reduce systematic bias.
                if batch_size % 2 == 0:
                    ladybug_metrics = measure_query(
                        lambda: ladybug_backend.neighbors_batch(query_nodes)
                    )

                    networkx_metrics = measure_query(
                        lambda: networkx_backend.neighbors_batch(query_nodes)
                    )
                else:
                    networkx_metrics = measure_query(
                        lambda: networkx_backend.neighbors_batch(query_nodes)
                    )

                    ladybug_metrics = measure_query(
                        lambda: ladybug_backend.neighbors_batch(query_nodes)
                    )

                networkx_result = networkx_metrics["final_result"]

                ladybug_result = ladybug_metrics["final_result"]

                correctness = networkx_result == ladybug_result

                networkx_returned = total_returned_neighbors(networkx_result)

                ladybug_returned = total_returned_neighbors(ladybug_result)

                if networkx_returned != ladybug_returned:
                    correctness = False

                networkx_median = networkx_metrics["warm_median_ms"]

                ladybug_median = ladybug_metrics["warm_median_ms"]

                winner, speedup = winner_details(
                    networkx_time=networkx_median,
                    ladybug_time=ladybug_median,
                )

                networkx_batches_per_second = 1000 / networkx_median

                ladybug_batches_per_second = 1000 / ladybug_median

                networkx_nodes_per_second = (
                    actual_batch_size * networkx_batches_per_second
                )

                ladybug_nodes_per_second = (
                    actual_batch_size * ladybug_batches_per_second
                )

                networkx_per_node_ms = networkx_median / actual_batch_size

                ladybug_per_node_ms = ladybug_median / actual_batch_size

                result = {
                    "nodes": number_of_nodes,
                    "edges": number_of_edges,
                    "batch_size": actual_batch_size,
                    "returned_neighbors": networkx_returned,
                    "correctness": correctness,
                    "networkx_cold_ms": round(
                        networkx_metrics["cold_ms"],
                        6,
                    ),
                    "ladybug_cold_ms": round(
                        ladybug_metrics["cold_ms"],
                        6,
                    ),
                    "networkx_warm_median_ms": round(
                        networkx_median,
                        6,
                    ),
                    "ladybug_warm_median_ms": round(
                        ladybug_median,
                        6,
                    ),
                    "networkx_warm_p95_ms": round(
                        networkx_metrics["warm_p95_ms"],
                        6,
                    ),
                    "ladybug_warm_p95_ms": round(
                        ladybug_metrics["warm_p95_ms"],
                        6,
                    ),
                    "networkx_ms_per_node": round(
                        networkx_per_node_ms,
                        9,
                    ),
                    "ladybug_ms_per_node": round(
                        ladybug_per_node_ms,
                        9,
                    ),
                    "networkx_batches_per_second": round(
                        networkx_batches_per_second,
                        2,
                    ),
                    "ladybug_batches_per_second": round(
                        ladybug_batches_per_second,
                        2,
                    ),
                    "networkx_nodes_per_second": round(
                        networkx_nodes_per_second,
                        2,
                    ),
                    "ladybug_nodes_per_second": round(
                        ladybug_nodes_per_second,
                        2,
                    ),
                    "winner": winner,
                    "speedup": round(
                        speedup,
                        4,
                    ),
                }

                results.append(result)

                print(f"Correctness:      " f"{'PASS' if correctness else 'FAIL'}")

                print(f"Returned edges:   " f"{networkx_returned:,}")

                print(f"NetworkX median:  " f"{networkx_median:.6f} ms")

                print(f"LadybugDB median: " f"{ladybug_median:.6f} ms")

                print(f"NetworkX/node:    " f"{networkx_per_node_ms:.9f} ms")

                print(f"LadybugDB/node:   " f"{ladybug_per_node_ms:.9f} ms")

                print(f"Winner:           " f"{winner} ({speedup:.2f}x)")

                if not correctness:
                    raise RuntimeError("Backends returned different neighbor results")

        finally:
            networkx_backend.close()
            ladybug_backend.close()

        del edges
        gc.collect()

    save_results(results)

    print()
    print("=" * 88)
    print("Query scalability summary")
    print("=" * 88)

    for result in results:
        print(
            f"{result['nodes']:>9,} nodes | "
            f"batch {result['batch_size']:>5,} | "
            f"NetworkX "
            f"{result['networkx_warm_median_ms']:>10.6f} ms | "
            f"LadybugDB "
            f"{result['ladybug_warm_median_ms']:>10.6f} ms | "
            f"{result['winner']} "
            f"{result['speedup']:.2f}x"
        )

    print()
    print(f"Saved results to {RESULTS_FILE}")


if __name__ == "__main__":
    main()
