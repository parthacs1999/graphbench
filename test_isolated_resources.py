from benchmarks.isolated_resources import compare_graph_resources

edges = [
    (0, 1),
    (0, 2),
    (1, 3),
    (2, 3),
    (3, 0),
]


def show_progress(percentage: int, message: str):
    print(f"{percentage}% - {message}")


results = compare_graph_resources(
    number_of_nodes=4,
    edges=edges,
    progress_callback=show_progress,
)

print()
print("Correctness:", results["correctness"])
print()
print("NetworkX:")
print(results["networkx"])
print()
print("LadybugDB:")
print(results["ladybug"])
