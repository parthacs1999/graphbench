from collections import deque
from collections.abc import Iterable

import ladybug as lb
import pandas as pd

from backends.base import Edge, GraphBackend


class LadybugBackend(GraphBackend):
    def __init__(self) -> None:
        self.database = lb.Database(":memory:")
        self.connection = lb.Connection(self.database)

        self._create_schema()

    @property
    def name(self) -> str:
        return "LadybugDB"

    def _create_schema(self) -> None:
        self.connection.execute("""
            CREATE NODE TABLE Node(
                id INT64 PRIMARY KEY
            )
            """)

        self.connection.execute("""
            CREATE REL TABLE Connects(
                FROM Node TO Node
            )
            """)

    def _clear_graph(self) -> None:
        self.connection.execute("""
            MATCH (source:Node)-[edge:Connects]->(target:Node)
            DELETE edge
            """)

        self.connection.execute("""
            MATCH (node:Node)
            DELETE node
            """)

    def build_graph(
        self,
        number_of_nodes: int,
        edges: Iterable[Edge],
    ) -> None:
        self._clear_graph()

        nodes_dataframe = pd.DataFrame(
            {
                "id": range(number_of_nodes),
            }
        )

        edges_dataframe = pd.DataFrame(
            list(edges),
            columns=["source", "target"],
        )

        self.connection.execute(
            "COPY Node FROM $nodes_dataframe",
            {
                "nodes_dataframe": nodes_dataframe,
            },
        )

        if not edges_dataframe.empty:
            self.connection.execute(
                "COPY Connects FROM $edges_dataframe",
                {
                    "edges_dataframe": edges_dataframe,
                },
            )

    def node_count(self) -> int:
        result = self.connection.execute("""
            MATCH (node:Node)
            RETURN count(node)
            """)

        for row in result:
            return int(row[0])

        return 0

    def edge_count(self) -> int:
        result = self.connection.execute("""
            MATCH (:Node)-[edge:Connects]->(:Node)
            RETURN count(edge)
            """)

        for row in result:
            return int(row[0])

        return 0

    def neighbors(self, node_id: int) -> list[int]:
        result = self.connection.execute(
            """
            MATCH (source:Node {id: $node_id})
                  -[:Connects]->
                  (target:Node)
            RETURN target.id
            ORDER BY target.id
            """,
            {
                "node_id": node_id,
            },
        )

        return [int(row[0]) for row in result]

    def has_path(self, source: int, target: int) -> bool:
        if source == target:
            return True

        nodes_to_visit = deque([source])
        visited = {source}

        while nodes_to_visit:
            current_node = nodes_to_visit.popleft()

            for neighbor in self.neighbors(current_node):
                if neighbor == target:
                    return True

                if neighbor not in visited:
                    visited.add(neighbor)
                    nodes_to_visit.append(neighbor)

        return False

    def close(self) -> None:
        self.connection = None
        self.database = None
