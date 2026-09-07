import hashlib
import io
import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from backends.ladybug_backend import LadybugBackend
from backends.networkx_backend import NetworkXBackend
from benchmarks.runner import benchmark_backend
from ingestion.csv_loader import load_edge_csv

st.set_page_config(
    page_title="GraphBench",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)


SAMPLE_DATASETS = {
    "Social network": {
        "path": Path("data/sample_social_network.csv"),
        "source": "follower",
        "target": "followed",
        "description": (
            "A directed social graph containing users and " "follow relationships."
        ),
    },
    "Web links": {
        "path": Path("data/sample_web_links.csv"),
        "source": "source_page",
        "target": "target_page",
        "description": ("A directed graph representing links between web pages."),
    },
    "Package dependencies": {
        "path": Path("data/sample_dependencies.csv"),
        "source": "package",
        "target": "depends_on",
        "description": (
            "A dependency graph showing which packages depend " "on other packages."
        ),
    },
}


st.markdown(
    """
    <style>
        .stApp {
            background:
                radial-gradient(
                    circle at 10% 0%,
                    rgba(37, 99, 235, 0.10),
                    transparent 28rem
                ),
                radial-gradient(
                    circle at 95% 10%,
                    rgba(245, 158, 11, 0.08),
                    transparent 25rem
                );
        }

        .block-container {
            max-width: 1280px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        .product-header {
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 18px;
            padding: 1.6rem 1.8rem;
            margin-bottom: 1.5rem;
            background: rgba(15, 23, 42, 0.36);
        }

        .product-kicker {
            color: #60a5fa;
            font-size: 0.85rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
        }

        .product-title {
            font-size: 2.4rem;
            font-weight: 750;
            letter-spacing: -0.04em;
            line-height: 1.05;
            margin: 0;
        }

        .product-description {
            color: #cbd5e1;
            font-size: 1rem;
            line-height: 1.65;
            margin-bottom: 0.9rem;
            margin-top: 0.8rem;
            max-width: 850px;
        }

        .technology-list {
            color: #94a3b8;
            font-family: monospace;
            font-size: 0.85rem;
            margin: 0;
        }

        .section-label {
            color: #94a3b8;
            font-size: 0.82rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            margin-bottom: 0.3rem;
            text-transform: uppercase;
        }

        .engine-card {
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 14px;
            min-height: 135px;
            padding: 1.1rem;
            background: rgba(15, 23, 42, 0.30);
        }

        .engine-card h4 {
            margin-bottom: 0.35rem;
            margin-top: 0;
        }

        .engine-card p {
            color: #94a3b8;
            font-size: 0.9rem;
            line-height: 1.45;
            margin-bottom: 0;
        }

        .status-available {
            color: #4ade80;
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
        }

        .status-planned {
            color: #fbbf24;
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
        }

        div[data-testid="stMetric"] {
            border: 1px solid rgba(148, 163, 184, 0.20);
            border-radius: 12px;
            padding: 1rem;
            background: rgba(15, 23, 42, 0.28);
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.55rem;
        }

        div.stButton > button {
            min-height: 3rem;
            border-radius: 10px;
            font-weight: 700;
        }

        div[data-testid="stDownloadButton"] > button {
            min-height: 2.8rem;
            border-radius: 10px;
            font-weight: 650;
        }

        div[data-testid="stProgress"] {
            margin-top: 0.8rem;
            margin-bottom: 0.8rem;
        }

        hr {
            border-color: rgba(148, 163, 184, 0.15);
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def determine_comparison(
    networkx_time: float,
    ladybug_time: float,
) -> dict:
    if networkx_time <= 0 or ladybug_time <= 0:
        return {
            "winner": "Inconclusive",
            "speedup": 0,
        }

    if networkx_time < ladybug_time:
        return {
            "winner": "NetworkX",
            "speedup": ladybug_time / networkx_time,
        }

    return {
        "winner": "LadybugDB",
        "speedup": networkx_time / ladybug_time,
    }


def run_benchmark(
    normalized_graph,
    configuration: dict,
    progress_bar=None,
    status_container=None,
) -> dict:
    requested_query_count = configuration["query_count"]

    query_count = min(
        requested_query_count,
        normalized_graph.number_of_nodes,
    )

    query_nodes = list(range(query_count))

    networkx_backend = NetworkXBackend()
    ladybug_backend = LadybugBackend()

    try:
        if status_container is not None:
            status_container.info("Preparing the NetworkX benchmark...")

        if progress_bar is not None:
            progress_bar.progress(
                10,
                text="Preparing NetworkX",
            )

        networkx_results = benchmark_backend(
            backend=networkx_backend,
            number_of_nodes=(normalized_graph.number_of_nodes),
            edges=normalized_graph.edges,
            query_nodes=query_nodes,
            build_repetitions=(configuration["build_repetitions"]),
            build_warmup_runs=(configuration["build_warmups"]),
            query_repetitions=(configuration["query_repetitions"]),
            query_warmup_runs=(configuration["query_warmups"]),
        )

        if status_container is not None:
            status_container.info("NetworkX finished. Running LadybugDB...")

        if progress_bar is not None:
            progress_bar.progress(
                45,
                text="NetworkX complete",
            )

        ladybug_results = benchmark_backend(
            backend=ladybug_backend,
            number_of_nodes=(normalized_graph.number_of_nodes),
            edges=normalized_graph.edges,
            query_nodes=query_nodes,
            build_repetitions=(configuration["build_repetitions"]),
            build_warmup_runs=(configuration["build_warmups"]),
            query_repetitions=(configuration["query_repetitions"]),
            query_warmup_runs=(configuration["query_warmups"]),
        )

        if status_container is not None:
            status_container.info("Validating equivalent graph results...")

        if progress_bar is not None:
            progress_bar.progress(
                85,
                text="Validating correctness",
            )

        neighbor_results_match = (
            networkx_results["neighbors"]["result"]
            == ladybug_results["neighbors"]["result"]
        )

        node_counts_match = (
            networkx_results["number_of_nodes"]
            == ladybug_results["number_of_nodes"]
            == normalized_graph.number_of_nodes
        )

        edge_counts_match = (
            networkx_results["number_of_edges"]
            == ladybug_results["number_of_edges"]
            == len(normalized_graph.edges)
        )

        correctness = neighbor_results_match and node_counts_match and edge_counts_match

        networkx_build = networkx_results["build"]["median_ms"]

        ladybug_build = ladybug_results["build"]["median_ms"]

        networkx_query = networkx_results["neighbors"]["median_ms"]

        ladybug_query = ladybug_results["neighbors"]["median_ms"]

        if progress_bar is not None:
            progress_bar.progress(
                100,
                text="Benchmark complete",
            )

        return {
            "graph_health": {
                "nodes": normalized_graph.number_of_nodes,
                "edges": normalized_graph.valid_rows,
                "missing_rows": (normalized_graph.missing_rows),
                "duplicate_edges": (normalized_graph.duplicate_edges),
                "self_loops": (normalized_graph.self_loops),
            },
            "benchmark_configuration": {
                **configuration,
                "actual_query_count": query_count,
            },
            "correctness": {
                "passed": correctness,
                "node_counts_match": node_counts_match,
                "edge_counts_match": edge_counts_match,
                "neighbor_results_match": (neighbor_results_match),
            },
            "networkx": {
                "build_median_ms": networkx_build,
                "build_p95_ms": (networkx_results["build"]["p95_ms"]),
                "query_median_ms": networkx_query,
                "query_p95_ms": (networkx_results["neighbors"]["p95_ms"]),
                "batch_throughput_per_second": (
                    networkx_results["neighbors"]["throughput_per_second"]
                ),
            },
            "ladybug": {
                "build_median_ms": ladybug_build,
                "build_p95_ms": (ladybug_results["build"]["p95_ms"]),
                "query_median_ms": ladybug_query,
                "query_p95_ms": (ladybug_results["neighbors"]["p95_ms"]),
                "batch_throughput_per_second": (
                    ladybug_results["neighbors"]["throughput_per_second"]
                ),
            },
            "build_comparison": determine_comparison(
                networkx_build,
                ladybug_build,
            ),
            "query_comparison": determine_comparison(
                networkx_query,
                ladybug_query,
            ),
        }

    finally:
        networkx_backend.close()
        ladybug_backend.close()


def create_latency_chart(report: dict) -> None:
    chart_dataframe = pd.DataFrame(
        [
            {
                "Operation": "Graph construction",
                "Backend": "NetworkX",
                "Latency": (report["networkx"]["build_median_ms"]),
            },
            {
                "Operation": "Graph construction",
                "Backend": "LadybugDB",
                "Latency": (report["ladybug"]["build_median_ms"]),
            },
            {
                "Operation": "Neighbor batch",
                "Backend": "NetworkX",
                "Latency": (report["networkx"]["query_median_ms"]),
            },
            {
                "Operation": "Neighbor batch",
                "Backend": "LadybugDB",
                "Latency": (report["ladybug"]["query_median_ms"]),
            },
        ]
    )

    scale_option = st.radio(
        "Chart scale",
        options=[
            "Logarithmic",
            "Linear",
        ],
        horizontal=True,
        key="latency_scale",
    )

    if scale_option == "Logarithmic":
        latency_scale = alt.Scale(
            type="log",
            nice=True,
        )
    else:
        latency_scale = alt.Scale(
            type="linear",
            zero=True,
            nice=True,
        )

    base_chart = alt.Chart(chart_dataframe).encode(
        x=alt.X(
            "Latency:Q",
            title="Median latency (milliseconds)",
            scale=latency_scale,
        ),
        y=alt.Y(
            "Operation:N",
            title=None,
            sort=[
                "Graph construction",
                "Neighbor batch",
            ],
        ),
        yOffset=alt.YOffset(
            "Backend:N",
        ),
        color=alt.Color(
            "Backend:N",
            scale=alt.Scale(
                domain=[
                    "NetworkX",
                    "LadybugDB",
                ],
                range=[
                    "#3B82F6",
                    "#F59E0B",
                ],
            ),
            legend=alt.Legend(
                title=None,
                orient="top",
            ),
        ),
        tooltip=[
            alt.Tooltip(
                "Operation:N",
                title="Operation",
            ),
            alt.Tooltip(
                "Backend:N",
                title="Backend",
            ),
            alt.Tooltip(
                "Latency:Q",
                title="Median latency",
                format=".6f",
            ),
        ],
    )

    points = base_chart.mark_circle(
        size=260,
        opacity=1,
    )

    labels = base_chart.mark_text(
        align="left",
        baseline="middle",
        dx=10,
        fontSize=13,
    ).encode(
        text=alt.Text(
            "Latency:Q",
            format=".6f",
        ),
    )

    chart = (points + labels).properties(
        height=280,
    )

    st.altair_chart(
        chart,
        use_container_width=True,
    )

    if scale_option == "Logarithmic":
        st.caption(
            "Logarithmic scale: horizontal distance represents "
            "multiplicative latency differences."
        )
    else:
        st.caption(
            "Linear scale: horizontal distance represents "
            "absolute latency differences."
        )


def create_throughput_chart(report: dict) -> None:
    throughput_dataframe = pd.DataFrame(
        [
            {
                "Backend": "NetworkX",
                "Batches per second": (
                    report["networkx"]["batch_throughput_per_second"]
                ),
            },
            {
                "Backend": "LadybugDB",
                "Batches per second": (
                    report["ladybug"]["batch_throughput_per_second"]
                ),
            },
        ]
    )

    base_chart = alt.Chart(throughput_dataframe).encode(
        x=alt.X(
            "Batches per second:Q",
            title="Estimated batches per second",
        ),
        y=alt.Y(
            "Backend:N",
            title=None,
            sort=[
                "NetworkX",
                "LadybugDB",
            ],
        ),
        color=alt.Color(
            "Backend:N",
            scale=alt.Scale(
                domain=[
                    "NetworkX",
                    "LadybugDB",
                ],
                range=[
                    "#3B82F6",
                    "#F59E0B",
                ],
            ),
            legend=None,
        ),
        tooltip=[
            alt.Tooltip(
                "Backend:N",
                title="Backend",
            ),
            alt.Tooltip(
                "Batches per second:Q",
                title="Batches/second",
                format=",.2f",
            ),
        ],
    )

    bars = base_chart.mark_bar(
        cornerRadiusEnd=5,
        height=32,
    )

    labels = base_chart.mark_text(
        align="left",
        baseline="middle",
        dx=8,
        fontSize=13,
    ).encode(
        text=alt.Text(
            "Batches per second:Q",
            format=",.2f",
        ),
    )

    chart = (bars + labels).properties(
        height=180,
    )

    st.altair_chart(
        chart,
        use_container_width=True,
    )


def show_benchmark_insight(report: dict) -> None:
    graph_health = report["graph_health"]
    query_comparison = report["query_comparison"]
    build_comparison = report["build_comparison"]

    if not report["correctness"]["passed"]:
        st.error(
            "The backends returned different results. No "
            "performance recommendation can be made."
        )
        return

    if graph_health["nodes"] < 100:
        st.warning(
            "This graph is very small. Fixed library and query "
            "overhead dominates operations at this scale, so "
            "large speedup ratios should be interpreted cautiously."
        )

    st.markdown(f"""
        **Measured result**

        - **{build_comparison["winner"]}** completed graph
          construction approximately
          **{build_comparison["speedup"]:.2f}× faster**.
        - **{query_comparison["winner"]}** completed the neighbor
          workload approximately
          **{query_comparison["speedup"]:.2f}× faster**.
        """)

    if (
        build_comparison["winner"] == "NetworkX"
        and query_comparison["winner"] == "NetworkX"
    ):
        st.info(
            "NetworkX is the stronger option for this measured "
            "in-memory workload. LadybugDB may still be appropriate "
            "when persistence, Cypher querying, transactions or "
            "larger analytical workloads are required."
        )

    elif (
        build_comparison["winner"] == "LadybugDB"
        and query_comparison["winner"] == "LadybugDB"
    ):
        st.info(
            "LadybugDB performed better for both measured workloads " "on this dataset."
        )

    else:
        st.info(
            "The engines lead different workload categories. "
            "The preferred backend depends on whether graph loading "
            "or repeated querying is more important."
        )

    st.caption(
        "This recommendation applies only to the selected dataset, "
        "workload, benchmark settings, installed versions and machine."
    )


st.markdown(
    """
    <div class="product-header">
    <h1 class="product-title">GraphBench</h1>
    <p class="product-description">
        GraphBench is an interactive graph-engine evaluation platform that
        runs equivalent workloads across NetworkX and LadybugDB. Use a
        built-in dataset or upload an edge-list CSV to compare correctness,
        construction latency, query latency, and throughput under
        reproducible benchmark settings.
    </p>
    <p class="technology-list">
        Python · NetworkX · LadybugDB · Cypher · Pandas · Streamlit · Altair
    </p>
    </div>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    '<div class="section-label">Dataset</div>',
    unsafe_allow_html=True,
)

