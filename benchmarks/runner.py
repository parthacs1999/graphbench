from backends.base import Edge, GraphBackend
from benchmarks.timer import measure_operation


def benchmark_backend(
    backend: GraphBackend,
    number_of_nodes: int,
    edges: list[Edge],
    query_nodes: list[int],
    build_repetitions: int = 5,
    build_warmup_runs: int = 1,
    query_repetitions: int = 20,
    query_warmup_runs: int = 3,
) -> dict:
    """
    Benchmark graph construction and neighbor queries.

    Every construction measurement uses a fresh backend. This prevents
    deletion of a previously loaded graph from being counted as part
    of the next construction operation.

    The backend passed to this function is reserved for query
    benchmarking after the construction measurements finish.
    """

    backend_class = type(backend)

    def build_fresh_backend() -> None:
        fresh_backend = backend_class()

        try:
            fresh_backend.build_graph(
                number_of_nodes=number_of_nodes,
                edges=edges,
            )
        finally:
            fresh_backend.close()

    build_metrics = measure_operation(
        operation=build_fresh_backend,
        repetitions=build_repetitions,
        warmup_runs=build_warmup_runs,
    )

    # Build one separate complete graph for query benchmarking.
    # This construction is intentionally outside the reported
    # construction measurements.
    backend.build_graph(
        number_of_nodes=number_of_nodes,
        edges=edges,
    )

    def run_neighbor_batch() -> dict[int, list[int]]:
        return backend.neighbors_batch(query_nodes)

    neighbor_metrics = measure_operation(
        operation=run_neighbor_batch,
        repetitions=query_repetitions,
        warmup_runs=query_warmup_runs,
    )

    return {
        "backend": backend.name,
        "number_of_nodes": backend.node_count(),
        "number_of_edges": backend.edge_count(),
        "query_count_per_batch": len(query_nodes),
        "configuration": {
            "build_repetitions": build_repetitions,
            "build_warmup_runs": build_warmup_runs,
            "query_repetitions": query_repetitions,
            "query_warmup_runs": query_warmup_runs,
            "fresh_backend_per_build": True,
        },
        "build": build_metrics,
        "neighbors": neighbor_metrics,
    }
