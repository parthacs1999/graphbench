import csv
import math
from collections.abc import Callable
from pathlib import Path
from statistics import median
from time import perf_counter_ns

from backends.ladybug_backend import LadybugBackend
from backends.networkx_backend import NetworkXBackend
from graph_generator import generate_edges

NUMBER_OF_NODES = 100_000
NUMBER_OF_EDGES = 500_000
BATCH_SIZE = 100
SEED = 42

WARMUP_RUNS = 5
MEASURED_RUNS = 30

RESULTS_DIRECTORY = Path("results")
RESULTS_FILE = RESULTS_DIRECTORY / "query_strategy_comparison.csv"


IN_QUERY = """
MATCH (source:Node)-[:Connects]->(target:Node)
WHERE source.id IN $node_ids
RETURN source.id, target.id
"""


SPLIT_MATCH_QUERY = """
MATCH (source:Node)
WHERE source.id IN $node_ids
MATCH (source)-[:Connects]->(target:Node)
RETURN source.id, target.id
"""


POINT_QUERY = """
MATCH (source:Node {id: $node_id})-[:Connects]->(target:Node)
RETURN target.id
"""


RANGE_QUERY = """
MATCH (source:Node)-[:Connects]->(target:Node)
WHERE source.id >= $start_id
  AND source.id < $end_id
RETURN source.id, target.id
"""


def timed_call(
    operation: Callable[[], dict[int, list[int]]],
) -> tuple[dict[int, list[int]], float]:
    """
    Run one operation and return the result and elapsed milliseconds.

    perf_counter_ns is used for better resolution than a floating-point
    seconds timer.
    """
    start_ns = perf_counter_ns()
    result = operation()
    elapsed_ns = perf_counter_ns() - start_ns

    elapsed_ms = elapsed_ns / 1_000_000

    return result, elapsed_ms


def percentile(
    values: list[float],
    percentage: float,
) -> float:
    if not values:
        raise ValueError("values cannot be empty")

    if not 0 <= percentage <= 1:
        raise ValueError("percentage must be between 0 and 1")

    sorted_values = sorted(values)
    rank = math.ceil(percentage * len(sorted_values))
    index = max(0, rank - 1)

    return sorted_values[index]


def normalize_result(
    result: dict[int, list[int]],
) -> dict[int, list[int]]:
    """
    Sort each neighbor list so different database result orders can
    be compared correctly.
    """
    normalized = {}

    for node_id, neighbors in result.items():
        normalized[node_id] = sorted(neighbors)

    return normalized


def create_empty_result(
    query_nodes: list[int],
) -> dict[int, list[int]]:
    return {node_id: [] for node_id in query_nodes}


def execute_batch_query(
    backend: LadybugBackend,
    query: str,
    parameters: dict,
    query_nodes: list[int],
) -> dict[int, list[int]]:
    results = create_empty_result(query_nodes)

    query_result = backend.connection.execute(
        query,
        parameters,
    )

    for row in query_result:
        source_id = int(row[0])
        target_id = int(row[1])

        if source_id in results:
            results[source_id].append(target_id)

    return normalize_result(results)


def run_in_strategy(
    backend: LadybugBackend,
    query_nodes: list[int],
) -> dict[int, list[int]]:
    return execute_batch_query(
        backend=backend,
        query=IN_QUERY,
        parameters={
            "node_ids": query_nodes,
        },
        query_nodes=query_nodes,
    )


def run_split_match_strategy(
    backend: LadybugBackend,
    query_nodes: list[int],
) -> dict[int, list[int]]:
    return execute_batch_query(
        backend=backend,
        query=SPLIT_MATCH_QUERY,
        parameters={
            "node_ids": query_nodes,
        },
        query_nodes=query_nodes,
    )


def run_point_query_strategy(
    backend: LadybugBackend,
    query_nodes: list[int],
) -> dict[int, list[int]]:
    """
    Execute one primary-key query for each requested node.
    """
    results = create_empty_result(query_nodes)

    for node_id in query_nodes:
        query_result = backend.connection.execute(
            POINT_QUERY,
            {
                "node_id": node_id,
            },
        )

        results[node_id] = sorted(int(row[0]) for row in query_result)

    return results


def run_range_strategy(
    backend: LadybugBackend,
    query_nodes: list[int],
) -> dict[int, list[int]]:
    """
    Use a range predicate.

    This is equivalent only because query_nodes contains every
    integer in one contiguous range.
    """
    start_id = min(query_nodes)
    end_id = max(query_nodes) + 1

    return execute_batch_query(
        backend=backend,
        query=RANGE_QUERY,
        parameters={
            "start_id": start_id,
            "end_id": end_id,
        },
        query_nodes=query_nodes,
    )


