import hashlib
import io
import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from backends.ladybug_backend import LadybugBackend
from backends.networkx_backend import NetworkXBackend
from benchmarks.isolated_resources import compare_graph_resources
from benchmarks.runner import benchmark_backend
from ingestion.csv_loader import load_edge_csv

st.set_page_config(
    page_title="GraphBench",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)


SAMPLE_DATASETS = {
    "Social network": {
        "path": Path("data/sample_social_network.csv"),
        "source": "follower",
        "target": "followed",
        "description": "Users connected by directed follow relationships.",
    },
    "Web links": {
        "path": Path("data/sample_web_links.csv"),
        "source": "source_page",
        "target": "target_page",
        "description": "A directed graph of links between web pages.",
    },
    "Package dependencies": {
        "path": Path("data/sample_dependencies.csv"),
        "source": "package",
        "target": "depends_on",
        "description": "Packages connected to their dependencies.",
    },
}

ENGINE_COLORS = {
    "NetworkX": "#3B82F6",
    "LadybugDB": "#F59E0B",
}


st.markdown(
    """
<style>
    .block-container {
        max-width: 1450px;
        padding-top: 1.25rem;
        padding-bottom: 2rem;
    }

    .stApp {
        background:
            radial-gradient(circle at 8% 0%, rgba(37, 99, 235, .10), transparent 28rem),
            radial-gradient(circle at 96% 5%, rgba(245, 158, 11, .08), transparent 25rem);
    }

    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(148, 163, 184, .18);
    }

    .product-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 2rem;
        border: 1px solid rgba(148, 163, 184, .20);
        border-radius: 16px;
        padding: 1.1rem 1.35rem;
        margin-bottom: .85rem;
        background: rgba(15, 23, 42, .30);
    }

    .product-kicker {
        color: #60A5FA;
        font-size: .74rem;
        font-weight: 750;
        margin-top: 12px;
        letter-spacing: .14em;
        text-transform: uppercase;
        margin-bottom: .25rem;
    }

    .product-title {
        font-size: 2rem;
        font-weight: 780;
        letter-spacing: -.04em;
        line-height: 1;
        margin: 0;
    }

    .product-description {
        color: #CBD5E1;
        font-size: .94rem;
        line-height: 1.5;
        margin: .55rem 0 0;
        max-width: 850px;
    }

    .product-badge {
        flex: 0 0 auto;
        border: 1px solid rgba(96, 165, 250, .35);
        border-radius: 999px;
        color: #93C5FD;
        font-size: .78rem;
        font-weight: 700;
        padding: .45rem .75rem;
        white-space: nowrap;
    }

    div[data-testid="stMetric"] {
        border: 1px solid rgba(148, 163, 184, .18);
        border-radius: 12px;
        padding: .65rem .8rem;
        background: rgba(15, 23, 42, .24);
    }

    div[data-testid="stMetricValue"] {
        font-size: 1.35rem;
    }

    div[data-testid="stMetricLabel"] {
        font-size: .78rem;
    }

    div.stButton > button,
    div[data-testid="stDownloadButton"] > button {
        min-height: 2.75rem;
        border-radius: 10px;
        font-weight: 700;
    }

    .engine-card {
        border: 1px solid rgba(148, 163, 184, .18);
        border-radius: 12px;
        padding: .85rem 1rem;
        min-height: 112px;
        background: rgba(15, 23, 42, .24);
    }

    .engine-card h4 { margin: .2rem 0 .25rem; }
    .engine-card p { color: #94A3B8; font-size: .85rem; margin: 0; }
    .available { color: #4ADE80; font-size: .72rem; font-weight: 750; text-transform: uppercase; }
    .planned { color: #FBBF24; font-size: .72rem; font-weight: 750; text-transform: uppercase; }

    @media (max-width: 800px) {
        .product-header { display: block; }
        .product-badge { display: inline-block; margin-top: .75rem; }
    }
</style>
""",
    unsafe_allow_html=True,
)