st.header("Choose graph data")


data_source = st.radio(
    "How would you like to provide the graph?",
    options=[
        "Try a sample dataset",
        "Upload your own CSV",
    ],
    horizontal=True,
    label_visibility="collapsed",
)


dataset_bytes = None
dataset_name = None
source_column = None
target_column = None


if data_source == "Try a sample dataset":
    selected_sample = st.selectbox(
        "Sample dataset",
        options=list(SAMPLE_DATASETS.keys()),
    )

    sample_configuration = SAMPLE_DATASETS[selected_sample]

    sample_path = sample_configuration["path"]

    st.caption(sample_configuration["description"])

    if not sample_path.exists():
        st.error(
            f"Sample file not found: {sample_path}. "
            "Run `python create_sample_datasets.py` first."
        )
        st.stop()

    dataset_bytes = sample_path.read_bytes()
    dataset_name = sample_path.name

    source_column = sample_configuration["source"]
    target_column = sample_configuration["target"]

    st.download_button(
        label="Download this sample CSV",
        data=dataset_bytes,
        file_name=dataset_name,
        mime="text/csv",
    )

else:
    uploaded_file = st.file_uploader(
        "Upload an edge-list CSV",
        type=["csv"],
        help=(
            "The file must contain at least one source-node "
            "column and one target-node column."
        ),
    )

    if uploaded_file is None:
        st.info("Upload a CSV file to configure the benchmark.")
        st.stop()

    dataset_bytes = uploaded_file.getvalue()
    dataset_name = uploaded_file.name


