from backends.ladybug_backend import LadybugBackend
from graph_generator import generate_edges

NUMBER_OF_NODES = 10_000
NUMBER_OF_EDGES = 50_000
QUERY_NODES = list(range(100))


backend = LadybugBackend()

edges = generate_edges(
    number_of_nodes=NUMBER_OF_NODES,
    number_of_edges=NUMBER_OF_EDGES,
    seed=42,
)

print("Building graph...")

backend.build_graph(
    number_of_nodes=NUMBER_OF_NODES,
    edges=edges,
)


queries = {
    "IN query": """
        EXPLAIN
        MATCH (source:Node)-[:Connects]->(target:Node)
        WHERE source.id IN $node_ids
        RETURN source.id, target.id
        ORDER BY source.id, target.id
    """,
    "UNWIND query": """
        EXPLAIN
        UNWIND $node_ids AS node_id
        MATCH (source:Node {id: node_id})-[:Connects]->(target:Node)
        RETURN source.id, target.id
        ORDER BY source.id, target.id
    """,
}


for query_name, query in queries.items():
    print("\n" + "=" * 70)
    print(query_name)
    print("=" * 70)

    result = backend.connection.execute(
        query,
        {
            "node_ids": QUERY_NODES,
        },
    )

    for row in result:
        print(row)


backend.close()
