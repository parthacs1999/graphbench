from typing import Any

import networkx as nx


def explain_dependency(
    component: str,
    dependent_count: int,
    dependency_count: int,
    pagerank_score: float,
) -> str:
    """
    Create a plain-English explanation for a ranked component.
    """

    if dependent_count == 0:
        dependent_text = "No component directly depends on it in this dataset."
    elif dependent_count == 1:
        dependent_text = "One component directly depends on it."
    else:
        dependent_text = f"{dependent_count} components directly depend on it."

    if dependency_count == 0:
        dependency_text = "It has no outgoing dependency in this dataset."
    elif dependency_count == 1:
        dependency_text = "It directly depends on one other component."
    else:
        dependency_text = (
            f"It directly depends on {dependency_count} " "other components."
        )

    return (
        f"{component} has a PageRank score of "
        f"{pagerank_score:.6f}. "
        f"{dependent_text} {dependency_text}"
    )


def rank_critical_dependencies(
    graph: nx.DiGraph,
    top_n: int = 10,
    alpha: float = 0.85,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> dict[str, Any]:
    """
    Rank dependencies using direct dependent count and PageRank.

    Edge direction:

        component -> dependency

    Therefore, PageRank flows toward dependencies.
    """

    if not graph.is_directed():
        raise ValueError("Critical dependency ranking requires a directed graph.")

    if graph.number_of_nodes() == 0:
        return {
            "rankings": [],
            "pagerank_sum": 0.0,
            "top_component": None,
            "parameters": {
                "alpha": alpha,
                "max_iterations": max_iterations,
                "tolerance": tolerance,
            },
        }

    if top_n <= 0:
        raise ValueError("top_n must be greater than zero.")

    if not 0 < alpha < 1:
        raise ValueError("alpha must be greater than 0 and less than 1.")

    pagerank_scores = nx.pagerank(
        graph,
        alpha=alpha,
        max_iter=max_iterations,
        tol=tolerance,
        weight=None,
    )

    number_of_nodes = graph.number_of_nodes()
    normalization_denominator = max(
        1,
        number_of_nodes - 1,
    )

    rankings: list[dict[str, Any]] = []

    for component in graph.nodes:
        dependent_count = int(graph.in_degree(component))
        dependency_count = int(graph.out_degree(component))

        in_degree_centrality = dependent_count / normalization_denominator

        pagerank_score = float(pagerank_scores[component])

        rankings.append(
            {
                "component": str(component),
                "pagerank": pagerank_score,
                "dependent_count": dependent_count,
                "dependency_count": dependency_count,
                "in_degree_centrality": (in_degree_centrality),
                "explanation": explain_dependency(
                    component=str(component),
                    dependent_count=dependent_count,
                    dependency_count=dependency_count,
                    pagerank_score=pagerank_score,
                ),
            }
        )

    rankings.sort(
        key=lambda result: (
            -result["pagerank"],
            -result["dependent_count"],
            result["component"],
        )
    )

    for index, result in enumerate(
        rankings,
        start=1,
    ):
        result["rank"] = index

    selected_rankings = rankings[: min(top_n, len(rankings))]

    return {
        "rankings": selected_rankings,
        "all_rankings": rankings,
        "pagerank_sum": sum(pagerank_scores.values()),
        "top_component": (rankings[0]["component"] if rankings else None),
        "parameters": {
            "alpha": alpha,
            "max_iterations": max_iterations,
            "tolerance": tolerance,
            "weight": None,
        },
    }
