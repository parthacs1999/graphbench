from typing import Any

import networkx as nx
import pandas as pd

from analysis.bottleneck_analysis import (
    analyze_bottlenecks,
)
from analysis.core_analysis import (
    analyze_structural_core,
)
from analysis.critical_dependencies import (
    rank_critical_dependencies,
)
from analysis.dependency_health import (
    analyze_dependency_health,
)


def find_cycle_members(
    graph: nx.DiGraph,
) -> set[str]:
    """
    Return every component participating in a directed cycle.

    A strongly connected component containing multiple nodes forms
    a cyclic region. A self-loop is also a cycle.
    """

    cycle_members: set[str] = set()

    for component_group in nx.strongly_connected_components(graph):
        if len(component_group) > 1:
            cycle_members.update(str(component) for component in component_group)
            continue

        component = next(iter(component_group))

        if graph.has_edge(component, component):
            cycle_members.add(str(component))

    return cycle_members


def create_component_finding(
    component: str,
    critical_result: dict[str, Any],
    bottleneck_result: dict[str, Any],
    core_result: dict[str, Any],
    cycle_members: set[str],
    high_pagerank_components: set[str],
    high_betweenness_components: set[str],
) -> dict[str, Any]:
    """
    Merge all structural evidence for one component.
    """

    signals: list[str] = []
    cautions: list[str] = []

    if component in high_pagerank_components:
        signals.append("High PageRank dependency")

    if component in high_betweenness_components:
        signals.append("Important dependency-path connector")

    if core_result["is_deepest_core"]:
        signals.append("Member of the deepest structural core")

    if bottleneck_result["is_articulation_point"]:
        signals.append("Structural articulation point")

    if component in cycle_members:
        cautions.append(
            "Participates in a dependency cycle; "
            "PageRank may be reinforced by cyclic flow"
        )

    if not signals:
        signals.append("No top structural signal in the current analysis")

    return {
        "component": component,
        "structural_signal_count": len(
            [signal for signal in signals if not signal.startswith("No top")]
        ),
        "signals": signals,
        "cautions": cautions,
        "pagerank_rank": critical_result["rank"],
        "pagerank": critical_result["pagerank"],
        "direct_dependents": critical_result["dependent_count"],
        "direct_dependencies": critical_result["dependency_count"],
        "betweenness_rank": bottleneck_result["rank"],
        "betweenness": bottleneck_result["betweenness"],
        "transitive_dependents": bottleneck_result["transitive_dependents"],
        "is_articulation_point": bottleneck_result["is_articulation_point"],
        "core_number": core_result["core_number"],
        "is_deepest_core": core_result["is_deepest_core"],
        "in_dependency_cycle": (component in cycle_members),
    }


def generate_dependency_intelligence_report(
    dataframe: pd.DataFrame,
    source_column: str,
    target_column: str,
    top_n: int = 10,
    pagerank_alpha: float = 0.85,
    exact_betweenness_threshold: int = 2_000,
    approximation_samples: int = 500,
    seed: int = 42,
) -> dict[str, Any]:
    """
    Generate one explainable dependency-intelligence report.
    """

    health_report = analyze_dependency_health(
        dataframe=dataframe,
        source_column=source_column,
        target_column=target_column,
    )

    graph = health_report["graph"]

    if graph.number_of_nodes() == 0:
        return {
            "status": "no_valid_graph",
            "executive_summary": {
                "message": ("No valid dependency graph could be created.")
            },
            "graph_health": {
                key: value
                for key, value in health_report.items()
                if key
                not in {
                    "graph",
                    "normalized_dataframe",
                }
            },
            "review_candidates": [],
        }

    number_of_nodes = graph.number_of_nodes()

    critical_report = rank_critical_dependencies(
        graph=graph,
        top_n=number_of_nodes,
        alpha=pagerank_alpha,
    )

    bottleneck_report = analyze_bottlenecks(
        graph=graph,
        top_n=number_of_nodes,
        exact_threshold=(exact_betweenness_threshold),
        approximation_samples=(approximation_samples),
        seed=seed,
    )

    core_report = analyze_structural_core(
        graph=graph,
        top_n=number_of_nodes,
    )

    cycle_members = find_cycle_members(graph)

    critical_by_component = {
        result["component"]: result for result in critical_report["all_rankings"]
    }

    bottleneck_by_component = {
        result["component"]: result for result in bottleneck_report["rankings"]
    }

    core_by_component = {
        result["component"]: result for result in core_report["rankings"]
    }

    high_pagerank_components = {
        result["component"] for result in critical_report["all_rankings"][:5]
    }

    high_betweenness_components = {
        result["component"]
        for result in bottleneck_report["rankings"][:5]
        if result["betweenness"] > 0
    }

    component_findings = []

    for component in sorted(critical_by_component):
        component_findings.append(
            create_component_finding(
                component=component,
                critical_result=(critical_by_component[component]),
                bottleneck_result=(bottleneck_by_component[component]),
                core_result=(core_by_component[component]),
                cycle_members=cycle_members,
                high_pagerank_components=(high_pagerank_components),
                high_betweenness_components=(high_betweenness_components),
            )
        )

    component_findings.sort(
        key=lambda result: (
            -result["structural_signal_count"],
            -result["pagerank"],
            -result["betweenness"],
            result["component"],
        )
    )

    for index, finding in enumerate(
        component_findings,
        start=1,
    ):
        finding["review_rank"] = index

    selected_candidates = component_findings[: min(top_n, len(component_findings))]

    top_pagerank = critical_report["all_rankings"][0]

    top_bottleneck = bottleneck_report["rankings"][0]

    graph_health_export = {
        key: value
        for key, value in health_report.items()
        if key
        not in {
            "graph",
            "normalized_dataframe",
        }
    }

    status = "review_recommended" if health_report["warnings"] else "healthy"

    return {
        "status": status,
        "executive_summary": {
            "highest_pagerank_component": (top_pagerank["component"]),
            "highest_pagerank_score": (top_pagerank["pagerank"]),
            "strongest_bottleneck": (top_bottleneck["component"]),
            "strongest_betweenness_score": (top_bottleneck["betweenness"]),
            "maximum_core": core_report["maximum_core"],
            "deepest_core_size": len(core_report["deepest_core_components"]),
            "dependency_cycle_detected": (bool(cycle_members)),
            "cycle_members": sorted(cycle_members),
            "representative_cycle": (health_report["representative_cycle_text"]),
        },
        "graph_health": graph_health_export,
        "review_candidates": selected_candidates,
        "all_component_findings": (component_findings),
        "articulation_points": (bottleneck_report["articulation_points"]),
        "bridges": bottleneck_report["bridges"],
        "deepest_core_components": (core_report["deepest_core_components"]),
        "methodology": {
            "edge_direction": (f"{source_column} -> {target_column}"),
            "pagerank_alpha": pagerank_alpha,
            "pagerank_weight": None,
            "betweenness_mode": (bottleneck_report["betweenness_mode"]),
            "betweenness_samples": (bottleneck_report["betweenness_samples"]),
            "k_core_direction": ("undirected projection"),
            "random_seed": seed,
        },
        "warnings": list(health_report["warnings"])
        + list(bottleneck_report["warnings"])
        + list(core_report["warnings"]),
    }
