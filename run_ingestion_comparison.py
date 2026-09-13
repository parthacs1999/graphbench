from collections.abc import Callable
from statistics import median
from time import perf_counter
from typing import Any

from backends.ladybug_backend import LadybugBackend
from backends.networkx_backend import NetworkXBackend
from graph_generator import generate_edges

NUMBER_OF_NODES = 10_000
NUMBER_OF_EDGES = 50_000
NUMBER_OF_RUNS = 7
WARMUP_RUNS = 2
SEED = 42


def measure(operation: Callable[[], Any]) -> tuple[Any, float]:
    """
    Execute an operation and return its result and elapsed time
    in milliseconds.
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
    Verify that the backend contains the expected graph.
    """
    actual_nodes = backend.node_count()
    actual_edges = backend.edge_count()

    if actual_nodes != expected_nodes:
        raise RuntimeError(
            f"{backend.name}: expected {expected_nodes} nodes, "
            f"but received {actual_nodes}"
        )

    if actual_edges != expected_edges:
        raise RuntimeError(
            f"{backend.name}: expected {expected_edges} edges, "
            f"but received {actual_edges}"
        )


def comparison_text(
    networkx_time: float,
    ladybug_time: float,
) -> str:
    """
    Return a readable comparison between two latency measurements.
    """
    if networkx_time <= 0 or ladybug_time <= 0:
        return "Comparison unavailable"

    if networkx_time < ladybug_time:
        ratio = ladybug_time / networkx_time
        return f"NetworkX is {ratio:.2f}x faster"

    if ladybug_time < networkx_time:
        ratio = networkx_time / ladybug_time
        return f"LadybugDB is {ratio:.2f}x faster"

    return "Tie"


# -------------------------------------------------------------------
# Generate a common graph
# -------------------------------------------------------------------

print("Generating common graph data...")

edges = list(
    generate_edges(
        number_of_nodes=NUMBER_OF_NODES,
        number_of_edges=NUMBER_OF_EDGES,
        seed=SEED,
    )
)


# -------------------------------------------------------------------
# Measure PyArrow preparation
# -------------------------------------------------------------------

print("Measuring LadybugDB Arrow preparation...")

# The first PyArrow call may include one-time native-library
# initialization. Measure it separately as cold preparation.
(
    cold_arrow_tables,
    cold_arrow_preparation_ms,
) = measure(
    lambda: LadybugBackend.prepare_arrow_tables(
        number_of_nodes=NUMBER_OF_NODES,
        edges=edges,
    )
)

node_table, edge_table = cold_arrow_tables


# Warm up the Arrow conversion path.
for warmup_number in range(1, WARMUP_RUNS + 1):
    print(f"Arrow preparation warm-up " f"{warmup_number}/{WARMUP_RUNS}...")

    LadybugBackend.prepare_arrow_tables(
        number_of_nodes=NUMBER_OF_NODES,
        edges=edges,
    )


arrow_preparation_times = []

for run_number in range(1, NUMBER_OF_RUNS + 1):
    print(f"Arrow preparation measured run " f"{run_number}/{NUMBER_OF_RUNS}...")

    prepared_tables, preparation_ms = measure(
        lambda: LadybugBackend.prepare_arrow_tables(
            number_of_nodes=NUMBER_OF_NODES,
            edges=edges,
        )
    )

    node_table, edge_table = prepared_tables
    arrow_preparation_times.append(preparation_ms)


warm_arrow_preparation_median = median(arrow_preparation_times)


# -------------------------------------------------------------------
# Measure native backend construction
# -------------------------------------------------------------------

networkx_build_times = []
ladybug_copy_times = []
ladybug_analyze_times = []
ladybug_ready_times = []

total_backend_runs = WARMUP_RUNS + NUMBER_OF_RUNS