try:
    preview_dataframe = pd.read_csv(io.BytesIO(dataset_bytes))
except Exception as error:
    st.error(f"Could not read the CSV: {error}")
    st.stop()


if len(preview_dataframe.columns) < 2:
    st.error("The CSV must contain at least two columns.")
    st.stop()


if preview_dataframe.empty:
    st.error("The CSV does not contain any data rows.")
    st.stop()


columns = list(preview_dataframe.columns)


if data_source == "Upload your own CSV":
    mapping_column_one, mapping_column_two = st.columns(2)

    with mapping_column_one:
        source_column = st.selectbox(
            "Starting-node column",
            options=columns,
            index=0,
        )

    with mapping_column_two:
        target_column = st.selectbox(
            "Connected-node column",
            options=columns,
            index=1 if len(columns) > 1 else 0,
        )


if source_column == target_column:
    st.error("The source and target columns must be different.")
    st.stop()


with st.expander("Preview input data"):
    st.dataframe(
        preview_dataframe.head(20),
        use_container_width=True,
    )

    st.caption(f"Showing up to 20 of " f"{len(preview_dataframe):,} input rows.")


try:
    normalized_graph = load_edge_csv(
        file_path=io.BytesIO(dataset_bytes),
        source_column=source_column,
        target_column=target_column,
    )
