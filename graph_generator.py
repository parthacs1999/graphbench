import random
from backends.base import Edge


def generate_edges(
    number_of_nodes: int, number_of_edges: int, seed: int = 42
) -> list[Edge]:
    if number_of_nodes <= 0:
        raise ValueError("number_of_nodes must be greater than zero")

    if number_of_edges < 0:
        raise ValueError("number_of_edges must be zero or greater")

    maximum_edges = number_of_nodes * (number_of_nodes - 1)

    if number_of_edges > maximum_edges:
        raise ValueError(
            f"Requested {number_of_edges} edges, but a directed graph "
            f"with {number_of_nodes} nodes can have at most "
            f"{maximum_edges} unique edges without self-loops."
        )

    random_generator = random.Random(seed)
    edges: set[Edge] = set()

    while len(edges) < number_of_edges:
        source = random_generator.randrange(number_of_nodes)
        target = random_generator.randrange(number_of_nodes)

        if source != target:
            edges.add((source, target))

    return sorted(edges)
