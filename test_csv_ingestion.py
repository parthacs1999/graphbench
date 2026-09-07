from ingestion.csv_loader import load_edge_csv

graph = load_edge_csv(
    file_path="data/sample_edges.csv",
    source_column="sender",
    target_column="receiver",
)


print("Graph health")
print("=" * 40)

print("Original rows:", graph.original_rows)
print("Valid unique edges:", graph.valid_rows)
print("Unique nodes:", graph.number_of_nodes)
print("Missing rows:", graph.missing_rows)
print("Duplicate edges:", graph.duplicate_edges)
print("Self-loops:", graph.self_loops)

print("\nNode mapping")

for node_id, label in graph.id_to_label.items():
    print(f"{node_id} -> {label}")

print("\nNormalized edges")

for source, target in graph.edges:
    source_label = graph.id_to_label[source]
    target_label = graph.id_to_label[target]

    print(f"{source} ({source_label}) " f"-> {target} ({target_label})")