for run_number in range(1, total_backend_runs + 1):
    is_warmup = run_number <= WARMUP_RUNS
    run_type = "warm-up" if is_warmup else "measured"

    print(f"Backend run {run_number}/{total_backend_runs} " f"({run_type})...")

    # ---------------------------------------------------------------
    # NetworkX native construction
    # ---------------------------------------------------------------

    networkx_backend = NetworkXBackend()

    try:
        _, networkx_build_ms = measure(
            lambda: networkx_backend.build_graph(
                number_of_nodes=NUMBER_OF_NODES,
                edges=edges,
            )
        )

        validate_backend(
            backend=networkx_backend,
            expected_nodes=NUMBER_OF_NODES,
            expected_edges=NUMBER_OF_EDGES,
        )

    finally:
        networkx_backend.close()

    # ---------------------------------------------------------------
    # LadybugDB native Arrow COPY
    # ---------------------------------------------------------------

    ladybug_backend = LadybugBackend()

    try:
        _, ladybug_copy_ms = measure(
            lambda: ladybug_backend.build_graph_from_arrow(
                node_table=node_table,
                edge_table=edge_table,
                clear_existing=False,
                analyze=False,
            )
        )

        _, ladybug_analyze_ms = measure(ladybug_backend.analyze)

        validate_backend(
            backend=ladybug_backend,
            expected_nodes=NUMBER_OF_NODES,
            expected_edges=NUMBER_OF_EDGES,
        )

    finally:
        ladybug_backend.close()

    ladybug_ready_ms = ladybug_copy_ms + ladybug_analyze_ms

    if not is_warmup:
        networkx_build_times.append(networkx_build_ms)
        ladybug_copy_times.append(ladybug_copy_ms)
        ladybug_analyze_times.append(ladybug_analyze_ms)
        ladybug_ready_times.append(ladybug_ready_ms)


# -------------------------------------------------------------------
# Calculate summary statistics
# -------------------------------------------------------------------

networkx_build_median = median(networkx_build_times)

ladybug_copy_median = median(ladybug_copy_times)

ladybug_analyze_median = median(ladybug_analyze_times)

ladybug_ready_median = median(ladybug_ready_times)


# Warm adapter-inclusive construction includes the normal Arrow
# preparation cost, COPY time, and ANALYZE time.
ladybug_warm_adapter_total = warm_arrow_preparation_median + ladybug_ready_median


# Cold adapter-inclusive construction also includes PyArrow's
# first-use initialization cost.
ladybug_cold_adapter_total = cold_arrow_preparation_ms + ladybug_ready_median


# -------------------------------------------------------------------
# Display results
# -------------------------------------------------------------------

print("\nGraphBench ingestion comparison")
print("=" * 76)

print(f"Nodes:                             {NUMBER_OF_NODES:,}")
print(f"Edges:                             {NUMBER_OF_EDGES:,}")
print(f"Warm-up runs:                      {WARMUP_RUNS}")
print(f"Measured runs:                     {NUMBER_OF_RUNS}")
print("Correctness:                       PASS")


print("\nArrow preparation")
print("-" * 76)

print(f"Cold Arrow preparation:            " f"{cold_arrow_preparation_ms:.4f} ms")

print(f"Warm Arrow preparation median:     " f"{warm_arrow_preparation_median:.4f} ms")


print("\nNative construction")
print("-" * 76)

print(f"NetworkX construction:             " f"{networkx_build_median:.4f} ms")

print(f"LadybugDB COPY:                    " f"{ladybug_copy_median:.4f} ms")

print(f"LadybugDB ANALYZE:                 " f"{ladybug_analyze_median:.4f} ms")

print(f"LadybugDB ready-to-query:          " f"{ladybug_ready_median:.4f} ms")


print("\nAdapter-inclusive LadybugDB construction")
print("-" * 76)

print(f"Warm Arrow + COPY + ANALYZE:       " f"{ladybug_warm_adapter_total:.4f} ms")

print(f"Cold Arrow + COPY + ANALYZE:       " f"{ladybug_cold_adapter_total:.4f} ms")


print("\nPerformance comparison")
print("-" * 76)

print(
    "Native construction:              "
    + comparison_text(
        networkx_time=networkx_build_median,
        ladybug_time=ladybug_ready_median,
    )
)

print(
    "Warm adapter-inclusive:           "
    + comparison_text(
        networkx_time=networkx_build_median,
        ladybug_time=ladybug_warm_adapter_total,
    )
)

print(
    "Cold adapter-inclusive:           "
    + comparison_text(
        networkx_time=networkx_build_median,
        ladybug_time=ladybug_cold_adapter_total,
    )
)


print("\nInterpretation")
print("-" * 76)

print(
    "Native construction compares NetworkX using a prepared Python "
    "edge list with LadybugDB using prepared Arrow tables."
)

print(
    "Warm adapter-inclusive construction also includes converting "
    "the Python edge list into Arrow tables."
)

print(
    "Cold adapter-inclusive construction includes PyArrow's "
    "one-time initialization overhead."
)

print("Graph generation is excluded from all three construction " "comparisons.")
