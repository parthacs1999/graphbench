import ladybug as lb

# Create a temporary in-memory database.
database = lb.Database(":memory:")

# Create a connection to the database.
connection = lb.Connection(database)


# Define the node schema.
connection.execute("""
    CREATE NODE TABLE Node(
        id INT64 PRIMARY KEY
    )
    """)


# Define a directed relationship.
connection.execute("""
    CREATE REL TABLE Connects(
        FROM Node TO Node
    )
    """)


# Insert four nodes.
connection.execute("CREATE (:Node {id: 0})")
connection.execute("CREATE (:Node {id: 1})")
connection.execute("CREATE (:Node {id: 2})")
connection.execute("CREATE (:Node {id: 3})")


# Insert directed relationships.
connection.execute("""
    MATCH (source:Node {id: 0}), (target:Node {id: 1})
    CREATE (source)-[:Connects]->(target)
    """)

connection.execute("""
    MATCH (source:Node {id: 0}), (target:Node {id: 2})
    CREATE (source)-[:Connects]->(target)
    """)

connection.execute("""
    MATCH (source:Node {id: 2}), (target:Node {id: 3})
    CREATE (source)-[:Connects]->(target)
    """)


# Find the outgoing neighbors of node 0.
result = connection.execute("""
    MATCH (source:Node {id: 0})-[:Connects]->(target:Node)
    RETURN target.id
    ORDER BY target.id
    """)


print("Neighbors of node 0:")

for row in result:
    print(row[0])
