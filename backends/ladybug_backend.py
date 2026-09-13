from collections import deque
from collections.abc import Iterable

import ladybug as lb
import pyarrow as pa

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
        self.connection.execute(
            """
            CREATE NODE TABLE Node(
                id INT64 PRIMARY KEY
            )
            """,
            {
                "dummy": 0,
            },
        )

        self.connection.execute(
            """
            CREATE REL TABLE Connects(
                FROM Node TO Node
            )
            """,
            {
                "dummy": 0,
            },
        )

    def _clear_graph(self) -> None:
        """
        Remove all relationships before removing the nodes.

        This method is not included in fresh-backend construction
        measurements.
        """
        self.connection.execute(
            """
            MATCH (source:Node)-[edge:Connects]->(target:Node)
            DELETE edge
            """,
            {
                "dummy": 0,
            },
        )

        self.connection.execute(
            """
            MATCH (node:Node)
            DELETE node
            """,
            {
                "dummy": 0,
            },
        )

    @staticmethod
    def prepare_arrow_tables(
        number_of_nodes: int,
        edges: Iterable[Edge],
    ) -> tuple[pa.Table, pa.Table]:
        """
        Convert graph data into sorted PyArrow tables.

        Input preparation can be measured separately from LadybugDB's
        native COPY operation.
        """
        if number_of_nodes < 0:
            raise ValueError("number_of_nodes cannot be negative")

        # Sorting groups relationships by source and then target.
        sorted_edges = sorted(edges)

        node_table = pa.table(
            {
                "id": pa.array(
                    range(number_of_nodes),
                    type=pa.int64(),
                )
            }
        )

        if sorted_edges:
            sources, targets = zip(*sorted_edges)

            edge_table = pa.table(
                {
                    "source": pa.array(
                        sources,
                        type=pa.int64(),
                    ),
                    "target": pa.array(
                        targets,
                        type=pa.int64(),
                    ),
                }
            )
        else:
            edge_table = pa.table(
                {
                    "source": pa.array(
                        [],
                        type=pa.int64(),
                    ),
                    "target": pa.array(
                        [],
                        type=pa.int64(),
                    ),
                }
            )

        return node_table, edge_table

    def build_graph_from_arrow(
        self,
        node_table: pa.Table,
        edge_table: pa.Table,
        *,
        clear_existing: bool = True,
        analyze: bool = True,
    ) -> None:
        """
        Load prepared PyArrow tables into LadybugDB.

        clear_existing should be False when the backend was freshly
        created because there is no previous graph to delete.
        """
        if clear_existing:
            self._clear_graph()

        self.connection.execute(
            "COPY Node FROM $node_table",
            {
                "node_table": node_table,
            },
        )

        if edge_table.num_rows > 0:
            self.connection.execute(
                "COPY Connects FROM $edge_table",
                {
                    "edge_table": edge_table,
                },
            )

        if analyze:
            self.analyze()

    def build_graph(
        self,
        number_of_nodes: int,
        edges: Iterable[Edge],
    ) -> None:
        """
        Build a query-ready graph using sorted Arrow bulk loading.

        This method preserves the common GraphBackend interface.
        """
        node_table, edge_table = self.prepare_arrow_tables(
            number_of_nodes=number_of_nodes,
            edges=edges,
        )

        self.build_graph_from_arrow(
            node_table=node_table,
            edge_table=edge_table,
            clear_existing=True,
            analyze=True,
        )

    def analyze(self) -> None:
        """
        Compute table statistics for LadybugDB's optimizer.
        """
        self.connection.execute(
            "ANALYZE",
            {
                "dummy": 0,
            },
        )

    def node_count(self) -> int:
        result = self.connection.execute(
            """
            MATCH (node:Node)
            RETURN count(node)
            """,
            {
                "dummy": 0,
            },
        )

        for row in result:
            return int(row[0])

        return 0

    def edge_count(self) -> int:
        result = self.connection.execute(
            """
            MATCH (:Node)-[edge:Connects]->(:Node)
            RETURN count(edge)
            """,
            {
                "dummy": 0,
            },
        )

        for row in result:
            return int(row[0])

        return 0

    def neighbors(
        self,
        node_id: int,
    ) -> list[int]:
        """
        Return the outgoing neighbors of one node.

        Sorting is performed in Python to avoid adding an ORDER BY
        operator to the LadybugDB query plan.
        """
        result = self.connection.execute(
            """
            MATCH (source:Node {id: $node_id})-[:Connects]->(target:Node)
            RETURN target.id
            """,
            {
                "node_id": node_id,
            },
        )

        neighbors = [int(row[0]) for row in result]

        neighbors.sort()

        return neighbors

    def neighbors_batch(
        self,
        node_ids: list[int],
    ) -> dict[int, list[int]]:
        """
        Return outgoing neighbors for multiple source nodes.

        A numeric range predicate is used when the requested IDs form a
        contiguous range. Arbitrary IDs use the general IN strategy.
        """
        unique_node_ids = sorted(set(node_ids))

        results = {node_id: [] for node_id in unique_node_ids}

        if not unique_node_ids:
            return results

        first_node_id = unique_node_ids[0]
        last_node_id = unique_node_ids[-1]

        is_contiguous = len(unique_node_ids) == last_node_id - first_node_id + 1

        if is_contiguous:
            query_result = self.connection.execute(
                """
                MATCH (source:Node)-[:Connects]->(target:Node)
                WHERE source.id >= $start_id
                AND source.id < $end_id
                RETURN source.id, target.id
                """,
                {
                    "start_id": first_node_id,
                    "end_id": last_node_id + 1,
                },
            )
        else:
            query_result = self.connection.execute(
                """
                MATCH (source:Node)-[:Connects]->(target:Node)
                WHERE source.id IN $node_ids
                RETURN source.id, target.id
                """,
                {
                    "node_ids": unique_node_ids,
                },
            )

        for row in query_result:
            source_id = int(row[0])
            target_id = int(row[1])

            if source_id in results:
                results[source_id].append(target_id)

        for neighbor_list in results.values():
            neighbor_list.sort()

        return results

    def has_path(
        self,
        source: int,
        target: int,
    ) -> bool:
        """
        Perform breadth-first search using repeated neighbor queries.

        This method is retained for correctness validation. It should
        not be used as a performance comparison with NetworkX's native
        path-finding algorithms.
        """
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
        """
        Release references to the LadybugDB connection and database.
        """
        self.connection = None
        self.database = None
