from backends.ladybug_backend import LadybugBackend
from backends.networkx_backend import NetworkXBackend
from benchmarks.runner import benchmark_backend
from graph_generator import generate_edges

NUMBER_OF_NODES = 1_000
NUMBER_OF_EDGES = 5_000
NUMBER_OF_QUERY_NODES = 100
SEED = 42


edges = generate_edges(
    number_of_nodes=NUMBER_OF_NODES,
    number_of_edges=NUMBER_OF_EDGES,
    seed=SEED,
)

query_nodes = list(range(NUMBER_OF_QUERY_NODES))


networkx_backend = NetworkXBackend()
ladybug_backend = LadybugBackend()


print("Running NetworkX benchmark...")

networkx_results = benchmark_backend(
    backend=networkx_backend,
    number_of_nodes=NUMBER_OF_NODES,
    edges=edges,
    query_nodes=query_nodes,
)


print("Running LadybugDB benchmark...")

ladybug_results = benchmark_backend(
    backend=ladybug_backend,
    number_of_nodes=NUMBER_OF_NODES,
    edges=edges,
    query_nodes=query_nodes,
)


networkx_neighbor_results = networkx_results["neighbors"]["result"]
ladybug_neighbor_results = ladybug_results["neighbors"]["result"]

results_match = networkx_neighbor_results == ladybug_neighbor_results


networkx_build_ms = networkx_results["build"]["median_ms"]
ladybug_build_ms = ladybug_results["build"]["median_ms"]

networkx_query_ms = networkx_results["neighbors"]["median_ms"]
ladybug_query_ms = ladybug_results["neighbors"]["median_ms"]


if networkx_build_ms < ladybug_build_ms:
    build_winner = "NetworkX"
    build_speedup = ladybug_build_ms / networkx_build_ms
else:
    build_winner = "LadybugDB"
    build_speedup = networkx_build_ms / ladybug_build_ms


if networkx_query_ms < ladybug_query_ms:
    query_winner = "NetworkX"
    query_speedup = ladybug_query_ms / networkx_query_ms
else:
    query_winner = "LadybugDB"
    query_speedup = networkx_query_ms / ladybug_query_ms


print("\nGraphBench comparison")
print("=" * 65)

print(f"Nodes:                  {NUMBER_OF_NODES:,}")
print(f"Edges:                  {NUMBER_OF_EDGES:,}")
print(f"Neighbor queries/batch: {NUMBER_OF_QUERY_NODES:,}")
print(f"Correctness:            {'PASS' if results_match else 'FAIL'}")

print("\nMedian graph construction time")
print(f"NetworkX:  {networkx_build_ms:.4f} ms")
print(f"LadybugDB: {ladybug_build_ms:.4f} ms")
print(f"Winner:    {build_winner} ({build_speedup:.2f}x faster)")

print("\nMedian time for one neighbor-query batch")
print(f"NetworkX:  {networkx_query_ms:.4f} ms")
print(f"LadybugDB: {ladybug_query_ms:.4f} ms")
print(f"Winner:    {query_winner} ({query_speedup:.2f}x faster)")

print("\nP95 batch latency")
print(f"NetworkX:  " f"{networkx_results['neighbors']['p95_ms']:.4f} ms")
print(f"LadybugDB: " f"{ladybug_results['neighbors']['p95_ms']:.4f} ms")

print("\nEstimated batch throughput")
print(
    f"NetworkX:  "
    f"{networkx_results['neighbors']['throughput_per_second']:,.2f} "
    "batches/second"
)
print(
    f"LadybugDB: "
    f"{ladybug_results['neighbors']['throughput_per_second']:,.2f} "
    "batches/second"
)

networkx_backend.close()
ladybug_backend.close()
