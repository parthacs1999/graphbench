from collections.abc import Iterable
import networkx as nx
from backends.base import Edge, GraphBackend


class NetworkXBackend(GraphBackend):
    def __init__(self) -> None:
        self.graph = nx.DiGraph()

    @property
    def name(self) -> str:
        return "NetworkX"

    def build_graph(self, number_of_nodes: int, edges: Iterable[Edge]) -> None:
        self.graph.clear()
        self.graph.add_nodes_from(range(number_of_nodes))
        self.graph.add_edges_from(edges)

    def node_count(self) -> int:
        return self.graph.number_of_nodes()

    def edge_count(self) -> int:
        return self.graph.number_of_edges()

    def neighbors(self, node_id: int) -> list[int]:
        return sorted(self.graph.successors(node_id))

    def neighbors_batch(self, node_ids: list[int]) -> dict[int, list[int]]:
        return {node_id: sorted(self.graph.successors(node_id)) for node_id in node_ids}

    def has_path(self, source: int, target: int) -> bool:
        return nx.has_path(self.graph, source, target)

    def shortest_path(
        self,
        source: int,
        target: int,
    ) -> list[int] | None:
        try:
            path = nx.shortest_path(
                self.graph,
                source=source,
                target=target,
            )

            return list(path)

        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def close(self) -> None:
        self.graph.clear()
