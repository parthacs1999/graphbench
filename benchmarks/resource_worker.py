import argparse
import json

from benchmarks.resources import measure_resources
from graph_generator import generate_edges


def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--backend",
        choices=["networkx", "ladybug"],
        required=True,
    )

    parser.add_argument(
        "--nodes",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--edges",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    return parser.parse_args()


def main():
    arguments = parse_arguments()

    if arguments.backend == "networkx":
        from backends.networkx_backend import NetworkXBackend

        backend_class = NetworkXBackend
    else:
        from backends.ladybug_backend import LadybugBackend

        backend_class = LadybugBackend

    edges = generate_edges(
        number_of_nodes=arguments.nodes,
        number_of_edges=arguments.edges,
        seed=arguments.seed,
    )

    def build_backend():
        backend = backend_class()

        backend.build_graph(
            number_of_nodes=arguments.nodes,
            edges=edges,
        )

        return backend

    metrics = measure_resources(build_backend)
    backend = metrics.pop("result")

    metrics["backend"] = backend.name
    metrics["node_count"] = backend.node_count()
    metrics["edge_count"] = backend.edge_count()

    print(json.dumps(metrics))

    backend.close()


if __name__ == "__main__":
    main()
