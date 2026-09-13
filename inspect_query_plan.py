from backends.ladybug_backend import LadybugBackend
from graph_generator import generate_edges

NUMBER_OF_NODES = 100_000
NUMBER_OF_EDGES = 500_000
SEED = 42

QUERY_NODES = list(range(100))


QUERY = """
MATCH (source:Node)-[:Connects]->(target:Node)
WHERE source.id IN $node_ids
RETURN source.id, target.id
ORDER BY source.id, target.id
"""


def print_result(result) -> None:
    for row in result:
        for value in row:
            print(value)


print("Generating graph...")

edges = list(
    generate_edges(
        number_of_nodes=NUMBER_OF_NODES,
        number_of_edges=NUMBER_OF_EDGES,
        seed=SEED,
    )
)

backend = LadybugBackend()

try:
    print("Building LadybugDB graph...")

    backend.build_graph(
        number_of_nodes=NUMBER_OF_NODES,
        edges=edges,
    )

    print("\nEXPLAIN")
    print("=" * 80)

    explain_result = backend.connection.execute(
        "EXPLAIN " + QUERY,
        {
            "node_ids": QUERY_NODES,
        },
    )

    print_result(explain_result)

    print("\nPROFILE")
    print("=" * 80)

    profile_result = backend.connection.execute(
        "PROFILE " + QUERY,
        {
            "node_ids": QUERY_NODES,
        },
    )

    print_result(profile_result)

finally:
    backend.close()
