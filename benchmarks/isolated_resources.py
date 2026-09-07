import json
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

ProgressCallback = Callable[[int, str], None]


def run_resource_worker(
    backend_name: str,
    input_file: Path,
    timeout_seconds: int = 300,
) -> dict:
    command = [
        sys.executable,
        "-m",
        "benchmarks.resource_worker",
        "--backend",
        backend_name,
        "--input-file",
        str(input_file),
    ]

    completed_process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )

    if completed_process.returncode != 0:
        error_message = completed_process.stderr.strip()

        raise RuntimeError(
            f"{backend_name} resource measurement failed.\n" f"{error_message}"
        )

    output_lines = [
        line.strip() for line in completed_process.stdout.splitlines() if line.strip()
    ]

    if not output_lines:
        raise RuntimeError(f"{backend_name} worker returned no output.")

    try:
        # The final output line contains the JSON metrics.
        return json.loads(output_lines[-1])
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"{backend_name} worker returned invalid JSON.\n"
            f"Output: {completed_process.stdout}"
        ) from error


def compare_graph_resources(
    number_of_nodes: int,
    edges: list[tuple[int, int]],
    progress_callback: ProgressCallback | None = None,
) -> dict:
    normalized_edges = [(int(source), int(target)) for source, target in edges]

    graph_data = {
        "number_of_nodes": int(number_of_nodes),
        "edges": [[source, target] for source, target in normalized_edges],
    }

    with tempfile.TemporaryDirectory(
        prefix="graphbench_resources_"
    ) as temporary_directory:
        input_file = Path(temporary_directory) / "normalized_graph.json"

        input_file.write_text(
            json.dumps(graph_data),
            encoding="utf-8",
        )

        if progress_callback:
            progress_callback(
                10,
                "Prepared normalized graph for resource measurement.",
            )

        if progress_callback:
            progress_callback(
                20,
                "Measuring NetworkX in an isolated process...",
            )

        networkx_metrics = run_resource_worker(
            backend_name="networkx",
            input_file=input_file,
        )

        if progress_callback:
            progress_callback(
                60,
                "Measuring LadybugDB in an isolated process...",
            )

        ladybug_metrics = run_resource_worker(
            backend_name="ladybug",
            input_file=input_file,
        )

    expected_edge_count = len(normalized_edges)

    correctness = (
        networkx_metrics["node_count"] == number_of_nodes
        and ladybug_metrics["node_count"] == number_of_nodes
        and networkx_metrics["edge_count"] == expected_edge_count
        and ladybug_metrics["edge_count"] == expected_edge_count
    )

    if progress_callback:
        progress_callback(
            100,
            "Resource measurement complete.",
        )

    return {
        "metadata": {
            "number_of_nodes": number_of_nodes,
            "number_of_edges": expected_edge_count,
        },
        "correctness": correctness,
        "networkx": networkx_metrics,
        "ladybug": ladybug_metrics,
    }
