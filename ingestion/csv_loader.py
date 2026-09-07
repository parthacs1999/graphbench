from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backends.base import Edge


@dataclass
class NormalizedGraph:
    number_of_nodes: int
    edges: list[Edge]

    label_to_id: dict[str, int]
    id_to_label: dict[int, str]

    original_rows: int
    valid_rows: int
    missing_rows: int
    duplicate_edges: int
    self_loops: int


def load_edge_csv(
    file_path: str | Path,
    source_column: str,
    target_column: str,
) -> NormalizedGraph:
    dataframe = pd.read_csv(file_path)

    required_columns = {
        source_column,
        target_column,
    }

    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        missing_names = ", ".join(sorted(missing_columns))

        raise ValueError(f"Missing required columns: {missing_names}")

    original_rows = len(dataframe)

    edges_dataframe = dataframe[[source_column, target_column]].copy()

    missing_mask = edges_dataframe.isna().any(axis=1)
    missing_rows = int(missing_mask.sum())

    edges_dataframe = edges_dataframe[~missing_mask].copy()

    edges_dataframe[source_column] = (
        edges_dataframe[source_column].astype(str).str.strip()
    )

    edges_dataframe[target_column] = (
        edges_dataframe[target_column].astype(str).str.strip()
    )

    empty_mask = (edges_dataframe[source_column] == "") | (
        edges_dataframe[target_column] == ""
    )

    missing_rows += int(empty_mask.sum())

    edges_dataframe = edges_dataframe[~empty_mask].copy()

    duplicate_edges = int(
        edges_dataframe.duplicated(subset=[source_column, target_column]).sum()
    )

    # DiGraph treats duplicate source-target pairs as one edge.
    # Remove duplicates so Ladybug receives equivalent data.
    edges_dataframe = edges_dataframe.drop_duplicates(
        subset=[source_column, target_column]
    )

    self_loops = int(
        (edges_dataframe[source_column] == edges_dataframe[target_column]).sum()
    )

    all_labels = pd.concat(
        [
            edges_dataframe[source_column],
            edges_dataframe[target_column],
        ],
        ignore_index=True,
    ).unique()

    label_to_id = {label: node_id for node_id, label in enumerate(all_labels)}

    id_to_label = {node_id: label for label, node_id in label_to_id.items()}

    edges = [
        (
            label_to_id[source],
            label_to_id[target],
        )
        for source, target in edges_dataframe.itertuples(
            index=False,
            name=None,
        )
    ]

    return NormalizedGraph(
        number_of_nodes=len(label_to_id),
        edges=edges,
        label_to_id=label_to_id,
        id_to_label=id_to_label,
        original_rows=original_rows,
        valid_rows=len(edges_dataframe),
        missing_rows=missing_rows,
        duplicate_edges=duplicate_edges,
        self_loops=self_loops,
    )
