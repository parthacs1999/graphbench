from backends.ladybug_backend import LadybugBackend

backend = LadybugBackend()

edges = [
    (0, 1),
    (0, 2),
    (2, 3),
]

backend.build_graph(
    number_of_nodes=5,
    edges=edges,
)

print("Backend:", backend.name)
print("Nodes:", backend.node_count())
print("Edges:", backend.edge_count())
print("Neighbors of 0:", backend.neighbors(0))
print("Path from 0 to 3:", backend.has_path(0, 3))
print("Path from 3 to 0:", backend.has_path(3, 0))

backend.close()
