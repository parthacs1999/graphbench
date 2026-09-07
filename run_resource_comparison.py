import json
import subprocess
import sys

NUMBER_OF_NODES = 10_000
NUMBER_OF_EDGES = 50_000
SEED = 42


def run_worker(backend_name: str) -> dict:
    completed_process = subprocess.run(
        [
            sys.executable,
            "-m",
            "benchmarks.resource_worker",
            "--backend",
            backend_name,
            "--nodes",
            str(NUMBER_OF_NODES),
            "--edges",
            str(NUMBER_OF_EDGES),
            "--seed",
            str(SEED),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    return json.loads(completed_process.stdout)


print("Measuring NetworkX in an isolated process...")

networkx_metrics = run_worker("networkx")


print("Measuring LadybugDB in an isolated process...")

ladybug_metrics = run_worker("ladybug")


counts_match = (
    networkx_metrics["node_count"] == ladybug_metrics["node_count"] == NUMBER_OF_NODES
    and networkx_metrics["edge_count"]
    == ladybug_metrics["edge_count"]
    == NUMBER_OF_EDGES
)


print("\nIsolated resource comparison")
print("=" * 65)

print(f"Nodes:       {NUMBER_OF_NODES:,}")
print(f"Edges:       {NUMBER_OF_EDGES:,}")
print(f"Correctness: {'PASS' if counts_match else 'FAIL'}")

print("\nNetworkX")
print(f"Construction time: " f"{networkx_metrics['elapsed_ms']:.4f} ms")
print(
    f"Additional peak memory: "
    f"{networkx_metrics['additional_peak_memory_mb']:.2f} MB"
)
print(f"Process peak memory: " f"{networkx_metrics['peak_memory_mb']:.2f} MB")
print(f"CPU utilization: " f"{networkx_metrics['cpu_utilization_percent']:.2f}%")

print("\nLadybugDB")
print(f"Construction time: " f"{ladybug_metrics['elapsed_ms']:.4f} ms")
print(
    f"Additional peak memory: " f"{ladybug_metrics['additional_peak_memory_mb']:.2f} MB"
)
print(f"Process peak memory: " f"{ladybug_metrics['peak_memory_mb']:.2f} MB")
print(f"CPU utilization: " f"{ladybug_metrics['cpu_utilization_percent']:.2f}%")