except Exception as error:
    st.error(f"Could not prepare the graph: {error}")
    st.stop()


if normalized_graph.number_of_nodes == 0:
    st.error("No valid graph data remained after validation.")
    st.stop()


st.markdown("---")

st.markdown(
    '<div class="section-label">Validation</div>',
    unsafe_allow_html=True,
)

st.header("Graph health")


health_columns = st.columns(5)

health_columns[0].metric(
    "Unique nodes",
    f"{normalized_graph.number_of_nodes:,}",
)

health_columns[1].metric(
    "Unique edges",
    f"{normalized_graph.valid_rows:,}",
)

health_columns[2].metric(
    "Missing rows",
    f"{normalized_graph.missing_rows:,}",
)

health_columns[3].metric(
    "Duplicates removed",
    f"{normalized_graph.duplicate_edges:,}",
)

health_columns[4].metric(
    "Self-loops",
    f"{normalized_graph.self_loops:,}",
)


st.markdown("---")

st.markdown(
    '<div class="section-label">Configuration</div>',
    unsafe_allow_html=True,
)

st.header("Configure benchmark")


benchmark_mode = st.radio(
    "Benchmark mode",
    options=[
        "Quick",
        "Advanced",
    ],
    horizontal=True,
)


if benchmark_mode == "Quick":
    configuration = {
        "mode": "Quick",
        "query_count": min(
            100,
            normalized_graph.number_of_nodes,
        ),
        "build_repetitions": 5,
        "build_warmups": 1,
        "query_repetitions": 20,
        "query_warmups": 3,
    }

    st.caption(
        "Quick mode uses five graph-build repetitions, "
        "20 query repetitions and automatic query sampling."
    )

