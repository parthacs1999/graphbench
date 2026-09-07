import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from backends.ladybug_backend import LadybugBackend
from backends.networkx_backend import NetworkXBackend
from benchmarks.runner import benchmark_backend
from ingestion.csv_loader import load_edge_csv


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=("Compare NetworkX and LadybugDB " "using an edge-list CSV file.")
    )

    parser.add_argument(
        "--file",
        required=True,
        help="Path to the CSV edge-list file.",
    )

    parser.add_argument(
        "--source",
        required=True,
        help="Name of the source-node column.",
    )

    parser.add_argument(
        "--target",
        required=True,
        help="Name of the target-node column.",
    )

    return parser.parse_args()


def determine_winner(
    networkx_time: float,
    ladybug_time: float,
) -> dict:
    if networkx_time < ladybug_time:
        return {
            "winner": "NetworkX",
            "speedup": ladybug_time / networkx_time,
        }

    return {
        "winner": "LadybugDB",
        "speedup": networkx_time / ladybug_time,
    }


def main():
    arguments = parse_arguments()

    normalized_graph = load_edge_csv(
        file_path=arguments.file,
        source_column=arguments.source,
        target_column=arguments.target,
    )

    query_count = min(
        100,
        normalized_graph.number_of_nodes,
    )

    query_nodes = list(range(query_count))

    networkx_backend = NetworkXBackend()
    ladybug_backend = LadybugBackend()

    try:
        print("Running NetworkX benchmark...")

        networkx_results = benchmark_backend(
            backend=networkx_backend,
            number_of_nodes=(normalized_graph.number_of_nodes),
            edges=normalized_graph.edges,
            query_nodes=query_nodes,
        )

        print("Running LadybugDB benchmark...")

        ladybug_results = benchmark_backend(
            backend=ladybug_backend,
            number_of_nodes=(normalized_graph.number_of_nodes),
            edges=normalized_graph.edges,
            query_nodes=query_nodes,
        )

        correctness = (
            networkx_results["neighbors"]["result"]
            == ladybug_results["neighbors"]["result"]
        )

        build_comparison = determine_winner(
            networkx_time=(networkx_results["build"]["median_ms"]),
            ladybug_time=(ladybug_results["build"]["median_ms"]),
        )

        query_comparison = determine_winner(
            networkx_time=(networkx_results["neighbors"]["median_ms"]),
            ladybug_time=(ladybug_results["neighbors"]["median_ms"]),
        )

        report = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "input": {
                "file": str(Path(arguments.file).resolve()),
                "source_column": arguments.source,
                "target_column": arguments.target,
            },
            "graph_health": {
                "original_rows": (normalized_graph.original_rows),
                "valid_unique_edges": (normalized_graph.valid_rows),
                "unique_nodes": (normalized_graph.number_of_nodes),
                "missing_rows": (normalized_graph.missing_rows),
                "duplicate_edges": (normalized_graph.duplicate_edges),
                "self_loops": (normalized_graph.self_loops),
            },
            "correctness": {
                "neighbor_results_match": correctness,
            },
            "networkx": {
                "build_median_ms": (networkx_results["build"]["median_ms"]),
                "build_p95_ms": (networkx_results["build"]["p95_ms"]),
                "neighbor_batch_median_ms": (
                    networkx_results["neighbors"]["median_ms"]
                ),
                "neighbor_batch_p95_ms": (networkx_results["neighbors"]["p95_ms"]),
            },
            "ladybug": {
                "build_median_ms": (ladybug_results["build"]["median_ms"]),
                "build_p95_ms": (ladybug_results["build"]["p95_ms"]),
                "neighbor_batch_median_ms": (ladybug_results["neighbors"]["median_ms"]),
                "neighbor_batch_p95_ms": (ladybug_results["neighbors"]["p95_ms"]),
            },
            "comparison": {
                "build_winner": (build_comparison["winner"]),
                "build_speedup": (build_comparison["speedup"]),
                "query_winner": (query_comparison["winner"]),
                "query_speedup": (query_comparison["speedup"]),
            },
        }

        output_path = Path("results/user_benchmark.json")

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with output_path.open(
            "w",
            encoding="utf-8",
        ) as report_file:
            json.dump(
                report,
                report_file,
                indent=2,
            )

        print("\nUser graph summary")
        print("=" * 60)
        print(f"Nodes:       " f"{normalized_graph.number_of_nodes:,}")
        print(f"Edges:       " f"{normalized_graph.valid_rows:,}")
        print(f"Missing:     " f"{normalized_graph.missing_rows:,}")
        print(f"Duplicates:  " f"{normalized_graph.duplicate_edges:,}")
        print(f"Self-loops:  " f"{normalized_graph.self_loops:,}")
        print(f"Correctness: " f"{'PASS' if correctness else 'FAIL'}")

        print("\nGraph construction")
        print("NetworkX:  " f"{report['networkx']['build_median_ms']:.4f} ms")
        print("LadybugDB: " f"{report['ladybug']['build_median_ms']:.4f} ms")
        print(
            f"Winner:    "
            f"{build_comparison['winner']} "
            f"({build_comparison['speedup']:.2f}x faster)"
        )

        print("\nNeighbor-query batch")
        print("NetworkX:  " f"{report['networkx']['neighbor_batch_median_ms']:.4f} ms")
        print("LadybugDB: " f"{report['ladybug']['neighbor_batch_median_ms']:.4f} ms")
        print(
            f"Winner:    "
            f"{query_comparison['winner']} "
            f"({query_comparison['speedup']:.2f}x faster)"
        )

        print("\nSaved report to " "results/user_benchmark.json")

    finally:
        networkx_backend.close()
        ladybug_backend.close()


if __name__ == "__main__":
    main()
