from typing import Any

import networkx as nx


def get_betweenness_scores(
    graph: nx.DiGraph,
    exact_threshold: int = 2_000,
    approximation_samples: int = 500,
    seed: int = 42,
) -> tuple[dict[str, float], str, int | None]:
    """
    Calculate exact betweenness for smaller graphs and sampled
    betweenness for larger graphs.

    Exact betweenness can be expensive, so large user graphs use
    a reproducible approximation.
    """

    number_of_nodes = graph.number_of_nodes()

    if number_of_nodes <= exact_threshold:
        scores = nx.betweenness_centrality(
            graph,
            normalized=True,
            weight=None,
        )

        return scores, "exact", None

    sample_count = min(
        approximation_samples,
        number_of_nodes,
    )

    scores = nx.betweenness_centrality(
        graph,
        k=sample_count,
        normalized=True,
        weight=None,
        seed=seed,
    )

    return scores, "approximate", sample_count


def find_articulation_points(
    graph: nx.DiGraph,
) -> set[str]:
    """
    Find structural articulation points.

    NetworkX articulation-point analysis requires an undirected
    graph, so edge direction is intentionally ignored here.
    """

    undirected_graph = graph.to_undirected()

    return {str(node) for node in nx.articulation_points(undirected_graph)}


def find_bridges(
    graph: nx.DiGraph,
) -> list[tuple[str, str]]:
    """
    Find structural bridge edges after ignoring edge direction.
    """

    undirected_graph = graph.to_undirected()

    bridges = [
        tuple(sorted((str(source), str(target))))
        for source, target in nx.bridges(undirected_graph)
    ]

    return sorted(set(bridges))


def analyze_bottlenecks(
    graph: nx.DiGraph,
    top_n: int = 10,
    exact_threshold: int = 2_000,
    approximation_samples: int = 500,
    seed: int = 42,
) -> dict[str, Any]:
    """
    Identify components that connect different architectural regions.
    """

    if not graph.is_directed():
        raise ValueError("Dependency bottleneck analysis requires a directed graph.")

    if top_n <= 0:
        raise ValueError("top_n must be greater than zero.")

    if graph.number_of_nodes() == 0:
        return {
            "rankings": [],
            "articulation_points": [],
            "bridges": [],
            "betweenness_mode": "exact",
            "betweenness_samples": None,
            "warnings": ["The graph contains no components."],
        }

    (
        betweenness_scores,
        betweenness_mode,
        betweenness_samples,
    ) = get_betweenness_scores(
        graph=graph,
        exact_threshold=exact_threshold,
        approximation_samples=approximation_samples,
        seed=seed,
    )

    articulation_points = find_articulation_points(graph)

    bridges = find_bridges(graph)

    ranked_components = sorted(
        graph.nodes,
        key=lambda component: (
            -betweenness_scores[component],
            -graph.in_degree(component),
            str(component),
        ),
    )

    selected_components = ranked_components[: min(top_n, len(ranked_components))]

    rankings: list[dict[str, Any]] = []

    for rank, component in enumerate(
        selected_components,
        start=1,
    ):
        component_name = str(component)

        # If A can reach component X, then A directly or indirectly
        # depends on X under the component -> dependency convention.
        transitive_dependents = nx.ancestors(
            graph,
            component,
        )

        score = float(betweenness_scores[component])

        is_articulation = component_name in articulation_points

        explanation_parts = [
            (f"{component_name} has a betweenness " f"score of {score:.6f}."),
            (
                f"{len(transitive_dependents)} component(s) "
                "can reach it through dependency paths."
            ),
        ]

        if is_articulation:
            explanation_parts.append(
                "It is also a structural articulation point when "
                "dependency direction is ignored."
            )

        rankings.append(
            {
                "rank": rank,
                "component": component_name,
                "betweenness": score,
                "direct_dependents": int(graph.in_degree(component)),
                "transitive_dependents": len(transitive_dependents),
                "is_articulation_point": (is_articulation),
                "explanation": " ".join(explanation_parts),
            }
        )

    warnings = [
        (
            "Articulation points and bridges are calculated on an "
            "undirected projection of the dependency graph."
        )
    ]

    if betweenness_mode == "approximate":
        warnings.append(
            "Betweenness was approximated using "
            f"{betweenness_samples} sampled source nodes."
        )

    return {
        "rankings": rankings,
        "articulation_points": sorted(articulation_points),
        "bridges": bridges,
        "betweenness_mode": betweenness_mode,
        "betweenness_samples": betweenness_samples,
        "parameters": {
            "top_n": top_n,
            "exact_threshold": exact_threshold,
            "approximation_samples": (approximation_samples),
            "seed": seed,
            "weight": None,
        },
        "warnings": warnings,
    }
