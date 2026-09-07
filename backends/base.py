from abc import ABC, abstractmethod
from collections.abc import Iterable

Edge = tuple[int, int]


class GraphBackend(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def build_graph(
        self,
        number_of_nodes: int,
        edges: Iterable[Edge],
    ) -> None:
        pass

    @abstractmethod
    def node_count(self) -> int:
        pass

    @abstractmethod
    def edge_count(self) -> int:
        pass

    @abstractmethod
    def neighbors(self, node_id: int) -> list[int]:
        pass

    @abstractmethod
    def neighbors_batch(
        self,
        node_ids: list[int],
    ) -> dict[int, list[int]]:
        pass

    @abstractmethod
    def has_path(self, source: int, target: int) -> bool:
        pass

    @abstractmethod
    def close(self) -> None:
        pass
