from typing import Any

import networkx as nx
import pandas as pd


def prepare_dependency_data(
    dataframe: pd.DataFrame,
    source_column: str,
    target_column: str,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """
    Validate and normalize a dependency edge list.

    Each row represents:

        source component -> dependency

    Example:

        storefront -> api_gateway

    means that storefront depends on api_gateway.
    """

    required_columns = {source_column, target_column}
    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        raise ValueError(
            "Missing required column(s): " + ", ".join(sorted(missing_columns))
        )

    original_rows = len(dataframe)

    working_dataframe = dataframe[[source_column, target_column]].copy()

    missing_mask = (
        working_dataframe[source_column].isna()
        | working_dataframe[target_column].isna()
    )
    missing_rows = int(missing_mask.sum())

    working_dataframe = working_dataframe.loc[~missing_mask].copy()

    working_dataframe[source_column] = (
        working_dataframe[source_column].astype(str).str.strip()
    )
    working_dataframe[target_column] = (
        working_dataframe[target_column].astype(str).str.strip()
    )

    empty_mask = working_dataframe[source_column].eq("") | working_dataframe[
        target_column
    ].eq("")
    empty_rows = int(empty_mask.sum())

    working_dataframe = working_dataframe.loc[~empty_mask].copy()

    duplicate_edges = int(
        working_dataframe.duplicated(subset=[source_column, target_column]).sum()
    )

    working_dataframe = working_dataframe.drop_duplicates(
        subset=[source_column, target_column]
    ).reset_index(drop=True)

    self_loops = int(
        (working_dataframe[source_column] == working_dataframe[target_column]).sum()
    )

    data_quality = {
        "original_rows": original_rows,
        "missing_rows": missing_rows,
        "empty_rows": empty_rows,
        "duplicate_edges": duplicate_edges,
        "self_loops": self_loops,
        "valid_unique_edges": len(working_dataframe),
    }

    return working_dataframe, data_quality


def build_dependency_graph(
    dataframe: pd.DataFrame,
    source_column: str,
    target_column: str,
) -> nx.DiGraph:
    """
    Construct a directed NetworkX graph.

    Direction:

        component -> dependency
    """

    graph = nx.DiGraph()

    graph.add_edges_from(
        dataframe[[source_column, target_column]].itertuples(
            index=False,
            name=None,
        )
    )

    return graph


def find_representative_cycle(
    graph: nx.DiGraph,
) -> list[tuple[str, str]]:
    """
    Return one dependency cycle.

    We intentionally return only one cycle because a large graph can
    contain an enormous number of simple cycles.
    """

    if nx.is_directed_acyclic_graph(graph):
        return []

    cycle_edges = nx.find_cycle(
        graph,
        orientation="original",
    )

    return [(str(source), str(target)) for source, target, _direction in cycle_edges]


def format_cycle(
    cycle_edges: list[tuple[str, str]],
) -> str | None:
    """
    Convert cycle edges into a readable path.

    Example:

        monitoring -> logging -> monitoring
    """

    if not cycle_edges:
        return None

    cycle_nodes = [cycle_edges[0][0]]

    for _source, target in cycle_edges:
        cycle_nodes.append(target)

    return " -> ".join(cycle_nodes)


def analyze_dependency_health(
    dataframe: pd.DataFrame,
    source_column: str,
    target_column: str,
) -> dict[str, Any]:
    """
    Validate a dependency CSV and calculate graph-health information.
    """

    normalized_dataframe, data_quality = prepare_dependency_data(
        dataframe=dataframe,
        source_column=source_column,
        target_column=target_column,
    )

    graph = build_dependency_graph(
        dataframe=normalized_dataframe,
        source_column=source_column,
        target_column=target_column,
    )

    number_of_nodes = graph.number_of_nodes()
    number_of_edges = graph.number_of_edges()

    if number_of_nodes == 0:
        return {
            "graph": graph,
            "normalized_dataframe": normalized_dataframe,
            "data_quality": data_quality,
            "number_of_nodes": 0,
            "number_of_edges": 0,
            "density": 0.0,
            "weakly_connected_components": 0,
            "strongly_connected_components": 0,
            "is_directed_acyclic": True,
            "representative_cycle": [],
            "representative_cycle_text": None,
            "warnings": ["No valid dependency relationships were found."],
        }

    weakly_connected_components = nx.number_weakly_connected_components(graph)

    strongly_connected_components = nx.number_strongly_connected_components(graph)

    is_directed_acyclic = nx.is_directed_acyclic_graph(graph)

    representative_cycle = find_representative_cycle(graph)

    warnings: list[str] = []

    if data_quality["missing_rows"] > 0:
        warnings.append(
            f"{data_quality['missing_rows']} row(s) had a missing endpoint."
        )

    if data_quality["empty_rows"] > 0:
        warnings.append(f"{data_quality['empty_rows']} row(s) had an empty endpoint.")

    if data_quality["duplicate_edges"] > 0:
        warnings.append(
            f"{data_quality['duplicate_edges']} duplicate edge(s) were removed."
        )

    if data_quality["self_loops"] > 0:
        warnings.append(
            f"{data_quality['self_loops']} self-dependency relationship(s) were found."
        )

    if weakly_connected_components > 1:
        warnings.append(
            "The dependency graph contains "
            f"{weakly_connected_components} disconnected subsystem(s)."
        )

    if not is_directed_acyclic:
        warnings.append(
            "A dependency cycle was detected. Cycles can make build order, "
            "deployment order, and failure analysis more difficult."
        )

    return {
        "graph": graph,
        "normalized_dataframe": normalized_dataframe,
        "data_quality": data_quality,
        "number_of_nodes": number_of_nodes,
        "number_of_edges": number_of_edges,
        "density": nx.density(graph),
        "weakly_connected_components": (weakly_connected_components),
        "strongly_connected_components": (strongly_connected_components),
        "is_directed_acyclic": is_directed_acyclic,
        "representative_cycle": representative_cycle,
        "representative_cycle_text": format_cycle(representative_cycle),
        "warnings": warnings,
    }