else:
    configuration_column_one, configuration_column_two = st.columns(2)

    with configuration_column_one:
        query_count = st.number_input(
            "Nodes queried per batch",
            min_value=1,
            max_value=(normalized_graph.number_of_nodes),
            value=min(
                100,
                normalized_graph.number_of_nodes,
            ),
            step=1,
        )

        build_repetitions = st.number_input(
            "Graph-build repetitions",
            min_value=1,
            max_value=50,
            value=5,
            step=1,
        )

        build_warmups = st.number_input(
            "Graph-build warm-ups",
            min_value=0,
            max_value=10,
            value=1,
            step=1,
        )

    with configuration_column_two:
        query_repetitions = st.number_input(
            "Query repetitions",
            min_value=1,
            max_value=1_000,
            value=50,
            step=10,
        )

        query_warmups = st.number_input(
            "Query warm-ups",
            min_value=0,
            max_value=100,
            value=5,
            step=1,
        )

    configuration = {
        "mode": "Advanced",
        "query_count": int(query_count),
        "build_repetitions": int(build_repetitions),
        "build_warmups": int(build_warmups),
        "query_repetitions": int(query_repetitions),
        "query_warmups": int(query_warmups),
    }


dataset_hash = hashlib.sha256(dataset_bytes).hexdigest()


