import csv
import gc
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

WARMUP_RUNS = 2
MEASURED_RUNS = 7
SEED = 42

RESULTS_DIRECTORY = Path("results")
RESULTS_FILE = RESULTS_DIRECTORY / "ingestion_scalability.csv"


def measure(
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


def validate_backend(
    backend,
    expected_nodes: int,
    expected_edges: int,
) -> None:
    """
    Confirm that the backend contains the expected graph.
    """
    actual_nodes = backend.node_count()
    actual_edges = backend.edge_count()

    if actual_nodes != expected_nodes:
        raise RuntimeError(
            f"{backend.name}: expected {expected_nodes} nodes, "
            f"received {actual_nodes}"
        )

    if actual_edges != expected_edges:
        raise RuntimeError(
            f"{backend.name}: expected {expected_edges} edges, "
            f"received {actual_edges}"
        )


def winner_details(
    networkx_time: float,
    ladybug_time: float,
) -> tuple[str, float]:
    """
    Return the faster backend and its speedup ratio.
    """
    if networkx_time <= 0 or ladybug_time <= 0:
        return "Unavailable", 0.0

    if networkx_time < ladybug_time:
        return "NetworkX", ladybug_time / networkx_time

    if ladybug_time < networkx_time:
        return "LadybugDB", networkx_time / ladybug_time

    return "Tie", 1.0


def run_networkx_construction(
    number_of_nodes: int,
    edges: list[tuple[int, int]],
) -> float:
    """
    Construct and validate a fresh NetworkX backend.
    """
    backend = NetworkXBackend()

    try:
        _, elapsed_ms = measure(
            lambda: backend.build_graph(
                number_of_nodes=number_of_nodes,
                edges=edges,
            )
        )

        validate_backend(
            backend=backend,
            expected_nodes=number_of_nodes,
            expected_edges=len(edges),
        )

        return elapsed_ms

    finally:
        backend.close()


def run_ladybug_construction(
    number_of_nodes: int,
    edge_count: int,
    node_table,
    edge_table,
) -> tuple[float, float, float]:
    """
    Copy prepared Arrow tables into a fresh LadybugDB database,
    run ANALYZE, and validate the resulting graph.
    """
    backend = LadybugBackend()

    try:
        _, copy_ms = measure(
            lambda: backend.build_graph_from_arrow(
                node_table=node_table,
                edge_table=edge_table,
                clear_existing=False,
                analyze=False,
            )
        )

        _, analyze_ms = measure(backend.analyze)

        ready_ms = copy_ms + analyze_ms

        validate_backend(
            backend=backend,
            expected_nodes=number_of_nodes,
            expected_edges=edge_count,
        )

        return copy_ms, analyze_ms, ready_ms

    finally:
        backend.close()


def save_results(results: list[dict]) -> None:
    """
    Save scalability results as a CSV file.
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
    print("Warming up PyArrow...")

    # Trigger PyArrow's one-time initialization before measuring
    # normal preparation latency.
    LadybugBackend.prepare_arrow_tables(
        number_of_nodes=2,
        edges=[(0, 1)],
    )

    results = []

    for number_of_nodes, number_of_edges in GRAPH_SIZES:
        print()
        print("=" * 82)
        print(
            f"Generating graph with "
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
                f"Generator returned {len(edges)} edges, " f"expected {number_of_edges}"
            )

        arrow_preparation_times = []
        networkx_build_times = []
        ladybug_copy_times = []
        ladybug_analyze_times = []
        ladybug_ready_times = []

        node_table = None
        edge_table = None

        total_runs = WARMUP_RUNS + MEASURED_RUNS

        for run_number in range(1, total_runs + 1):
            is_warmup = run_number <= WARMUP_RUNS
            run_type = "warm-up" if is_warmup else "measured"

            print(f"Run {run_number}/{total_runs} " f"({run_type})...")

            gc.collect()

            prepared_tables, arrow_preparation_ms = measure(
                lambda: LadybugBackend.prepare_arrow_tables(
                    number_of_nodes=number_of_nodes,
                    edges=edges,
                )
            )

            node_table, edge_table = prepared_tables

            gc.collect()

            # Alternate backend order to reduce systematic bias caused
            # by always running the same backend first.
            if run_number % 2 == 1:
                networkx_build_ms = run_networkx_construction(
                    number_of_nodes=number_of_nodes,
                    edges=edges,
                )

                (
                    ladybug_copy_ms,
                    ladybug_analyze_ms,
                    ladybug_ready_ms,
                ) = run_ladybug_construction(
                    number_of_nodes=number_of_nodes,
                    edge_count=number_of_edges,
                    node_table=node_table,
                    edge_table=edge_table,
                )
            else:
                (
                    ladybug_copy_ms,
                    ladybug_analyze_ms,
                    ladybug_ready_ms,
                ) = run_ladybug_construction(
                    number_of_nodes=number_of_nodes,
                    edge_count=number_of_edges,
                    node_table=node_table,
                    edge_table=edge_table,
                )

                networkx_build_ms = run_networkx_construction(
                    number_of_nodes=number_of_nodes,
                    edges=edges,
                )

            if not is_warmup:
                arrow_preparation_times.append(arrow_preparation_ms)
                networkx_build_times.append(networkx_build_ms)
                ladybug_copy_times.append(ladybug_copy_ms)
                ladybug_analyze_times.append(ladybug_analyze_ms)
                ladybug_ready_times.append(ladybug_ready_ms)

        arrow_preparation_median = median(arrow_preparation_times)

        networkx_build_median = median(networkx_build_times)

        ladybug_copy_median = median(ladybug_copy_times)

        ladybug_analyze_median = median(ladybug_analyze_times)

        ladybug_ready_median = median(ladybug_ready_times)

        ladybug_adapter_total = arrow_preparation_median + ladybug_ready_median

        native_winner, native_speedup = winner_details(
            networkx_time=networkx_build_median,
            ladybug_time=ladybug_ready_median,
        )

        adapter_winner, adapter_speedup = winner_details(
            networkx_time=networkx_build_median,
            ladybug_time=ladybug_adapter_total,
        )

        result = {
            "nodes": number_of_nodes,
            "edges": number_of_edges,
            "correctness": True,
            "arrow_preparation_ms": round(
                arrow_preparation_median,
                4,
            ),
            "networkx_build_ms": round(
                networkx_build_median,
                4,
            ),
            "ladybug_copy_ms": round(
                ladybug_copy_median,
                4,
            ),
            "ladybug_analyze_ms": round(
                ladybug_analyze_median,
                4,
            ),
            "ladybug_ready_ms": round(
                ladybug_ready_median,
                4,
            ),
            "ladybug_adapter_total_ms": round(
                ladybug_adapter_total,
                4,
            ),
            "native_winner": native_winner,
            "native_speedup": round(
                native_speedup,
                4,
            ),
            "adapter_winner": adapter_winner,
            "adapter_speedup": round(
                adapter_speedup,
                4,
            ),
        }

        results.append(result)

        print("\nResult")
        print("-" * 82)

        print(f"Arrow preparation:             " f"{arrow_preparation_median:.4f} ms")

        print(f"NetworkX construction:         " f"{networkx_build_median:.4f} ms")

        print(f"LadybugDB COPY:                " f"{ladybug_copy_median:.4f} ms")

        print(f"LadybugDB ANALYZE:             " f"{ladybug_analyze_median:.4f} ms")

        print(f"LadybugDB ready-to-query:      " f"{ladybug_ready_median:.4f} ms")

        print(f"LadybugDB adapter-inclusive:   " f"{ladybug_adapter_total:.4f} ms")

        print(
            f"Native winner:                 "
            f"{native_winner} ({native_speedup:.2f}x)"
        )

        print(
            f"Adapter-inclusive winner:      "
            f"{adapter_winner} ({adapter_speedup:.2f}x)"
        )

        # Release the largest objects before generating the next graph.
        del edges
        del node_table
        del edge_table
        gc.collect()

    save_results(results)

    print()
    print("=" * 82)
    print("Ingestion scalability summary")
    print("=" * 82)

    for result in results:
        print(
            f"{result['nodes']:>10,} nodes | "
            f"NetworkX {result['networkx_build_ms']:>10.4f} ms | "
            f"LadybugDB native {result['ladybug_ready_ms']:>10.4f} ms | "
            f"LadybugDB adapter "
            f"{result['ladybug_adapter_total_ms']:>10.4f} ms"
        )

    print()
    print(f"Saved results to {RESULTS_FILE}")


if __name__ == "__main__":
    main()