def measure_strategy(
    name: str,
    operation: Callable[[], dict[int, list[int]]],
    expected_result: dict[int, list[int]],
) -> dict:
    """
    Measure cold and warm latency for one query strategy.
    """
    print()
    print(f"Testing strategy: {name}")

    cold_result, cold_ms = timed_call(operation)
    cold_result = normalize_result(cold_result)

    if cold_result != expected_result:
        raise RuntimeError(f"{name} failed cold-query correctness")

    for _ in range(WARMUP_RUNS):
        warmup_result = normalize_result(operation())

        if warmup_result != expected_result:
            raise RuntimeError(f"{name} failed warm-up correctness")

    measured_times = []

    for _ in range(MEASURED_RUNS):
        result, elapsed_ms = timed_call(operation)
        result = normalize_result(result)

        if result != expected_result:
            raise RuntimeError(f"{name} failed measured correctness")

        measured_times.append(elapsed_ms)

    median_ms = median(measured_times)
    p95_ms = percentile(
        measured_times,
        0.95,
    )

    returned_neighbors = sum(len(neighbors) for neighbors in expected_result.values())

    batches_per_second = 1000 / median_ms if median_ms > 0 else 0

    requested_nodes_per_second = BATCH_SIZE * batches_per_second

    milliseconds_per_requested_node = median_ms / BATCH_SIZE

    print(f"Correctness:             PASS")
    print(f"Cold latency:            {cold_ms:.6f} ms")
    print(f"Warm median:             {median_ms:.6f} ms")
    print(f"Warm P95:                {p95_ms:.6f} ms")
    print(f"Latency/requested node:  " f"{milliseconds_per_requested_node:.9f} ms")
    print(f"Requested nodes/second:  " f"{requested_nodes_per_second:,.2f}")

    return {
        "strategy": name,
        "correctness": True,
        "nodes": NUMBER_OF_NODES,
        "edges": NUMBER_OF_EDGES,
        "batch_size": BATCH_SIZE,
        "returned_neighbors": returned_neighbors,
        "cold_ms": round(cold_ms, 6),
        "warm_median_ms": round(
            median_ms,
            6,
        ),
        "warm_p95_ms": round(
            p95_ms,
            6,
        ),
        "ms_per_requested_node": round(
            milliseconds_per_requested_node,
            9,
        ),
        "batches_per_second": round(
            batches_per_second,
            2,
        ),
        "requested_nodes_per_second": round(
            requested_nodes_per_second,
            2,
        ),
    }


def save_results(
    results: list[dict],
) -> None:
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
    print("Generating graph...")

    edges = list(
        generate_edges(
            number_of_nodes=NUMBER_OF_NODES,
            number_of_edges=NUMBER_OF_EDGES,
            seed=SEED,
        )
    )

    networkx_backend = NetworkXBackend()
    ladybug_backend = LadybugBackend()

    try:
        print("Building NetworkX graph...")

        networkx_backend.build_graph(
            number_of_nodes=NUMBER_OF_NODES,
            edges=edges,
        )

        print("Building optimized LadybugDB graph " "and running ANALYZE...")

        ladybug_backend.build_graph(
            number_of_nodes=NUMBER_OF_NODES,
            edges=edges,
        )

        # Contiguous query IDs are required for the range strategy.
        query_nodes = list(range(BATCH_SIZE))

        expected_result = normalize_result(
            networkx_backend.neighbors_batch(query_nodes)
        )

        returned_neighbors = sum(
            len(neighbors) for neighbors in expected_result.values()
        )

        print()
        print("=" * 78)
        print("LadybugDB query-strategy comparison")
        print("=" * 78)
        print(f"Nodes:               {NUMBER_OF_NODES:,}")
        print(f"Edges:               {NUMBER_OF_EDGES:,}")
        print(f"Batch size:          {BATCH_SIZE:,}")
        print(f"Returned neighbors:  {returned_neighbors:,}")

        strategies = [
            (
                "IN batch",
                lambda: run_in_strategy(
                    ladybug_backend,
                    query_nodes,
                ),
            ),
            (
                "Split MATCH",
                lambda: run_split_match_strategy(
                    ladybug_backend,
                    query_nodes,
                ),
            ),
            (
                "Primary-key point queries",
                lambda: run_point_query_strategy(
                    ladybug_backend,
                    query_nodes,
                ),
            ),
            (
                "Contiguous range",
                lambda: run_range_strategy(
                    ladybug_backend,
                    query_nodes,
                ),
            ),
        ]

        results = []

        for strategy_name, operation in strategies:
            result = measure_strategy(
                name=strategy_name,
                operation=operation,
                expected_result=expected_result,
            )

            results.append(result)

        results.sort(key=lambda item: item["warm_median_ms"])

        fastest_time = results[0]["warm_median_ms"]

        print()
        print("=" * 78)
        print("Strategy ranking")
        print("=" * 78)

        for position, result in enumerate(
            results,
            start=1,
        ):
            relative_to_fastest = result["warm_median_ms"] / fastest_time

            print(
                f"{position}. "
                f"{result['strategy']:<28} "
                f"{result['warm_median_ms']:>10.6f} ms "
                f"({relative_to_fastest:.2f}x fastest time)"
            )

        save_results(results)

        print()
        print(f"Saved results to {RESULTS_FILE}")

    finally:
        networkx_backend.close()
        ladybug_backend.close()


if __name__ == "__main__":
    main()
