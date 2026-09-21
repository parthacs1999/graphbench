from collections import Counter
from typing import Any

import networkx as nx


def analyze_structural_core(
    graph: nx.DiGraph,
    top_n: int = 10,
) -> dict[str, Any]:
    """
    Analyze the structural backbone using K-core decomposition.

    Dependency direction is ignored because standard K-core measures
    the number of neighbors remaining around each node.
    """

    if top_n <= 0:
        raise ValueError("top_n must be greater than zero.")

    if graph.number_of_nodes() == 0:
        return {
            "rankings": [],
            "core_numbers": {},
            "maximum_core": 0,
            "deepest_core_components": [],
            "core_distribution": {},
            "warnings": ["The graph contains no components."],
        }

    undirected_graph = graph.to_undirected()

    # NetworkX core_number does not accept self-loops.
    self_loops = list(nx.selfloop_edges(undirected_graph))

    if self_loops:
        undirected_graph.remove_edges_from(self_loops)

    core_numbers = nx.core_number(undirected_graph)

    maximum_core = max(
        core_numbers.values(),
        default=0,
    )

    deepest_core_components = sorted(
        str(component)
        for component, core_number in core_numbers.items()
        if core_number == maximum_core
    )

    core_distribution = dict(sorted(Counter(core_numbers.values()).items()))

    ordered_components = sorted(
        graph.nodes,
        key=lambda component: (
            -core_numbers[component],
            -undirected_graph.degree(component),
            str(component),
        ),
    )

    rankings: list[dict[str, Any]] = []

    for rank, component in enumerate(
        ordered_components[: min(top_n, len(ordered_components))],
        start=1,
    ):
        component_name = str(component)
        core_number = int(core_numbers[component])
        structural_degree = int(undirected_graph.degree(component))
        is_deepest_core = core_number == maximum_core

        if is_deepest_core:
            explanation = (
                f"{component_name} belongs to the deepest "
                f"{maximum_core}-core. It remains connected to "
                f"at least {maximum_core} other surviving "
                "components within that structural layer."
            )
        else:
            explanation = (
                f"{component_name} has core number "
                f"{core_number}. It does not belong to the "
                f"deepest {maximum_core}-core."
            )

        rankings.append(
            {
                "rank": rank,
                "component": component_name,
                "core_number": core_number,
                "structural_degree": structural_degree,
                "is_deepest_core": is_deepest_core,
                "explanation": explanation,
            }
        )

    warnings = [
        (
            "K-core was calculated on an undirected projection, "
            "so dependency direction was ignored."
        )
    ]

    if self_loops:
        warnings.append(
            f"{len(self_loops)} self-loop(s) were excluded " "from K-core calculation."
        )

    return {
        "rankings": rankings,
        "core_numbers": {
            str(component): int(core_number)
            for component, core_number in core_numbers.items()
        },
        "maximum_core": maximum_core,
        "deepest_core_components": (deepest_core_components),
        "core_distribution": (core_distribution),
        "excluded_self_loops": len(self_loops),
        "parameters": {
            "top_n": top_n,
            "directed": False,
        },
        "warnings": warnings,
    }
