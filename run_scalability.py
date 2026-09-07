import pandas as pd

from backends.ladybug_backend import LadybugBackend
from backends.networkx_backend import NetworkXBackend
from benchmarks.runner import benchmark_backend
from graph_generator import generate_edges

GRAPH_CONFIGURATIONS = [
    {
        "nodes": 100,
        "edges": 500,
    },
    {
        "nodes": 1_000,
        "edges": 5_000,
    },
    {
        "nodes": 10_000,
        "edges": 50_000,
    },
]

NUMBER_OF_QUERY_NODES = 100
SEED = 42


all_results = []


for configuration in GRAPH_CONFIGURATIONS:
    number_of_nodes = configuration["nodes"]
    number_of_edges = configuration["edges"]

    print(
        f"\nGenerating graph with "
        f"{number_of_nodes:,} nodes and "
        f"{number_of_edges:,} edges..."
    )

    edges = generate_edges(
        number_of_nodes=number_of_nodes,
        number_of_edges=number_of_edges,
        seed=SEED,
    )

    query_count = min(
        NUMBER_OF_QUERY_NODES,
        number_of_nodes,
    )

    query_nodes = list(range(query_count))

    networkx_backend = NetworkXBackend()
    ladybug_backend = LadybugBackend()

    print("Running NetworkX...")

    networkx_results = benchmark_backend(
        backend=networkx_backend,
        number_of_nodes=number_of_nodes,
        edges=edges,
        query_nodes=query_nodes,
    )

    print("Running LadybugDB...")

    ladybug_results = benchmark_backend(
        backend=ladybug_backend,
        number_of_nodes=number_of_nodes,
        edges=edges,
        query_nodes=query_nodes,
    )

    correctness = (
        networkx_results["neighbors"]["result"]
        == ladybug_results["neighbors"]["result"]
    )

    networkx_build_ms = networkx_results["build"]["median_ms"]
    ladybug_build_ms = ladybug_results["build"]["median_ms"]

    networkx_query_ms = networkx_results["neighbors"]["median_ms"]
    ladybug_query_ms = ladybug_results["neighbors"]["median_ms"]

    build_ratio = (
        ladybug_build_ms / networkx_build_ms if networkx_build_ms > 0 else float("inf")
    )

    query_ratio = (
        ladybug_query_ms / networkx_query_ms if networkx_query_ms > 0 else float("inf")
    )

    all_results.append(
        {
            "nodes": number_of_nodes,
            "edges": number_of_edges,
            "query_nodes": query_count,
            "correctness": correctness,
            "networkx_build_ms": networkx_build_ms,
            "ladybug_build_ms": ladybug_build_ms,
            "networkx_neighbor_batch_ms": networkx_query_ms,
            "ladybug_neighbor_batch_ms": ladybug_query_ms,
            "ladybug_to_networkx_build_ratio": build_ratio,
            "ladybug_to_networkx_query_ratio": query_ratio,
        }
    )

    networkx_backend.close()
    ladybug_backend.close()


results_dataframe = pd.DataFrame(all_results)

results_dataframe.to_csv(
    "results/scalability_results.csv",
    index=False,
)


print("\nScalability results")
print("=" * 100)

print(
    results_dataframe.to_string(
        index=False,
        float_format=lambda value: f"{value:.4f}",
    )
)

print("\nSaved results to " "results/scalability_results.csv")
