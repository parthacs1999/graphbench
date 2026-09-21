import hashlib
import io
import json
from pathlib import Path
from typing import Any

import altair as alt
import networkx as nx
import pandas as pd
import streamlit as st

from analysis.impact_analysis import analyze_dependency_impact
from analysis.dependency_report import generate_dependency_intelligence_report
from benchmarks.reproducibility import collect_environment_metadata
from ingestion.csv_loader import load_edge_csv

st.set_page_config(
    page_title="GraphBench Dependency Intelligence",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="collapsed",
)


SAMPLE_FILE = Path("data/sample_dependency_risk.csv")
MAX_ANALYSIS_NODES = 2_000


st.markdown(
    """
<style>
    .block-container {
        max-width: 1180px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }

    [data-testid="stSidebar"], [data-testid="collapsedControl"] {
        display: none;
    }

    .hero {
        border: 1px solid rgba(148, 163, 184, .20);
        border-radius: 22px;
        padding: 1.5rem 1.65rem;
        background:
            radial-gradient(circle at 95% 0%, rgba(59, 130, 246, .16), transparent 22rem),
            rgba(15, 23, 42, .36);
        margin-bottom: 1rem;
    }

    .eyebrow {
        color: #60A5FA;
        font-size: .74rem;
        font-weight: 800;
        letter-spacing: .14em;
        text-transform: uppercase;
        margin-bottom: .45rem;
    }

    .hero h1 {
        font-size: clamp(2.1rem, 5vw, 3.45rem);
        letter-spacing: -.055em;
        line-height: 1;
        margin: 0;
    }

    .hero p {
        color: #CBD5E1;
        font-size: 1.02rem;
        line-height: 1.65;
        max-width: 790px;
        margin: .85rem 0 0;
    }

    .empty-state {
        text-align: center;
        border: 1px dashed rgba(96, 165, 250, .36);
        border-radius: 20px;
        padding: 3.2rem 2rem 2.7rem;
        margin-top: 1.1rem;
        background: rgba(15, 23, 42, .22);
    }

    .empty-state h2 {
        margin: 0 0 .65rem;
        letter-spacing: -.035em;
    }

    .empty-state p {
        color: #94A3B8;
        max-width: 650px;
        margin: 0 auto 1.4rem;
        line-height: 1.6;
    }

    .step-strip {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: .65rem;
        margin: 1.1rem 0;
    }

    .step-item {
        border: 1px solid rgba(148, 163, 184, .18);
        border-radius: 12px;
        padding: .8rem .9rem;
        color: #94A3B8;
        font-size: .86rem;
    }

    .step-item strong { color: #E2E8F0; display: block; margin-bottom: .2rem; }
    .step-item.active { border-color: #60A5FA; background: rgba(59, 130, 246, .10); }

    .summary-card, div[data-testid="stMetric"] {
        border: 1px solid rgba(148, 163, 184, .18);
        border-radius: 14px;
        padding: .75rem .9rem;
        background: rgba(15, 23, 42, .25);
    }

    .summary-card {
        min-height: 132px;
        padding: 1rem 1.05rem;
    }

    .summary-card .label {
        color: #94A3B8;
        font-size: .78rem;
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: .07em;
    }

    .summary-card h3 { margin: .45rem 0 .35rem; font-size: 1.22rem; }
    .summary-card p { color: #94A3B8; margin: 0; font-size: .87rem; line-height: 1.45; }

    .action-card {
        border-left: 3px solid #60A5FA;
        border-radius: 10px;
        padding: .9rem 1rem;
        background: rgba(30, 41, 59, .48);
        min-height: 118px;
    }

    .action-card strong { display: block; margin-bottom: .35rem; }
    .action-card span { color: #A8B3C7; font-size: .88rem; line-height: 1.5; }

    .section-intro { color: #94A3B8; margin-top: -.35rem; }

    div.stButton > button, div[data-testid="stDownloadButton"] > button {
        min-height: 2.75rem;
        border-radius: 10px;
        font-weight: 700;
    }

    @media (max-width: 760px) {
        .step-strip { grid-template-columns: 1fr; }
        .hero { padding: 1.2rem; }
    }
</style>
""",
    unsafe_allow_html=True,
)


def find_first(data: Any, keys: set[str]) -> Any:
    """Find the first matching key in a nested report."""
    if isinstance(data, dict):
        for key, value in data.items():
            if key in keys and value not in (None, "", []):
                return value
        for value in data.values():
            found = find_first(value, keys)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = find_first(item, keys)
            if found is not None:
                return found
    return None


def number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def get_candidates(report: dict) -> list[dict]:
    candidates = (
        report.get("review_candidates")
        or report.get("components_for_review")
        or report.get("ranked_components")
        or []
    )
    return candidates if isinstance(candidates, list) else []


