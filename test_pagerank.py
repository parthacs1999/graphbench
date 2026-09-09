import networkx as nx

from backends.ladybug_backend import LadybugBackend

NUMBER_OF_NODES = 6

EDGES = [
    (0, 1),
    (0, 2),
    (1, 2),
    (2, 0),
    (3, 4),
    (4, 3),
    (4, 5),
]


def run_networkx_pagerank():
    graph = nx.DiGraph()

    graph.add_nodes_from(range(NUMBER_OF_NODES))
    graph.add_edges_from(EDGES)

    scores = nx.pagerank(
        graph,
        alpha=0.85,
        max_iter=100,
        tol=1e-7,
    )

    return sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )


def run_ladybug_pagerank():
    backend = LadybugBackend()

    try:
        backend.build_graph(
            number_of_nodes=NUMBER_OF_NODES,
            edges=EDGES,
        )

        backend.connection.execute("LOAD algo;")

        backend.connection.execute("""
            CALL project_graph(
                'GraphBenchPageRank',
                ['Node'],
                ['Connects']
            );
            """)

        result = backend.connection.execute("""
            CALL page_rank(
                'GraphBenchPageRank',
                dampingFactor := 0.85,
                maxIterations := 100,
                tolerance := 0.0000001,
                normalizeInitial := true
            )
            RETURN node.id, rank
            ORDER BY rank DESC;
            """)

        return [(int(row[0]), float(row[1])) for row in result]

    finally:
        backend.close()


print("PageRank capability test")
print("=" * 60)

print("\nEdges:")

for source, target in EDGES:
    print(f"{source} -> {target}")

print("\nNetworkX PageRank:")

networkx_results = run_networkx_pagerank()

for node_id, score in networkx_results:
    print(f"Node {node_id}: {score:.10f}")

print("\nLadybugDB PageRank:")

ladybug_results = run_ladybug_pagerank()

for node_id, score in ladybug_results:
    print(f"Node {node_id}: {score:.10f}")

networkx_ranking = [node_id for node_id, _ in networkx_results]

ladybug_ranking = [node_id for node_id, _ in ladybug_results]

print("\nRanking comparison")
print("NetworkX:", networkx_ranking)
print("Ladybug: ", ladybug_ranking)
print(
    "Exact ranking match:",
    networkx_ranking == ladybug_ranking,
)
