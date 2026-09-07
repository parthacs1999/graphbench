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
    build_metrics = measure_operation(
        operation=lambda: backend.build_graph(
            number_of_nodes=number_of_nodes,
            edges=edges,
        ),
        repetitions=build_repetitions,
        warmup_runs=build_warmup_runs,
    )

    # Ensure a complete graph is available before
    # measuring query performance.
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
        },
        "build": build_metrics,
        "neighbors": neighbor_metrics,
    }