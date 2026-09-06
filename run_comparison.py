from backends.networkx_backend import NetworkXBackend
from graph_generator import generate_edges

NUMBER_OF_NODES = 10
NUMBER_OF_EDGES = 20
SEED = 42


edges = generate_edges(
    number_of_nodes=NUMBER_OF_NODES,
    number_of_edges=NUMBER_OF_EDGES,
    seed=SEED,
)

backend = NetworkXBackend()

backend.build_graph(
    number_of_nodes=NUMBER_OF_NODES,
    edges=edges,
)

print("Generated edges:")
for edge in edges:
    print(edge)

print("\nGraph information")
print("Backend:", backend.name)
print("Nodes:", backend.node_count())
print("Edges:", backend.edge_count())
print("Neighbors of node 0:", backend.neighbors(0))

backend.close()