benchmark_key = (
    dataset_hash,
    source_column,
    target_column,
    json.dumps(
        configuration,
        sort_keys=True,
    ),
)


if st.session_state.get("benchmark_key") != benchmark_key:
    st.session_state.pop(
        "benchmark_report",
        None,
    )

    st.session_state["benchmark_key"] = benchmark_key


if st.button(
    "Run benchmark",
    type="primary",
    use_container_width=True,
):
    progress_container = st.container()

    with progress_container:
        status_container = st.empty()

        progress_bar = st.progress(
            0,
            text="Starting benchmark...",
        )

        try:
            report = run_benchmark(
                normalized_graph=normalized_graph,
                configuration=configuration,
                progress_bar=progress_bar,
                status_container=status_container,
            )

            report["dataset"] = {
                "name": dataset_name,
                "source_column": source_column,
                "target_column": target_column,
            }

            st.session_state["benchmark_report"] = report

            status_container.success("Benchmark completed successfully.")

        except Exception as error:
            progress_bar.empty()

            status_container.error(f"The benchmark could not be completed: {error}")

            st.stop()


if "benchmark_report" not in st.session_state:
    st.stop()


report = st.session_state["benchmark_report"]


st.markdown("---")

st.markdown(
    '<div class="section-label">Results</div>',
    unsafe_allow_html=True,
)

st.header("Benchmark results")


if report["correctness"]["passed"]:
    st.success(
        "Correctness passed. Both backends loaded equivalent "
        "graphs and returned matching neighbor results."
    )
else:
    st.error("Correctness failed. These performance results " "should not be used.")


result_tabs = st.tabs(
    [
        "Overview",
        "Latency",
        "Throughput",
        "Insights",
        "Raw report",
    ]
)


with result_tabs[0]:
    result_column_one, result_column_two = st.columns(2)

    with result_column_one:
        st.subheader("Graph construction")

        st.metric(
            "NetworkX median",
            (f"{report['networkx']['build_median_ms']:.6f} ms"),
        )

        st.metric(
            "LadybugDB median",
            (f"{report['ladybug']['build_median_ms']:.6f} ms"),
        )

        build_comparison = report["build_comparison"]

        st.write(
            f"**{build_comparison['winner']}** was "
            f"**{build_comparison['speedup']:.2f}× faster** "
            f"for graph construction."
        )

    with result_column_two:
        st.subheader("Neighbor workload")

        st.metric(
            "NetworkX median",
            (f"{report['networkx']['query_median_ms']:.6f} ms"),
        )

        st.metric(
            "LadybugDB median",
            (f"{report['ladybug']['query_median_ms']:.6f} ms"),
        )

        query_comparison = report["query_comparison"]

        st.write(
            f"**{query_comparison['winner']}** was "
            f"**{query_comparison['speedup']:.2f}× faster** "
            f"for the neighbor workload."
        )


