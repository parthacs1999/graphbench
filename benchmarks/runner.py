from backends.base import Edge, GraphBackend
from benchmarks.timer import measure_operation


def benchmark_backend(
    backend: GraphBackend,
    number_of_nodes: int,
    edges: list[Edge],
    query_nodes: list[int],
) -> dict:
    build_metrics = measure_operation(
        operation=lambda: backend.build_graph(
            number_of_nodes=number_of_nodes,
            edges=edges,
        ),
        repetitions=5,
        warmup_runs=1,
    )

    backend.build_graph(
        number_of_nodes=number_of_nodes,
        edges=edges,
    )

    def run_neighbor_batch() -> dict[int, list[int]]:
        return backend.neighbors_batch(query_nodes)

    neighbor_metrics = measure_operation(
        operation=run_neighbor_batch,
        repetitions=20,
        warmup_runs=3,
    )

    return {
        "backend": backend.name,
        "number_of_nodes": backend.node_count(),
        "number_of_edges": backend.edge_count(),
        "query_count_per_batch": len(query_nodes),
        "build": build_metrics,
        "neighbors": neighbor_metrics,
    }