def determine_comparison(networkx_value: float, ladybug_value: float) -> dict:
    if networkx_value <= 0 or ladybug_value <= 0:
        return {"winner": "Inconclusive", "speedup": 0.0}

    if networkx_value < ladybug_value:
        return {
            "winner": "NetworkX",
            "speedup": ladybug_value / networkx_value,
        }

    return {
        "winner": "LadybugDB",
        "speedup": networkx_value / ladybug_value,
    }


def run_benchmark(
    normalized_graph,
    configuration: dict,
    progress_bar=None,
    status_container=None,
) -> dict:
    query_count = min(
        configuration["query_count"],
        normalized_graph.number_of_nodes,
    )
    query_nodes = list(range(query_count))
    networkx_backend = NetworkXBackend()
    ladybug_backend = LadybugBackend()

    try:
        if status_container is not None:
            status_container.info("Running NetworkX benchmark...")
        if progress_bar is not None:
            progress_bar.progress(10, text="Running NetworkX")

        networkx_results = benchmark_backend(
            backend=networkx_backend,
            number_of_nodes=normalized_graph.number_of_nodes,
            edges=normalized_graph.edges,
            query_nodes=query_nodes,
            build_repetitions=configuration["build_repetitions"],
            build_warmup_runs=configuration["build_warmups"],
            query_repetitions=configuration["query_repetitions"],
            query_warmup_runs=configuration["query_warmups"],
        )

        if status_container is not None:
            status_container.info("NetworkX complete. Running LadybugDB...")
        if progress_bar is not None:
            progress_bar.progress(48, text="Running LadybugDB")

        ladybug_results = benchmark_backend(
            backend=ladybug_backend,
            number_of_nodes=normalized_graph.number_of_nodes,
            edges=normalized_graph.edges,
            query_nodes=query_nodes,
            build_repetitions=configuration["build_repetitions"],
            build_warmup_runs=configuration["build_warmups"],
            query_repetitions=configuration["query_repetitions"],
            query_warmup_runs=configuration["query_warmups"],
        )

        if status_container is not None:
            status_container.info("Validating equivalent results...")
        if progress_bar is not None:
            progress_bar.progress(88, text="Validating correctness")

        neighbors_match = (
            networkx_results["neighbors"]["result"]
            == ladybug_results["neighbors"]["result"]
        )
        nodes_match = (
            networkx_results["number_of_nodes"]
            == ladybug_results["number_of_nodes"]
            == normalized_graph.number_of_nodes
        )
        edges_match = (
            networkx_results["number_of_edges"]
            == ladybug_results["number_of_edges"]
            == len(normalized_graph.edges)
        )

        networkx_build = networkx_results["build"]["median_ms"]
        ladybug_build = ladybug_results["build"]["median_ms"]
        networkx_query = networkx_results["neighbors"]["median_ms"]
        ladybug_query = ladybug_results["neighbors"]["median_ms"]

        if progress_bar is not None:
            progress_bar.progress(100, text="Benchmark complete")

        return {
            "graph_health": {
                "nodes": normalized_graph.number_of_nodes,
                "edges": normalized_graph.valid_rows,
                "missing_rows": normalized_graph.missing_rows,
                "duplicate_edges": normalized_graph.duplicate_edges,
                "self_loops": normalized_graph.self_loops,
            },
            "benchmark_configuration": {
                **configuration,
                "actual_query_count": query_count,
            },
            "correctness": {
                "passed": neighbors_match and nodes_match and edges_match,
                "node_counts_match": nodes_match,
                "edge_counts_match": edges_match,
                "neighbor_results_match": neighbors_match,
            },
            "networkx": {
                "build_median_ms": networkx_build,
                "build_p95_ms": networkx_results["build"]["p95_ms"],
                "query_median_ms": networkx_query,
                "query_p95_ms": networkx_results["neighbors"]["p95_ms"],
                "batch_throughput_per_second": networkx_results["neighbors"][
                    "throughput_per_second"
                ],
            },
            "ladybug": {
                "build_median_ms": ladybug_build,
                "build_p95_ms": ladybug_results["build"]["p95_ms"],
                "query_median_ms": ladybug_query,
                "query_p95_ms": ladybug_results["neighbors"]["p95_ms"],
                "batch_throughput_per_second": ladybug_results["neighbors"][
                    "throughput_per_second"
                ],
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
    dataframe = pd.DataFrame(
        [
            {
                "Operation": "Construction",
                "Backend": "NetworkX",
                "Latency": report["networkx"]["build_median_ms"],
            },
            {
                "Operation": "Construction",
                "Backend": "LadybugDB",
                "Latency": report["ladybug"]["build_median_ms"],
            },
            {
                "Operation": "Neighbor batch",
                "Backend": "NetworkX",
                "Latency": report["networkx"]["query_median_ms"],
            },
            {
                "Operation": "Neighbor batch",
                "Backend": "LadybugDB",
                "Latency": report["ladybug"]["query_median_ms"],
            },
        ]
    )

    scale_name = st.radio(
        "Latency scale",
        ["Logarithmic", "Linear"],
        index=0,
        horizontal=True,
        key="latency_scale",
    )
    scale = alt.Scale(
        type="log" if scale_name == "Logarithmic" else "linear",
        zero=False if scale_name == "Logarithmic" else True,
        nice=True,
    )

    base = alt.Chart(dataframe).encode(
        x=alt.X("Latency:Q", title="Median latency (ms)", scale=scale),
        y=alt.Y("Operation:N", title=None, sort=["Construction", "Neighbor batch"]),
        yOffset="Backend:N",
        color=alt.Color(
            "Backend:N",
            scale=alt.Scale(
                domain=list(ENGINE_COLORS),
                range=list(ENGINE_COLORS.values()),
            ),
            legend=alt.Legend(title=None, orient="top"),
        ),
        tooltip=[
            "Operation:N",
            "Backend:N",
            alt.Tooltip("Latency:Q", format=".6f", title="Median latency (ms)"),
        ],
    )
    points = base.mark_circle(size=250)
    labels = base.mark_text(align="left", dx=10, fontSize=12).encode(
        text=alt.Text("Latency:Q", format=".6f")
    )
    st.altair_chart((points + labels).properties(height=220), use_container_width=True)


def create_throughput_chart(report: dict) -> None:
    dataframe = pd.DataFrame(
        [
            {
                "Backend": "NetworkX",
                "Batches per second": report["networkx"]["batch_throughput_per_second"],
            },
            {
                "Backend": "LadybugDB",
                "Batches per second": report["ladybug"]["batch_throughput_per_second"],
            },
        ]
    )
    chart = (
        alt.Chart(dataframe)
        .mark_bar(cornerRadiusEnd=5, height=28)
        .encode(
            x=alt.X("Batches per second:Q", title="Estimated batches per second"),
            y=alt.Y("Backend:N", title=None, sort=["NetworkX", "LadybugDB"]),
            color=alt.Color(
                "Backend:N",
                scale=alt.Scale(
                    domain=list(ENGINE_COLORS), range=list(ENGINE_COLORS.values())
                ),
                legend=None,
            ),
            tooltip=["Backend:N", alt.Tooltip("Batches per second:Q", format=",.2f")],
        )
        .properties(height=145)
    )
    st.altair_chart(chart, use_container_width=True)


def create_resource_charts(resource_report: dict) -> None:
    memory_data = pd.DataFrame(
        [
            {
                "Backend": "NetworkX",
                "Metric": "Additional peak",
                "Memory (MB)": resource_report["networkx"]["additional_peak_memory_mb"],
            },
            {
                "Backend": "NetworkX",
                "Metric": "Process peak",
                "Memory (MB)": resource_report["networkx"]["peak_memory_mb"],
            },
            {
                "Backend": "LadybugDB",
                "Metric": "Additional peak",
                "Memory (MB)": resource_report["ladybug"]["additional_peak_memory_mb"],
            },
            {
                "Backend": "LadybugDB",
                "Metric": "Process peak",
                "Memory (MB)": resource_report["ladybug"]["peak_memory_mb"],
            },
        ]
    )
    memory_chart = (
        alt.Chart(memory_data)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Backend:N", title=None),
            xOffset="Metric:N",
            y=alt.Y("Memory (MB):Q", title="Memory (MB)"),
            color=alt.Color(
                "Metric:N",
                scale=alt.Scale(
                    domain=["Additional peak", "Process peak"],
                    range=["#60A5FA", "#F59E0B"],
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                "Backend:N",
                "Metric:N",
                alt.Tooltip("Memory (MB):Q", format=".2f"),
            ],
        )
        .properties(height=220)
    )
    st.altair_chart(memory_chart, use_container_width=True)


def show_benchmark_insight(report: dict) -> None:
    if not report["correctness"]["passed"]:
        st.error(
            "The engines returned different results, so no recommendation is made."
        )
        return

    if report["graph_health"]["nodes"] < 100:
        st.warning(
            "This graph is very small. Initialization and timer overhead can dominate the measured work."
        )

    build = report["build_comparison"]
    query = report["query_comparison"]
    st.markdown(f"""
**Measured outcome**

- **{build['winner']}** completed construction approximately **{build['speedup']:.2f}x faster**.
- **{query['winner']}** completed the neighbor workload approximately **{query['speedup']:.2f}x faster**.
""")
    st.info(
        "Choose an engine based on the target workload. NetworkX is an in-process graph-analysis library; "
        "LadybugDB offers database capabilities such as Cypher and persistent graph storage."
    )
    st.caption(
        "The conclusion applies only to this dataset, workload, configuration, machine, and installed versions."
    )


# -----------------------------------------------------------------------------
# Compact sidebar: dataset and benchmark configuration
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("GraphBench")
    st.caption("Configure one reproducible comparison.")

    data_source = st.radio(
        "Graph source",
        ["Sample dataset", "Upload CSV"],
    )

    dataset_bytes = None
    dataset_name = None
    source_column = None
    target_column = None

    if data_source == "Sample dataset":
        selected_sample = st.selectbox("Dataset", list(SAMPLE_DATASETS))
        sample = SAMPLE_DATASETS[selected_sample]
        sample_path = sample["path"]
        st.caption(sample["description"])

        if not sample_path.exists():
            st.error(f"Missing {sample_path}. Run `python create_sample_datasets.py`.")
            st.stop()

        dataset_bytes = sample_path.read_bytes()
        dataset_name = sample_path.name
        source_column = sample["source"]
        target_column = sample["target"]
        st.download_button(
            "Download sample CSV",
            dataset_bytes,
            dataset_name,
            "text/csv",
            use_container_width=True,
        )
    else:
        uploaded_file = st.file_uploader(
            "Edge-list CSV",
            type=["csv"],
            help="Choose one source column and one target column.",
        )
        if uploaded_file is None:
            st.info("Upload a CSV to begin.")
            st.stop()
        dataset_bytes = uploaded_file.getvalue()
        dataset_name = uploaded_file.name

    try:
        preview_dataframe = pd.read_csv(io.BytesIO(dataset_bytes))
    except Exception as error:
        st.error(f"Could not read the CSV: {error}")
        st.stop()

    if preview_dataframe.empty or len(preview_dataframe.columns) < 2:
        st.error("The CSV needs at least two columns and one data row.")
        st.stop()

    columns = list(preview_dataframe.columns)
    if data_source == "Upload CSV":
        source_column = st.selectbox("Source column", columns, index=0)
        target_column = st.selectbox(
            "Target column",
            columns,
            index=1 if len(columns) > 1 else 0,
        )

    if source_column == target_column:
        st.error("Source and target columns must be different.")
        st.stop()

    st.divider()
    benchmark_mode = st.radio("Benchmark mode", ["Quick", "Advanced"], horizontal=True)

    if benchmark_mode == "Quick":
        configuration = {
            "mode": "Quick",
            "query_count": 100,
            "build_repetitions": 5,
            "build_warmups": 1,
            "query_repetitions": 20,
            "query_warmups": 3,
        }
        st.caption("5 builds, 20 query batches, automatic query sampling.")
    else:
        with st.expander("Advanced settings", expanded=True):
            query_count = st.number_input("Nodes per query batch", 1, 1_000_000, 100)
            build_repetitions = st.number_input("Build repetitions", 1, 50, 5)
            build_warmups = st.number_input("Build warm-ups", 0, 10, 1)
            query_repetitions = st.number_input("Query repetitions", 1, 1_000, 50)
            query_warmups = st.number_input("Query warm-ups", 0, 100, 5)
        configuration = {
            "mode": "Advanced",
            "query_count": int(query_count),
            "build_repetitions": int(build_repetitions),
            "build_warmups": int(build_warmups),
            "query_repetitions": int(query_repetitions),
            "query_warmups": int(query_warmups),
        }


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

configuration["query_count"] = min(
    configuration["query_count"],
    normalized_graph.number_of_nodes,
)

dataset_hash = hashlib.sha256(dataset_bytes).hexdigest()
dataset_key = (dataset_hash, source_column, target_column)
benchmark_key = (*dataset_key, json.dumps(configuration, sort_keys=True))

if st.session_state.get("active_dataset_key") != dataset_key:
    st.session_state.pop("benchmark_report", None)
    st.session_state.pop("resource_report", None)
    st.session_state["active_dataset_key"] = dataset_key

if st.session_state.get("active_benchmark_key") != benchmark_key:
    st.session_state.pop("benchmark_report", None)
    st.session_state["active_benchmark_key"] = benchmark_key


# -----------------------------------------------------------------------------
# Main workspace
# -----------------------------------------------------------------------------
st.markdown(
    """
<div class="product-header">
    <div>
        <div class="product-kicker">Reproducible graph-engine evaluation</div>
        <h1 class="product-title">GraphBench</h1>
        <p class="product-description">
            Compare NetworkX and LadybugDB on the same graph and workload. Validate equivalent
            results before examining latency, throughput, memory, and CPU behavior.
        </p>
    </div>
    <div class="product-badge">Open-source learning project</div>
</div>
""",
    unsafe_allow_html=True,
)

health_columns = st.columns(5)
health_columns[0].metric("Nodes", f"{normalized_graph.number_of_nodes:,}")
health_columns[1].metric("Edges", f"{normalized_graph.valid_rows:,}")
health_columns[2].metric("Missing", f"{normalized_graph.missing_rows:,}")
health_columns[3].metric("Duplicates", f"{normalized_graph.duplicate_edges:,}")
health_columns[4].metric("Self-loops", f"{normalized_graph.self_loops:,}")

action_one, action_two = st.columns(2)
run_performance = action_one.button(
    "Run performance benchmark",
    type="primary",
    use_container_width=True,
)
run_resources = action_two.button(
    "Run isolated resource profile",
    use_container_width=True,
    help="Runs each engine in a separate process for cleaner memory and CPU measurements.",
)

status_container = st.empty()
progress_bar = st.empty()

if run_performance:
    with progress_bar.container():
        benchmark_progress = st.progress(0, text="Starting benchmark...")
    try:
        report = run_benchmark(
            normalized_graph,
            configuration,
            benchmark_progress,
            status_container,
        )
        report["dataset"] = {
            "name": dataset_name,
            "source_column": source_column,
            "target_column": target_column,
        }
        st.session_state["benchmark_report"] = report
        status_container.success("Performance benchmark completed.")
        progress_bar.empty()
    except Exception as error:
        progress_bar.empty()
        status_container.error(f"Performance benchmark failed: {error}")

if run_resources:
    with progress_bar.container():
        resource_progress = st.progress(0, text="Preparing resource profile...")

    def update_resource_progress(percentage: int, message: str) -> None:
        resource_progress.progress(percentage, text=message)
        status_container.info(message)

    try:
        resource_report = compare_graph_resources(
            number_of_nodes=normalized_graph.number_of_nodes,
            edges=normalized_graph.edges,
            progress_callback=update_resource_progress,
        )
        resource_report["dataset"] = {
            "name": dataset_name,
            "source_column": source_column,
            "target_column": target_column,
        }
        st.session_state["resource_report"] = resource_report
        status_container.success("Isolated resource profile completed.")
        progress_bar.empty()
    except Exception as error:
        progress_bar.empty()
        status_container.error(f"Resource profiling failed: {error}")


workspace_tabs = st.tabs(
    ["Results", "Latency", "Throughput", "Resources", "Data", "Project"]
)

report = st.session_state.get("benchmark_report")
resource_report = st.session_state.get("resource_report")

with workspace_tabs[0]:
    if report is None:
        st.info("Run the performance benchmark to generate a comparison.")
    else:
        if report["correctness"]["passed"]:
            st.success("Correctness PASS: both engines produced equivalent results.")
        else:
            st.error("Correctness FAIL: do not use these performance results.")

        build = report["build_comparison"]
        query = report["query_comparison"]
        columns = st.columns(4)
        columns[0].metric(
            "NetworkX build", f"{report['networkx']['build_median_ms']:.4f} ms"
        )
        columns[1].metric(
            "LadybugDB build", f"{report['ladybug']['build_median_ms']:.4f} ms"
        )
        columns[2].metric(
            "NetworkX query", f"{report['networkx']['query_median_ms']:.4f} ms"
        )
        columns[3].metric(
            "LadybugDB query", f"{report['ladybug']['query_median_ms']:.4f} ms"
        )

        insight_one, insight_two = st.columns(2)
        insight_one.info(
            f"Construction: {build['winner']} was {build['speedup']:.2f}x faster."
        )
        insight_two.info(
            f"Neighbor batch: {query['winner']} was {query['speedup']:.2f}x faster."
        )
        show_benchmark_insight(report)

with workspace_tabs[1]:
    if report is None:
        st.info("Latency results appear after the performance benchmark.")
    else:
        create_latency_chart(report)
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Backend": "NetworkX",
                        "Build median (ms)": report["networkx"]["build_median_ms"],
                        "Build P95 (ms)": report["networkx"]["build_p95_ms"],
                        "Query median (ms)": report["networkx"]["query_median_ms"],
                        "Query P95 (ms)": report["networkx"]["query_p95_ms"],
                    },
                    {
                        "Backend": "LadybugDB",
                        "Build median (ms)": report["ladybug"]["build_median_ms"],
                        "Build P95 (ms)": report["ladybug"]["build_p95_ms"],
                        "Query median (ms)": report["ladybug"]["query_median_ms"],
                        "Query P95 (ms)": report["ladybug"]["query_p95_ms"],
                    },
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

with workspace_tabs[2]:
    if report is None:
        st.info("Throughput results appear after the performance benchmark.")
    else:
        create_throughput_chart(report)
        st.caption(
            "Estimated throughput is derived from average batch latency; it is not a concurrent load test."
        )

with workspace_tabs[3]:
    if resource_report is None:
        st.info("Run the isolated resource profile to compare memory and CPU usage.")
    else:
        if resource_report["correctness"]:
            st.success("Resource-profile correctness PASS.")
        else:
            st.error("Resource-profile correctness FAIL.")

        nx_resource = resource_report["networkx"]
        lb_resource = resource_report["ladybug"]
        resource_columns = st.columns(4)
        resource_columns[0].metric(
            "NetworkX added memory",
            f"{nx_resource['additional_peak_memory_mb']:.2f} MB",
        )
        resource_columns[1].metric(
            "LadybugDB added memory",
            f"{lb_resource['additional_peak_memory_mb']:.2f} MB",
        )
        resource_columns[2].metric(
            "NetworkX CPU",
            f"{nx_resource['cpu_utilization_percent']:.1f}%",
        )
        resource_columns[3].metric(
            "LadybugDB CPU",
            f"{lb_resource['cpu_utilization_percent']:.1f}%",
        )

        chart_column, table_column = st.columns([1.15, 1])
        with chart_column:
            create_resource_charts(resource_report)
        with table_column:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Backend": "NetworkX",
                            "Isolated build (ms)": nx_resource["elapsed_ms"],
                            "Added peak (MB)": nx_resource["additional_peak_memory_mb"],
                            "Process peak (MB)": nx_resource["peak_memory_mb"],
                            "CPU (%)": nx_resource["cpu_utilization_percent"],
                        },
                        {
                            "Backend": "LadybugDB",
                            "Isolated build (ms)": lb_resource["elapsed_ms"],
                            "Added peak (MB)": lb_resource["additional_peak_memory_mb"],
                            "Process peak (MB)": lb_resource["peak_memory_mb"],
                            "CPU (%)": lb_resource["cpu_utilization_percent"],
                        },
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "CPU can exceed 100% when a process uses more than one core. Tiny graphs are dominated by engine startup overhead."
            )