with result_tabs[1]:
    st.subheader("Median latency")

    create_latency_chart(report)

    latency_table = pd.DataFrame(
        [
            {
                "Backend": "NetworkX",
                "Build median (ms)": (report["networkx"]["build_median_ms"]),
                "Build P95 (ms)": (report["networkx"]["build_p95_ms"]),
                "Query median (ms)": (report["networkx"]["query_median_ms"]),
                "Query P95 (ms)": (report["networkx"]["query_p95_ms"]),
            },
            {
                "Backend": "LadybugDB",
                "Build median (ms)": (report["ladybug"]["build_median_ms"]),
                "Build P95 (ms)": (report["ladybug"]["build_p95_ms"]),
                "Query median (ms)": (report["ladybug"]["query_median_ms"]),
                "Query P95 (ms)": (report["ladybug"]["query_p95_ms"]),
            },
        ]
    )

    st.dataframe(
        latency_table,
        use_container_width=True,
        hide_index=True,
    )


with result_tabs[2]:
    st.subheader("Estimated batch throughput")

    create_throughput_chart(report)

    st.caption(
        "Throughput is calculated from average batch latency. "
        "It is not a concurrent multi-user load test."
    )


with result_tabs[3]:
    show_benchmark_insight(report)


with result_tabs[4]:
    st.json(report)


st.subheader("Export")

report_json = json.dumps(
    report,
    indent=2,
)


st.download_button(
    label="Download benchmark report",
    data=report_json,
    file_name="graphbench_report.json",
    mime="application/json",
    use_container_width=True,
)


st.markdown("---")

st.markdown(
    '<div class="section-label">Platform</div>',
    unsafe_allow_html=True,
)

st.header("Graph engines")


available_one, available_two = st.columns(2)


with available_one:
    st.markdown(
        """
        <div class="engine-card">
            <div class="status-available">Available</div>
            <h4>NetworkX</h4>
            <p>
                Python-based, in-memory graph construction,
                traversal and analytics.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


with available_two:
    st.markdown(
        """
        <div class="engine-card">
            <div class="status-available">Available</div>
            <h4>LadybugDB</h4>
            <p>
                Embedded property-graph database with Cypher,
                columnar storage and analytical query execution.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.subheader("Planned integrations")


planned_one, planned_two, planned_three = st.columns(3)


with planned_one:
    st.markdown(
        """
        <div class="engine-card">
            <div class="status-planned">In development</div>
            <h4>Neo4j</h4>
            <p>
                Server-based property-graph database and
                Cypher query engine.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


with planned_two:
    st.markdown(
        """
        <div class="engine-card">
            <div class="status-planned">In development</div>
            <h4>igraph</h4>
            <p>
                Compiled, high-performance graph-analysis
                library with Python bindings.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


with planned_three:
    st.markdown(
        """
        <div class="engine-card">
            <div class="status-planned">In development</div>
            <h4>NetworKit</h4>
            <p>
                Parallel network-analysis toolkit designed
                for large graph workloads.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


with st.expander("About this project"):
    st.write("""
        GraphBench investigates the engineering tradeoffs between
        in-memory graph libraries and embedded graph databases.
        It uses a common backend interface so equivalent datasets
        and workloads can be executed across multiple engines.
        """)

    st.write("""
        The project emphasizes reproducibility, correctness
        validation and workload-specific conclusions instead of
        making universal performance claims.
        """)

    st.write("""
        Current measurements include graph construction, batched
        outgoing-neighbor lookup, median latency, P95 latency and
        estimated throughput. Isolated memory and CPU profiling,
        additional graph algorithms and more database engines are
        being added.
        """)
