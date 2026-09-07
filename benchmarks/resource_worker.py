import argparse
import json
from pathlib import Path

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
    )

    parser.add_argument(
        "--edges",
        type=int,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--input-file",
        type=str,
        help="Path to a normalized graph JSON file.",
    )

    arguments = parser.parse_args()

    using_synthetic_graph = arguments.nodes is not None and arguments.edges is not None

    using_input_file = arguments.input_file is not None

    if using_synthetic_graph and using_input_file:
        parser.error("Use either --input-file or --nodes/--edges, not both.")

    if not using_synthetic_graph and not using_input_file:
        parser.error("Provide --input-file or both --nodes and --edges.")

    return arguments


def load_graph_from_file(file_path: str):
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Graph input file does not exist: {path}")

    with path.open("r", encoding="utf-8") as input_file:
        graph_data = json.load(input_file)

    if "number_of_nodes" not in graph_data:
        raise ValueError("Input file must contain 'number_of_nodes'.")

    if "edges" not in graph_data:
        raise ValueError("Input file must contain 'edges'.")

    number_of_nodes = int(graph_data["number_of_nodes"])

    edges = [(int(source), int(target)) for source, target in graph_data["edges"]]

    return number_of_nodes, edges


def load_graph(arguments):
    if arguments.input_file:
        return load_graph_from_file(arguments.input_file)

    edges = generate_edges(
        number_of_nodes=arguments.nodes,
        number_of_edges=arguments.edges,
        seed=arguments.seed,
    )

    return arguments.nodes, edges


def load_backend_class(backend_name: str):
    if backend_name == "networkx":
        from backends.networkx_backend import NetworkXBackend

        return NetworkXBackend

    from backends.ladybug_backend import LadybugBackend

    return LadybugBackend


def main():
    arguments = parse_arguments()

    # Loading and normalization happen before resource measurement.
    # Therefore, we measure graph-engine construction rather than
    # JSON parsing or synthetic graph generation.
    number_of_nodes, edges = load_graph(arguments)

    backend_class = load_backend_class(arguments.backend)

    def build_backend():
        backend = backend_class()

        backend.build_graph(
            number_of_nodes=number_of_nodes,
            edges=edges,
        )

        return backend

    metrics = measure_resources(build_backend)

    backend = metrics.pop("result")

    try:
        metrics["backend"] = backend.name
        metrics["node_count"] = backend.node_count()
        metrics["edge_count"] = backend.edge_count()
        metrics["expected_node_count"] = number_of_nodes
        metrics["expected_edge_count"] = len(edges)

        print(json.dumps(metrics))
    finally:
        backend.close()


if __name__ == "__main__":
    main()