with workspace_tabs[4]:
    preview_column, health_column = st.columns([1.5, 1])
    with preview_column:
        st.subheader(dataset_name)
        st.dataframe(
            preview_dataframe.head(15), use_container_width=True, hide_index=True
        )
        st.caption(f"Showing 15 of {len(preview_dataframe):,} original rows.")
    with health_column:
        st.subheader("Normalization")
        st.write(f"Source column: `{source_column}`")
        st.write(f"Target column: `{target_column}`")
        st.write(f"Missing rows removed: **{normalized_graph.missing_rows:,}**")
        st.write(f"Duplicate edges removed: **{normalized_graph.duplicate_edges:,}**")
        st.write(f"Self-loops retained: **{normalized_graph.self_loops:,}**")

with workspace_tabs[5]:
    about_column, roadmap_column = st.columns([1.25, 1])
    with about_column:
        st.subheader("What GraphBench demonstrates")
        st.write(
            "GraphBench evaluates in-memory graph libraries and embedded graph databases using "
            "the same normalized data and equivalent operations. Correctness is checked before "
            "performance results are presented."
        )
        st.markdown(
            "**Current measurements:** construction latency, neighbor-query latency, P95 latency, "
            "estimated throughput, isolated memory, and isolated CPU usage."
        )
        st.caption(
            "Python · NetworkX · LadybugDB · Cypher · Pandas · Streamlit · Altair"
        )
    with roadmap_column:
        st.subheader("Engine roadmap")
        engine_columns = st.columns(2)
        cards = [
            ("NetworkX", "available", "Available", "In-memory Python graph analytics."),
            (
                "LadybugDB",
                "available",
                "Available",
                "Embedded property-graph database.",
            ),
            ("Neo4j", "planned", "In development", "Server-based Cypher database."),
            (
                "igraph / NetworKit",
                "planned",
                "In development",
                "Compiled graph-analysis engines.",
            ),
        ]
        for index, (name, css_class, status, description) in enumerate(cards):
            with engine_columns[index % 2]:
                st.markdown(
                    f"""
<div class="engine-card">
    <div class="{css_class}">{status}</div>
    <h4>{name}</h4>
    <p>{description}</p>
</div>
""",
                    unsafe_allow_html=True,
                )


combined_report = {
    "performance": report,
    "resources": resource_report,
}
if report is not None or resource_report is not None:
    with st.sidebar:
        st.divider()
        st.download_button(
            "Download current report",
            json.dumps(combined_report, indent=2),
            "graphbench_report.json",
            "application/json",
            use_container_width=True,
        )
        with st.expander("Raw report"):
            st.json(combined_report)
