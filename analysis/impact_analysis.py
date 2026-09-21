from typing import Any

import networkx as nx
import pandas as pd


def build_dependency_graph(
    dataframe: pd.DataFrame,
    source_column: str,
    target_column: str,
) -> nx.DiGraph:
    """
    Build a directed software-dependency graph.

    Edge meaning:
        source -> target

    This means the source component depends on the target component.
    """
    if source_column not in dataframe.columns:
        raise ValueError(f"Source column '{source_column}' was not found.")

    if target_column not in dataframe.columns:
        raise ValueError(f"Target column '{target_column}' was not found.")

    if source_column == target_column:
        raise ValueError("Source and target columns must be different.")

    edge_dataframe = (
        dataframe[[source_column, target_column]].dropna().drop_duplicates().copy()
    )

    edge_dataframe[source_column] = (
        edge_dataframe[source_column].astype(str).str.strip()
    )

    edge_dataframe[target_column] = (
        edge_dataframe[target_column].astype(str).str.strip()
    )

    edge_dataframe = edge_dataframe[
        (edge_dataframe[source_column] != "") & (edge_dataframe[target_column] != "")
    ]

    graph = nx.DiGraph()

    graph.add_edges_from(
        edge_dataframe[[source_column, target_column]].itertuples(
            index=False,
            name=None,
        )
    )

    return graph


def find_cycle_membership(
    graph: nx.DiGraph,
    component: str,
) -> dict[str, Any]:
    """
    Determine whether the selected component participates
    in a dependency cycle.
    """
    for strongly_connected_component in nx.strongly_connected_components(graph):
        if component not in strongly_connected_component:
            continue

        members = sorted(strongly_connected_component)

        if len(members) > 1:
            return {
                "in_cycle": True,
                "cycle_members": members,
            }

        if graph.has_edge(component, component):
            return {
                "in_cycle": True,
                "cycle_members": members,
            }

        return {
            "in_cycle": False,
            "cycle_members": [],
        }

    return {
        "in_cycle": False,
        "cycle_members": [],
    }


def analyze_component_impact(
    graph: nx.DiGraph,
    component: str,
) -> dict[str, Any]:
    """
    Calculate the possible failure impact of one component.

    Because graph edges mean:

        component -> depends_on

    affected components are the nodes that can reach the
    selected component.

    We reverse the graph and run one breadth-first search
    starting from the selected component.
    """
    component = str(component).strip()

    if not component:
        raise ValueError("Component cannot be empty.")

    if component not in graph:
        raise ValueError(f"Component '{component}' was not found in the graph.")

    reversed_graph = graph.reverse(copy=False)

    reversed_paths = nx.single_source_shortest_path(
        reversed_graph,
        component,
    )

    impact_paths: dict[str, list[str]] = {}
    impact_layers: dict[int, list[str]] = {}

    for affected_component, reversed_path in reversed_paths.items():
        if affected_component == component:
            continue

        # The reversed graph gives:
        # failed component -> affected component
        #
        # Reverse that path to show the original dependency direction:
        # affected component -> ... -> failed component
        original_direction_path = list(reversed(reversed_path))

        impact_paths[str(affected_component)] = [
            str(node) for node in original_direction_path
        ]

        distance = len(original_direction_path) - 1

        impact_layers.setdefault(
            distance,
            [],
        ).append(str(affected_component))

    for distance in impact_layers:
        impact_layers[distance].sort()

    direct_dependents = sorted(
        component_name
        for component_name, path in impact_paths.items()
        if len(path) == 2
    )

    transitive_dependents = sorted(impact_paths)

    indirect_dependents = sorted(set(transitive_dependents) - set(direct_dependents))

    directly_used_dependencies = sorted(
        str(dependency) for dependency in graph.successors(component)
    )

    cycle_information = find_cycle_membership(
        graph=graph,
        component=component,
    )

    possible_other_components = max(
        graph.number_of_nodes() - 1,
        0,
    )

    blast_radius_percent = (
        (len(transitive_dependents) / possible_other_components) * 100
        if possible_other_components > 0
        else 0.0
    )

    maximum_impact_depth = max(
        impact_layers,
        default=0,
    )

    return {
        "component": component,
        "graph_summary": {
            "number_of_components": graph.number_of_nodes(),
            "number_of_dependencies": graph.number_of_edges(),
        },
        "impact_summary": {
            "direct_dependents": len(direct_dependents),
            "indirect_dependents": len(indirect_dependents),
            "total_affected_components": len(transitive_dependents),
            "blast_radius_percent": blast_radius_percent,
            "maximum_impact_depth": maximum_impact_depth,
        },
        "direct_dependents": direct_dependents,
        "indirect_dependents": indirect_dependents,
        "all_affected_components": transitive_dependents,
        "direct_dependencies_of_selected_component": (directly_used_dependencies),
        "impact_layers": {
            str(distance): components
            for distance, components in sorted(impact_layers.items())
        },
        "impact_paths": {
            component_name: impact_paths[component_name]
            for component_name in sorted(impact_paths)
        },
        "cycle": cycle_information,
        "methodology": {
            "edge_direction": "component -> depends_on",
            "impact_direction": (
                "Find components that can reach the " "selected component."
            ),
            "path_algorithm": ("Breadth-first search on the reversed graph"),
            "path_type": "Unweighted shortest dependency path",
        },
    }


def analyze_dependency_impact(
    dataframe: pd.DataFrame,
    source_column: str,
    target_column: str,
    component: str,
) -> dict[str, Any]:
    """
    Public function used by scripts and the Streamlit interface.
    """
    graph = build_dependency_graph(
        dataframe=dataframe,
        source_column=source_column,
        target_column=target_column,
    )

    return analyze_component_impact(
        graph=graph,
        component=component,
    )