def candidate_value(candidate: dict, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in candidate and candidate[key] is not None:
            return candidate[key]
    return default


def summarize_report(report: dict) -> dict:
    candidates = get_candidates(report)

    pagerank_candidate = max(
        candidates,
        key=lambda item: number(
            candidate_value(item, "pagerank", "pagerank_score", default=0)
        ),
        default={},
    )
    bottleneck_candidate = max(
        candidates,
        key=lambda item: number(
            candidate_value(item, "betweenness", "betweenness_score", default=0)
        ),
        default={},
    )

    highest_raw = find_first(
        report,
        {"highest_pagerank", "highest_pagerank_component", "most_critical_component"},
    )
    if isinstance(highest_raw, dict):
        highest_component = highest_raw.get("component", highest_raw.get("name"))
        highest_score = number(highest_raw.get("score", highest_raw.get("pagerank")))
    else:
        highest_component = highest_raw
        highest_score = number(
            find_first(report, {"highest_pagerank_score", "top_pagerank_score"})
        )

    if not highest_component:
        highest_component = candidate_value(
            pagerank_candidate, "component", "name", default="Not available"
        )
    if highest_score == 0:
        highest_score = number(
            candidate_value(pagerank_candidate, "pagerank", "pagerank_score", default=0)
        )

    bottleneck_raw = find_first(
        report,
        {"strongest_bottleneck", "strongest_bottleneck_component", "top_bottleneck"},
    )
    if isinstance(bottleneck_raw, dict):
        bottleneck_component = bottleneck_raw.get(
            "component", bottleneck_raw.get("name")
        )
        bottleneck_score = number(
            bottleneck_raw.get("score", bottleneck_raw.get("betweenness"))
        )
    else:
        bottleneck_component = bottleneck_raw
        bottleneck_score = number(
            find_first(report, {"strongest_bottleneck_score", "top_betweenness_score"})
        )

    if not bottleneck_component:
        bottleneck_component = candidate_value(
            bottleneck_candidate, "component", "name", default="Not available"
        )
    if bottleneck_score == 0:
        bottleneck_score = number(
            candidate_value(
                bottleneck_candidate,
                "betweenness",
                "betweenness_score",
                default=0,
            )
        )

    cycle = find_first(report, {"representative_cycle", "dependency_cycle", "cycle"})
    if isinstance(cycle, bool):
        cycle = None

    maximum_core = number(
        find_first(report, {"maximum_core_number", "max_core_number", "deepest_core"})
    )
    deepest_size = number(
        find_first(report, {"deepest_core_size", "deepest_core_component_count"})
    )

    return {
        "status": find_first(report, {"status"}) or "review_recommended",
        "highest_component": str(highest_component),
        "highest_score": highest_score,
        "bottleneck_component": str(bottleneck_component),
        "bottleneck_score": bottleneck_score,
        "cycle": cycle,
        "maximum_core": int(maximum_core),
        "deepest_size": int(deepest_size),
        "candidates": candidates,
    }


@st.cache_data(show_spinner=False)
def build_graph_visualization(
    edges: tuple[tuple[str, str], ...],
    lens: str,
    maximum_visible_nodes: int = 100,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Create a readable, metric-aware subgraph for the selected analysis lens."""
    graph = nx.DiGraph()
    graph.add_edges_from(edges)

    if graph.number_of_nodes() == 0:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}

    pagerank = nx.pagerank(graph, alpha=0.85)
    if graph.number_of_nodes() <= 500:
        betweenness = nx.betweenness_centrality(graph, normalized=True)
        betweenness_method = "exact"
    else:
        sample_size = min(100, graph.number_of_nodes())
        betweenness = nx.betweenness_centrality(
            graph,
            k=sample_size,
            normalized=True,
            seed=42,
        )
        betweenness_method = f"approximate ({sample_size} sampled nodes)"

    undirected = graph.to_undirected()
    core_numbers = nx.core_number(undirected) if graph.number_of_nodes() else {}

    cycle_nodes: set[str] = set()
    for component in nx.strongly_connected_components(graph):
        if len(component) > 1:
            cycle_nodes.update(str(node) for node in component)
        elif component:
            node = next(iter(component))
            if graph.has_edge(node, node):
                cycle_nodes.add(str(node))

    if lens == "Critical dependencies":
        metric = pagerank
        metric_title = "PageRank"
    elif lens == "Path bottlenecks":
        metric = betweenness
        metric_title = "Betweenness"
    elif lens == "Structural core":
        metric = core_numbers
        metric_title = "Core number"
    else:
        metric = {node: 1 if str(node) in cycle_nodes else 0 for node in graph.nodes}
        metric_title = "Cycle member"

    ranked_nodes = sorted(
        graph.nodes,
        key=lambda node: (
            float(metric.get(node, 0)),
            float(pagerank.get(node, 0)),
            graph.degree(node),
        ),
        reverse=True,
    )

    if graph.number_of_nodes() <= maximum_visible_nodes:
        visible_nodes = set(graph.nodes)
        focused = False
    else:
        visible_nodes = set(ranked_nodes[: min(60, maximum_visible_nodes)])
        for node in list(visible_nodes):
            visible_nodes.update(graph.predecessors(node))
            visible_nodes.update(graph.successors(node))
            if len(visible_nodes) >= maximum_visible_nodes:
                break
        visible_nodes = set(
            sorted(
                visible_nodes,
                key=lambda node: (
                    float(metric.get(node, 0)),
                    float(pagerank.get(node, 0)),
                ),
                reverse=True,
            )[:maximum_visible_nodes]
        )
        focused = True

    view = graph.subgraph(visible_nodes).copy()
    positions = nx.spring_layout(
        view,
        seed=42,
        iterations=80 if view.number_of_nodes() <= 100 else 40,
        k=None,
    )

    metric_values = [float(metric.get(node, 0)) for node in view.nodes]
    maximum_metric = max(metric_values, default=0)

    node_rows = []
    for node in view.nodes:
        metric_value = float(metric.get(node, 0))
        normalized_metric = metric_value / maximum_metric if maximum_metric > 0 else 0
        node_rows.append(
            {
                "node": str(node),
                "x": float(positions[node][0]),
                "y": float(positions[node][1]),
                "metric": metric_value,
                "metric_label": metric_title,
                "size": 120 + (1_050 * normalized_metric),
                "pagerank": float(pagerank.get(node, 0)),
                "betweenness": float(betweenness.get(node, 0)),
                "core": int(core_numbers.get(node, 0)),
                "cycle_status": (
                    "In dependency cycle"
                    if str(node) in cycle_nodes
                    else "Not in cycle"
                ),
                "in_cycle": str(node) in cycle_nodes,
                "dependencies": int(graph.out_degree(node)),
                "dependents": int(graph.in_degree(node)),
            }
        )

    edge_rows = []
    for source, target in view.edges:
        edge_rows.append(
            {
                "source": str(source),
                "target": str(target),
                "x": float(positions[source][0]),
                "y": float(positions[source][1]),
                "x2": float(positions[target][0]),
                "y2": float(positions[target][1]),
                "cycle_edge": str(source) in cycle_nodes and str(target) in cycle_nodes,
            }
        )

    label_nodes = set(ranked_nodes[:8])
    if view.number_of_nodes() <= 20:
        label_nodes = set(view.nodes)
    label_rows = [row for row in node_rows if row["node"] in label_nodes]

    metadata = {
        "total_nodes": graph.number_of_nodes(),
        "visible_nodes": view.number_of_nodes(),
        "total_edges": graph.number_of_edges(),
        "visible_edges": view.number_of_edges(),
        "focused": focused,
        "metric_title": metric_title,
        "betweenness_method": betweenness_method,
        "cycle_nodes": len(cycle_nodes),
    }
    return (
        pd.DataFrame(node_rows),
        pd.DataFrame(edge_rows),
        pd.DataFrame(label_rows),
        metadata,
    )


def render_graph_explorer(dataset_info: dict) -> None:
    st.markdown("### Explore the architecture visually")
    st.caption(
        "The arrows follow your CSV direction: source component → dependency. "
        "Change the lens to see how each graph algorithm interprets the same architecture."
    )

    control_column, explanation_column = st.columns([1, 1.35])
    with control_column:
        lens = st.selectbox(
            "Analysis lens",
            [
                "Critical dependencies",
                "Path bottlenecks",
                "Structural core",
                "Dependency cycles",
            ],
        )
    lens_explanations = {
        "Critical dependencies": "Larger and brighter nodes have higher PageRank. They receive dependency importance from other important components.",
        "Path bottlenecks": "Larger and brighter nodes have higher betweenness. They sit on more dependency paths.",
        "Structural core": "Larger and brighter nodes belong to deeper K-core layers. Direction is ignored for this lens.",
        "Dependency cycles": "Red nodes participate in a circular dependency. Gray nodes do not.",
    }
    with explanation_column:
        st.info(lens_explanations[lens])

    edge_tuples = tuple(
        (str(edge[0]), str(edge[1])) for edge in dataset_info.get("graph_edges", [])
    )
    nodes, edges, labels, metadata = build_graph_visualization(edge_tuples, lens)

    if nodes.empty:
        st.info("No graph connections are available to visualize.")
        return

    edge_color = (
        alt.condition(
            "datum.cycle_edge",
            alt.value("#EF4444"),
            alt.value("#64748B"),
        )
        if lens == "Dependency cycles"
        else alt.value("#64748B")
    )

    edge_layer = (
        alt.Chart(edges)
        .mark_rule(opacity=0.34, strokeWidth=1.1)
        .encode(
            x=alt.X("x:Q", axis=None),
            y=alt.Y("y:Q", axis=None),
            x2="x2:Q",
            y2="y2:Q",
            color=edge_color,
            tooltip=["source:N", "target:N"],
        )
    )

    if lens == "Dependency cycles":
        node_color = alt.Color(
            "cycle_status:N",
            title=None,
            scale=alt.Scale(
                domain=["In dependency cycle", "Not in cycle"],
                range=["#EF4444", "#64748B"],
            ),
            legend=alt.Legend(orient="top"),
        )
    else:
        node_color = alt.Color(
            "metric:Q",
            title=metadata["metric_title"],
            scale=alt.Scale(range=["#60A5FA", "#F59E0B"]),
            legend=alt.Legend(orient="top"),
        )

    node_layer = (
        alt.Chart(nodes)
        .mark_circle(stroke="#E2E8F0", strokeWidth=0.65, opacity=0.94)
        .encode(
            x=alt.X("x:Q", axis=None),
            y=alt.Y("y:Q", axis=None),
            size=alt.Size("size:Q", scale=None, legend=None),
            color=node_color,
            tooltip=[
                alt.Tooltip("node:N", title="Component"),
                alt.Tooltip("pagerank:Q", title="PageRank", format=".6f"),
                alt.Tooltip("betweenness:Q", title="Betweenness", format=".6f"),
                alt.Tooltip("core:Q", title="Core number"),
                alt.Tooltip("cycle_status:N", title="Cycle"),
                alt.Tooltip("dependents:Q", title="Direct dependents"),
                alt.Tooltip("dependencies:Q", title="Dependencies"),
            ],
        )
    )

    label_layer = (
        alt.Chart(labels)
        .mark_text(dy=-13, fontSize=11, color="#E2E8F0")
        .encode(
            x=alt.X("x:Q", axis=None),
            y=alt.Y("y:Q", axis=None),
            text="node:N",
        )
    )

    graph_chart = (
        (edge_layer + node_layer + label_layer).properties(height=590).interactive()
    )
    st.altair_chart(graph_chart, width="stretch")
    st.caption(
        "Scroll over the graph to zoom, drag to move around, and use the "
        "chart toolbar to reset or open the graph in fullscreen."
    )

    graph_metrics = st.columns(4)
    graph_metrics[0].metric("Visible components", f"{metadata['visible_nodes']:,}")
    graph_metrics[1].metric("Visible dependencies", f"{metadata['visible_edges']:,}")
    graph_metrics[2].metric("Cycle members", f"{metadata['cycle_nodes']:,}")
    graph_metrics[3].metric("Layout", "Focused" if metadata["focused"] else "Complete")

    if metadata["focused"]:
        st.caption(
            f"To keep the graph readable, this view focuses on the most important nodes "
            f"and their neighbors ({metadata['visible_nodes']:,} of "
            f"{metadata['total_nodes']:,} total components). The analysis still uses the full graph."
        )
    if lens == "Path bottlenecks":
        st.caption(f"Betweenness calculation used: {metadata['betweenness_method']}.")


def render_impact_graph(impact_report: dict, graph_edges: list[list[str]]) -> None:
    selected_component = impact_report["component"]
    direct_dependents = set(impact_report["direct_dependents"])
    indirect_dependents = set(impact_report["indirect_dependents"])
    affected_components = direct_dependents | indirect_dependents | {selected_component}

    complete_graph = nx.DiGraph()
    complete_graph.add_edges_from(
        (str(source), str(target)) for source, target in graph_edges
    )
    impact_graph = complete_graph.subgraph(affected_components).copy()

    if impact_graph.number_of_nodes() == 0:
        st.info("No affected graph is available to visualize.")
        return

    positions = nx.spring_layout(impact_graph, seed=42, iterations=80)
    node_rows = []

    for node in impact_graph.nodes:
        if node == selected_component:
            impact_type = "Selected failure"
            node_size = 1_100
        elif node in direct_dependents:
            impact_type = "Directly affected"
            node_size = 800
        else:
            impact_type = "Indirectly affected"
            node_size = 600

        impact_path = impact_report["impact_paths"].get(str(node), [str(node)])
        node_rows.append(
            {
                "component": str(node),
                "x": float(positions[node][0]),
                "y": float(positions[node][1]),
                "impact_type": impact_type,
                "size": node_size,
                "impact_path": " → ".join(impact_path),
            }
        )

    edge_rows = [
        {
            "source": str(source),
            "target": str(target),
            "x": float(positions[source][0]),
            "y": float(positions[source][1]),
            "x2": float(positions[target][0]),
            "y2": float(positions[target][1]),
        }
        for source, target in impact_graph.edges
    ]

    node_dataframe = pd.DataFrame(node_rows)
    edge_dataframe = pd.DataFrame(edge_rows)

    if edge_dataframe.empty:
        edge_chart = (
            alt.Chart(pd.DataFrame({"x": [], "y": [], "x2": [], "y2": []}))
            .mark_rule()
            .encode(
                x=alt.X("x:Q", axis=None),
                y=alt.Y("y:Q", axis=None),
                x2="x2:Q",
                y2="y2:Q",
            )
        )
    else:
        edge_chart = (
            alt.Chart(edge_dataframe)
            .mark_rule(color="#64748B", opacity=0.45, strokeWidth=1.4)
            .encode(
                x=alt.X("x:Q", axis=None),
                y=alt.Y("y:Q", axis=None),
                x2="x2:Q",
                y2="y2:Q",
                tooltip=[
                    alt.Tooltip("source:N", title="Dependent"),
                    alt.Tooltip("target:N", title="Dependency"),
                ],
            )
        )

    node_chart = (
        alt.Chart(node_dataframe)
        .mark_circle(stroke="#E2E8F0", strokeWidth=0.8, opacity=0.96)
        .encode(
            x=alt.X("x:Q", axis=None),
            y=alt.Y("y:Q", axis=None),
            size=alt.Size("size:Q", scale=None, legend=None),
            color=alt.Color(
                "impact_type:N",
                title=None,
                scale=alt.Scale(
                    domain=[
                        "Selected failure",
                        "Directly affected",
                        "Indirectly affected",
                    ],
                    range=["#EF4444", "#F59E0B", "#3B82F6"],
                ),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip("component:N", title="Component"),
                alt.Tooltip("impact_type:N", title="Impact"),
                alt.Tooltip("impact_path:N", title="Dependency path"),
            ],
        )
    )

    label_chart = (
        alt.Chart(node_dataframe)
        .mark_text(dy=-16, fontSize=11, color="#E2E8F0")
        .encode(
            x=alt.X("x:Q", axis=None),
            y=alt.Y("y:Q", axis=None),
            text="component:N",
        )
    )

    impact_chart = (
        (edge_chart + node_chart + label_chart).properties(height=560).interactive()
    )

    st.altair_chart(impact_chart, width="stretch")
    st.caption(
        "Scroll over the graph to zoom, drag to move around, and use the "
        "chart toolbar to reset or open the graph in fullscreen."
    )
    st.caption(
        "Relationship direction: dependent component → dependency. Red is the "
        "simulated failure, orange is directly affected, and blue is indirectly affected."
    )


def render_impact_simulator(dataset_info: dict) -> None:
    st.markdown("### Simulate a component failure")
    st.caption(
        "Choose one component to see which services directly or indirectly depend on it."
    )

    graph_edges = dataset_info.get("graph_edges", [])
    if not graph_edges:
        st.info("Run dependency analysis again to make graph data available.")
        return

    source_column = dataset_info["source_column"]
    target_column = dataset_info["target_column"]
    edge_dataframe = pd.DataFrame(
        graph_edges,
        columns=[source_column, target_column],
    )
    components = sorted(
        set(edge_dataframe[source_column]) | set(edge_dataframe[target_column])
    )

    selection_column, button_column = st.columns([2, 1])
    selected_component = selection_column.selectbox(
        "Component to simulate",
        components,
        help="GraphBench will treat this component as unavailable.",
    )
    run_simulation = button_column.button(
        "Simulate failure",
        type="primary",
        width="stretch",
    )

    if run_simulation:
        with st.spinner("Calculating failure impact..."):
            impact_report = analyze_dependency_impact(
                dataframe=edge_dataframe,
                source_column=source_column,
                target_column=target_column,
                component=selected_component,
            )
        st.session_state["impact_report"] = impact_report
        st.session_state["impact_component"] = selected_component

    impact_report = st.session_state.get("impact_report")
    simulated_component = st.session_state.get("impact_component")

    if impact_report is None or simulated_component != selected_component:
        st.info("Select a component and run the failure simulation.")
        return

    summary = impact_report["impact_summary"]
    metric_columns = st.columns(4)
    metric_columns[0].metric("Directly affected", summary["direct_dependents"])
    metric_columns[1].metric("Indirectly affected", summary["indirect_dependents"])
    metric_columns[2].metric(
        "Total blast radius",
        f"{summary['total_affected_components']} components",
    )
    metric_columns[3].metric(
        "Graph affected",
        f"{summary['blast_radius_percent']:.2f}%",
    )

    if impact_report["cycle"]["in_cycle"]:
        cycle_members = ", ".join(impact_report["cycle"]["cycle_members"])
        st.warning(
            f"**{selected_component}** participates in a dependency cycle with: "
            f"**{cycle_members}**."
        )

    blast_radius = summary["blast_radius_percent"]
    if summary["total_affected_components"] == 0:
        st.success(
            "No other component depends on this component in the uploaded graph."
        )
    elif blast_radius >= 50:
        st.error(
            "High potential blast radius. More than half of the other components "
            "could be affected."
        )
    elif blast_radius >= 20:
        st.warning(
            "Moderate potential blast radius. Review fallbacks and recovery procedures."
        )
    else:
        st.info(
            "The selected component has a relatively limited structural blast radius."
        )

    graph_tab, paths_tab, layers_tab = st.tabs(
        ["Impact graph", "Dependency paths", "Impact layers"]
    )

    with graph_tab:
        render_impact_graph(impact_report=impact_report, graph_edges=graph_edges)

    with paths_tab:
        path_rows = [
            {
                "Affected component": affected_component,
                "Distance": len(path) - 1,
                "Impact path": " → ".join(path),
            }
            for affected_component, path in impact_report["impact_paths"].items()
        ]
        if path_rows:
            path_dataframe = pd.DataFrame(path_rows).sort_values(
                ["Distance", "Affected component"]
            )
            st.dataframe(path_dataframe, width="stretch", hide_index=True)
        else:
            st.info("No dependency paths were found.")

    with layers_tab:
        if not impact_report["impact_layers"]:
            st.info("No affected layers were found.")
        for distance, layer_components in impact_report["impact_layers"].items():
            layer_name = (
                "Direct dependents"
                if int(distance) == 1
                else f"{distance} dependency steps away"
            )
            st.markdown(f"**{layer_name}**")
            st.write(", ".join(layer_components))

    st.download_button(
        "Download impact report",
        json.dumps(impact_report, indent=2),
        f"impact_report_{selected_component}.json",
        "application/json",
        width="stretch",
    )


def cycle_text(cycle: Any) -> str | None:
    if isinstance(cycle, list) and cycle:
        return " → ".join(str(item) for item in cycle)
    if isinstance(cycle, str) and cycle.strip():
        return cycle.strip()
    return None


def initialize_state() -> None:
    defaults = {
        "show_setup": False,
        "wizard_step": 1,
        "wizard_bytes": None,
        "wizard_name": None,
        "wizard_source": None,
        "wizard_target": None,
        "dependency_report": None,
        "dataset_info": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


initialize_state()


def reset_wizard() -> None:
    st.session_state["wizard_step"] = 1
    st.session_state["wizard_bytes"] = None
    st.session_state["wizard_name"] = None
    st.session_state["wizard_source"] = None
    st.session_state["wizard_target"] = None
    st.session_state.pop("impact_report", None)
    st.session_state.pop("impact_component", None)


@st.dialog("Set up dependency analysis", width="large")
def setup_dialog() -> None:
    step = st.session_state["wizard_step"]
    st.markdown(
        f"""
<div class="step-strip">
    <div class="step-item {'active' if step == 1 else ''}"><strong>1. Choose data</strong>Sample or CSV upload</div>
    <div class="step-item {'active' if step == 2 else ''}"><strong>2. Define direction</strong>Which component depends on which</div>
    <div class="step-item {'active' if step == 3 else ''}"><strong>3. Review and run</strong>Validate before analysis</div>
</div>
""",
        unsafe_allow_html=True,
    )

    if step == 1:
        st.markdown("### Choose dependency data")
        st.caption("Each CSV row should connect one component to one dependency.")
        source_type = st.radio(
            "Data source",
            ["Try the guided sample", "Upload my CSV"],
            horizontal=True,
            label_visibility="collapsed",
        )

        selected_bytes = None
        selected_name = None

        if source_type == "Try the guided sample":
            if not SAMPLE_FILE.exists():
                st.error(f"Missing `{SAMPLE_FILE}`.")
            else:
                selected_bytes = SAMPLE_FILE.read_bytes()
                selected_name = SAMPLE_FILE.name
                st.info(
                    "The sample represents software services and packages. It includes "
                    "an intentional dependency cycle so you can see how GraphBench explains risk."
                )
                st.dataframe(
                    pd.read_csv(io.BytesIO(selected_bytes)).head(8),
                    width="stretch",
                    hide_index=True,
                )
        else:
            uploaded = st.file_uploader(
                "Dependency edge-list CSV",
                type=["csv"],
                help="The file needs at least two columns and one data row.",
            )
            if uploaded is not None:
                selected_bytes = uploaded.getvalue()
                selected_name = uploaded.name
                try:
                    uploaded_frame = pd.read_csv(io.BytesIO(selected_bytes))
                    st.dataframe(
                        uploaded_frame.head(8), width="stretch", hide_index=True
                    )
                except Exception as error:
                    st.error(f"Could not read this CSV: {error}")
                    selected_bytes = None

        if st.button(
            "Continue to relationship direction",
            type="primary",
            width="stretch",
            disabled=selected_bytes is None,
        ):
            st.session_state["wizard_bytes"] = selected_bytes
            st.session_state["wizard_name"] = selected_name
            st.session_state["wizard_step"] = 2
            st.rerun()

    elif step == 2:
        try:
            frame = pd.read_csv(io.BytesIO(st.session_state["wizard_bytes"]))
        except Exception as error:
            st.error(f"Could not read the selected CSV: {error}")
            if st.button("Return to data selection"):
                reset_wizard()
                st.rerun()
            return

        columns = list(frame.columns)
        st.markdown("### Tell us what one row means")
        st.caption("This direction changes how every result is interpreted.")

        default_source = columns.index("component") if "component" in columns else 0
        default_target = (
            columns.index("depends_on")
            if "depends_on" in columns
            else min(1, len(columns) - 1)
        )
        source_column = st.selectbox(
            "Component column",
            columns,
            index=default_source,
            help="The component that has the dependency.",
        )
        target_column = st.selectbox(
            "Dependency column",
            columns,
            index=default_target,
            help="The component being depended upon.",
        )

        if source_column == target_column:
            st.error("Choose two different columns.")
        else:
            st.info(
                f"**{source_column} → {target_column}** means: each value in "
                f"`{source_column}` depends on the value in `{target_column}`."
            )
            confirmed = st.checkbox(
                "Yes, this relationship direction is correct",
                help="For example, api_gateway → logging means api_gateway depends on logging.",
            )

            back_column, next_column = st.columns([1, 2])
            if back_column.button("Back", width="stretch"):
                st.session_state["wizard_step"] = 1
                st.rerun()
            if next_column.button(
                "Review graph",
                type="primary",
                width="stretch",
                disabled=not confirmed,
            ):
                st.session_state["wizard_source"] = source_column
                st.session_state["wizard_target"] = target_column
                st.session_state["wizard_step"] = 3
                st.rerun()

    else:
        frame = pd.read_csv(io.BytesIO(st.session_state["wizard_bytes"]))
        source_column = st.session_state["wizard_source"]
        target_column = st.session_state["wizard_target"]

        try:
            normalized = load_edge_csv(
                file_path=io.BytesIO(st.session_state["wizard_bytes"]),
                source_column=source_column,
                target_column=target_column,
            )
        except Exception as error:
            st.error(f"Could not prepare this graph: {error}")
            return

        st.markdown("### Review before analysis")
        metric_columns = st.columns(4)
        metric_columns[0].metric("Components", f"{normalized.number_of_nodes:,}")
        metric_columns[1].metric("Dependencies", f"{normalized.valid_rows:,}")
        metric_columns[2].metric("Missing rows", f"{normalized.missing_rows:,}")
        metric_columns[3].metric("Duplicates", f"{normalized.duplicate_edges:,}")

        st.caption(
            f"Meaning: `{source_column} → {target_column}` · File: "
            f"`{st.session_state['wizard_name']}`"
        )

        too_large = normalized.number_of_nodes > MAX_ANALYSIS_NODES
        if too_large:
            st.error(
                f"This version supports up to {MAX_ANALYSIS_NODES:,} components for "
                "dependency intelligence. Your graph has "
                f"{normalized.number_of_nodes:,}."
            )

        back_column, run_column = st.columns([1, 2])
        if back_column.button("Back", width="stretch"):
            st.session_state["wizard_step"] = 2
            st.rerun()

        if run_column.button(
            "Analyze dependency architecture",
            type="primary",
            width="stretch",
            disabled=too_large,
        ):
            progress = st.progress(10, text="Validating dependency data...")
            try:
                progress.progress(35, text="Detecting cycles and graph structure...")
                report = generate_dependency_intelligence_report(
                    dataframe=frame,
                    source_column=source_column,
                    target_column=target_column,
                    top_n=10,
                    pagerank_alpha=0.85,
                    exact_betweenness_threshold=2_000,
                    approximation_samples=500,
                    seed=42,
                )
                progress.progress(85, text="Preparing explainable findings...")

                dataset_hash = hashlib.sha256(
                    st.session_state["wizard_bytes"]
                ).hexdigest()
                report["dataset"] = {
                    "name": st.session_state["wizard_name"],
                    "source_column": source_column,
                    "target_column": target_column,
                    "sha256": dataset_hash,
                }
                report["environment"] = collect_environment_metadata()

                st.session_state["dependency_report"] = report
                clean_edge_frame = (
                    frame[[source_column, target_column]]
                    .dropna()
                    .drop_duplicates()
                    .astype(str)
                )
                st.session_state["dataset_info"] = {
                    "name": st.session_state["wizard_name"],
                    "source_column": source_column,
                    "target_column": target_column,
                    "nodes": normalized.number_of_nodes,
                    "edges": normalized.valid_rows,
                    "missing": normalized.missing_rows,
                    "duplicates": normalized.duplicate_edges,
                    "self_loops": normalized.self_loops,
                    "preview": frame.head(20).to_dict(orient="records"),
                    "graph_edges": clean_edge_frame.values.tolist(),
                }
                progress.progress(100, text="Analysis complete")
                st.session_state["show_setup"] = False
                st.rerun()
            except nx.PowerIterationFailedConvergence:
                st.error(
                    "PageRank did not converge. Review the graph's cycles and try again."
                )
            except Exception as error:
                st.error(f"Dependency analysis failed: {error}")


st.markdown(
    """
<div class="hero">
    <div class="eyebrow">Software dependency intelligence</div>
    <h1>GraphBench</h1>
    <p>
        Upload a software dependency graph and discover critical dependencies,
        architectural bottlenecks, circular dependencies, and structural cores—
        with plain-language evidence and recommended next actions.
    </p>
</div>
""",
    unsafe_allow_html=True,
)


report = st.session_state.get("dependency_report")
dataset_info = st.session_state.get("dataset_info")


if report is None:
    st.markdown(
        """
<div class="empty-state">
    <div class="eyebrow">Three guided steps</div>
    <h2>Understand the hidden risk in your dependency graph</h2>
    <p>
        Start with our sample or upload a two-column CSV. GraphBench will guide you
        through relationship direction, validation, analysis, and interpretation.
    </p>
</div>
""",
        unsafe_allow_html=True,
    )
    button_columns = st.columns([1, 1.2, 1])
    if button_columns[1].button(
        "Start dependency analysis",
        type="primary",
        width="stretch",
    ):
        reset_wizard()
        st.session_state["show_setup"] = True
        st.rerun()

    st.markdown("### What you will receive")
    benefit_columns = st.columns(4)
    benefits = [
        (
            "Critical dependencies",
            "Find components that receive importance from many dependency paths.",
        ),
        (
            "Path bottlenecks",
            "Identify connectors where change or failure may affect multiple areas.",
        ),
        (
            "Dependency cycles",
            "Expose circular relationships that complicate builds and deployments.",
        ),
        (
            "Structural core",
            "Locate the tightly connected layer that deserves careful change control.",
        ),
    ]
    for column, (title, description) in zip(benefit_columns, benefits):
        with column:
            st.markdown(
                f'<div class="summary-card"><div class="label">Analysis output</div><h3>{title}</h3><p>{description}</p></div>',
                unsafe_allow_html=True,
            )

else:
    summary = summarize_report(report)
    cycle = cycle_text(summary["cycle"])
    candidates = summary["candidates"]

    title_column, action_column = st.columns([3, 1])
    with title_column:
        st.subheader("Architecture review")
        st.caption(
            f"{dataset_info['name']} · {dataset_info['nodes']:,} components · "
            f"{dataset_info['edges']:,} dependencies · "
            f"{dataset_info['source_column']} → {dataset_info['target_column']}"
        )
    with action_column:
        if st.button("Analyze another graph", width="stretch"):
            reset_wizard()
            st.session_state["show_setup"] = True
            st.rerun()

    if cycle:
        st.warning(
            f"**Review recommended:** circular dependency detected: {cycle}. "
            "Cycles can complicate build order, deployment order, and failure analysis."
        )
    else:
        st.success("No circular dependency was detected.")

    graph_tab, impact_tab, findings_tab, actions_tab, evidence_tab = st.tabs(
        [
            "Graph explorer",
            "Impact simulator",
            "Key findings",
            "Recommended actions",
            "Evidence & method",
        ]
    )

    with graph_tab:
        render_graph_explorer(dataset_info)

    with impact_tab:
        render_impact_simulator(dataset_info)

    with findings_tab:
        finding_columns = st.columns(3)
        with finding_columns[0]:
            st.markdown(
                f'<div class="summary-card"><div class="label">Critical dependency</div><h3>{summary["highest_component"]}</h3><p>PageRank {summary["highest_score"]:.6f}. Review reliability, ownership, and fallback coverage.</p></div>',
                unsafe_allow_html=True,
            )
        with finding_columns[1]:
            st.markdown(
                f'<div class="summary-card"><div class="label">Path bottleneck</div><h3>{summary["bottleneck_component"]}</h3><p>Betweenness {summary["bottleneck_score"]:.6f}. It connects important dependency paths.</p></div>',
                unsafe_allow_html=True,
            )
        with finding_columns[2]:
            st.markdown(
                f'<div class="summary-card"><div class="label">Structural core</div><h3>{summary["maximum_core"]}-core</h3><p>{summary["deepest_size"]} components belong to the deepest connected layer.</p></div>',
                unsafe_allow_html=True,
            )

        st.markdown("### Components to review first")
        st.caption(
            "A higher signal count means several independent graph measures point to the same component. It does not prove a defect."
        )

        if not candidates:
            st.info("The report did not return ranked review candidates.")
        else:
            normalized_candidates = []
            for index, candidate in enumerate(candidates, start=1):
                reasons = candidate_value(candidate, "reasons", "signals", default=[])
                cautions = candidate_value(
                    candidate, "cautions", "warnings", default=[]
                )
                normalized_candidates.append(
                    {
                        "Rank": int(candidate_value(candidate, "rank", default=index)),
                        "Component": str(
                            candidate_value(
                                candidate, "component", "name", default="Unknown"
                            )
                        ),
                        "Signals": int(
                            candidate_value(
                                candidate,
                                "signal_count",
                                "signals_count",
                                default=len(reasons),
                            )
                        ),
                        "PageRank": number(
                            candidate_value(
                                candidate, "pagerank", "pagerank_score", default=0
                            )
                        ),
                        "Betweenness": number(
                            candidate_value(
                                candidate, "betweenness", "betweenness_score", default=0
                            )
                        ),
                        "Core": int(
                            number(
                                candidate_value(
                                    candidate, "core_number", "core", default=0
                                )
                            )
                        ),
                        "In cycle": bool(
                            candidate_value(
                                candidate, "in_cycle", "cycle_member", default=False
                            )
                        ),
                        "Reasons": reasons,
                        "Cautions": cautions,
                    }
                )

            candidate_frame = pd.DataFrame(normalized_candidates)
            chart = (
                alt.Chart(candidate_frame.head(10))
                .mark_bar(cornerRadiusEnd=5)
                .encode(
                    x=alt.X("Signals:Q", title="Independent structural signals"),
                    y=alt.Y("Component:N", title=None, sort="-x"),
                    color=alt.Color(
                        "Signals:Q",
                        scale=alt.Scale(range=["#60A5FA", "#F59E0B"]),
                        legend=None,
                    ),
                    tooltip=["Component:N", "Signals:Q", "PageRank:Q", "Betweenness:Q"],
                )
                .properties(height=300)
            )
            st.altair_chart(chart, width="stretch")

            selected_name = st.selectbox(
                "Explain a review candidate",
                candidate_frame["Component"].tolist(),
            )
            selected = next(
                item
                for item in normalized_candidates
                if item["Component"] == selected_name
            )
            explanation_columns = st.columns(2)
            with explanation_columns[0]:
                st.markdown("**Why GraphBench flagged it**")
                if selected["Reasons"]:
                    for reason in selected["Reasons"]:
                        st.write(f"- {reason}")
                else:
                    st.write(
                        "Multiple structural measurements place it among the top review candidates."
                    )
            with explanation_columns[1]:
                st.markdown("**Interpretation caution**")
                if selected["Cautions"]:
                    for caution in selected["Cautions"]:
                        st.write(f"- {caution}")
                else:
                    st.write(
                        "This is a review priority, not proof that the component is defective."
                    )

            st.dataframe(
                candidate_frame.drop(columns=["Reasons", "Cautions"]),
                width="stretch",
                hide_index=True,
            )

    with actions_tab:
        st.markdown("### Turn findings into engineering work")
        action_columns = st.columns(3)
        action_items = [
            (
                "1. Protect the critical dependency",
                f"Review ownership, monitoring, capacity, tests, and fallback behavior for {summary['highest_component']}.",
            ),
            (
                "2. Test the path bottleneck",
                f"Run a failure or change-impact exercise around {summary['bottleneck_component']} and document affected services.",
            ),
            (
                "3. Control dependency drift",
                (
                    "Break or explicitly document the detected cycle. Add a CI check to prevent new circular dependencies."
                    if cycle
                    else "Add cycle detection to CI so future circular dependencies are caught before merge."
                ),
            ),
        ]
        for column, (title, description) in zip(action_columns, action_items):
            with column:
                st.markdown(
                    f'<div class="action-card"><strong>{title}</strong><span>{description}</span></div>',
                    unsafe_allow_html=True,
                )

        st.info(
            "Suggested workflow: validate these findings with component owners, create tickets for confirmed risks, and rerun GraphBench after architecture changes."
        )

    with evidence_tab:
        data_tab, method_tab, download_tab = st.tabs(
            ["Input data", "Method", "Downloads"]
        )

        with data_tab:
            quality_columns = st.columns(5)
            quality_columns[0].metric("Components", f"{dataset_info['nodes']:,}")
            quality_columns[1].metric("Dependencies", f"{dataset_info['edges']:,}")
            quality_columns[2].metric("Missing", f"{dataset_info['missing']:,}")
            quality_columns[3].metric("Duplicates", f"{dataset_info['duplicates']:,}")
            quality_columns[4].metric(
                "Self-dependencies", f"{dataset_info['self_loops']:,}"
            )
            st.dataframe(
                pd.DataFrame(dataset_info["preview"]), width="stretch", hide_index=True
            )

        with method_tab:
            st.markdown("""
- **PageRank** highlights dependencies that receive importance from other important components.
- **Betweenness centrality** highlights components that sit on many dependency paths.
- **K-core** finds deeply embedded structural layers after treating the graph as undirected.
- **Cycle detection** identifies circular dependency chains.

These measurements prioritize human review. They do not predict outages or prove that a component is defective.
""")
            with st.expander("Exact recorded methodology"):
                st.json(report.get("methodology", {}))
            for warning in report.get("warnings", []):
                st.warning(warning)

        with download_tab:
            download_columns = st.columns(2)
            download_columns[0].download_button(
                "Download full report (JSON)",
                json.dumps(report, indent=2),
                "dependency_intelligence_report.json",
                "application/json",
                width="stretch",
            )
            if candidates:
                csv_frame = pd.DataFrame(normalized_candidates).drop(
                    columns=["Reasons", "Cautions"]
                )
                download_columns[1].download_button(
                    "Download review list (CSV)",
                    csv_frame.to_csv(index=False),
                    "dependency_review_candidates.csv",
                    "text/csv",
                    width="stretch",
                )


if st.session_state.get("show_setup"):
    setup_dialog()
