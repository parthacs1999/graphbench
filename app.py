import hashlib
import io
import json
import random
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from backends.ladybug_backend import LadybugBackend
from backends.networkx_backend import NetworkXBackend
from benchmarks.isolated_resources import compare_graph_resources
from benchmarks.reproducibility import collect_environment_metadata
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
        "description": "People connected by directed follow relationships.",
    },
    "Web links": {
        "path": Path("data/sample_web_links.csv"),
        "source": "source_page",
        "target": "target_page",
        "description": "Web pages connected by directed hyperlinks.",
    },
    "Package dependencies": {
        "path": Path("data/sample_dependencies.csv"),
        "source": "package",
        "target": "depends_on",
        "description": "Software packages connected to their dependencies.",
    },
}

GENERATED_PRESETS = {
    "Medium — 10K nodes / 50K edges": {
        "nodes": 10_000,
        "edges": 50_000,
        "seed": 42,
        "description": "A reproducible medium-sized directed graph.",
    },
    "Large — 100K nodes / 500K edges": {
        "nodes": 100_000,
        "edges": 500_000,
        "seed": 42,
        "description": "A larger reproducible graph for scalability testing.",
    },
}

ENGINE_COLORS = {
    "NetworkX": "#3B82F6",
    "LadybugDB": "#F59E0B",
}

INGESTION_RESULTS_FILE = Path("results/ingestion_scalability.csv")
QUERY_RESULTS_FILE = Path("results/query_scalability.csv")
QUERY_STRATEGY_RESULTS_FILE = Path("results/query_strategy_comparison.csv")


st.markdown(
    """
<style>
    .block-container {
        max-width: 1440px;
        padding-top: 1.15rem;
        padding-bottom: 2.5rem;
    }

    .stApp {
        background:
            radial-gradient(circle at 6% 0%, rgba(59, 130, 246, .11), transparent 30rem),
            radial-gradient(circle at 95% 2%, rgba(245, 158, 11, .08), transparent 28rem),
            #0B0F17;
    }

    section[data-testid="stSidebar"] {
        background: rgba(10, 15, 24, .96);
        border-right: 1px solid rgba(148, 163, 184, .16);
    }

    .hero {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 2rem;
        padding: 1.35rem 1.5rem;
        margin-bottom: .85rem;
        border: 1px solid rgba(148, 163, 184, .18);
        border-radius: 18px;
        background: linear-gradient(135deg, rgba(15, 23, 42, .92), rgba(17, 24, 39, .72));
        box-shadow: 0 18px 50px rgba(0, 0, 0, .16);
    }

    .hero-kicker {
        color: #60A5FA;
        font-size: .72rem;
        font-weight: 800;
        letter-spacing: .15em;
        text-transform: uppercase;
        margin-bottom: .35rem;
    }

    .hero-title {
        font-size: 2.35rem;
        font-weight: 800;
        letter-spacing: -.045em;
        line-height: 1;
        margin: 0;
    }

    .hero-description {
        color: #CBD5E1;
        max-width: 900px;
        font-size: .98rem;
        line-height: 1.55;
        margin: .7rem 0 0;
    }

    .hero-badge {
        flex: 0 0 auto;
        border: 1px solid rgba(96, 165, 250, .38);
        border-radius: 999px;
        color: #93C5FD;
        font-size: .77rem;
        font-weight: 750;
        padding: .48rem .78rem;
        white-space: nowrap;
    }

    .section-intro {
        color: #94A3B8;
        font-size: .91rem;
        line-height: 1.55;
        margin: -.25rem 0 .8rem;
    }

    .trust-strip {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: .7rem;
        margin: .4rem 0 .95rem;
    }

    .trust-item {
        border: 1px solid rgba(148, 163, 184, .16);
        border-radius: 12px;
        padding: .75rem .9rem;
        background: rgba(15, 23, 42, .38);
    }

    .trust-label {
        color: #94A3B8;
        font-size: .72rem;
        font-weight: 750;
        letter-spacing: .08em;
        text-transform: uppercase;
    }

    .trust-value {
        color: #E2E8F0;
        font-size: .9rem;
        font-weight: 650;
        margin-top: .22rem;
    }

    div[data-testid="stMetric"] {
        border: 1px solid rgba(148, 163, 184, .16);
        border-radius: 13px;
        padding: .7rem .85rem;
        background: rgba(15, 23, 42, .32);
    }

    div[data-testid="stMetricValue"] {
        font-size: 1.35rem;
    }

    div[data-testid="stMetricLabel"] {
        font-size: .78rem;
    }

    div.stButton > button,
    div[data-testid="stDownloadButton"] > button {
        min-height: 2.7rem;
        border-radius: 10px;
        font-weight: 700;
    }

    .engine-card {
        border: 1px solid rgba(148, 163, 184, .16);
        border-radius: 12px;
        padding: .85rem 1rem;
        min-height: 112px;
        background: rgba(15, 23, 42, .30);
    }

    .engine-card h4 { margin: .2rem 0 .25rem; }
    .engine-card p { color: #94A3B8; font-size: .84rem; margin: 0; }
    .available { color: #4ADE80; font-size: .7rem; font-weight: 800; text-transform: uppercase; }
    .planned { color: #FBBF24; font-size: .7rem; font-weight: 800; text-transform: uppercase; }

    @media (max-width: 850px) {
        .hero { display: block; }
        .hero-badge { display: inline-block; margin-top: .9rem; }
        .trust-strip { grid-template-columns: 1fr; }
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


@st.cache_data(show_spinner=False)
def generate_preset_csv(
    number_of_nodes: int,
    number_of_edges: int,
    seed: int,
) -> bytes:
    """Generate a deterministic graph in which every declared node appears."""
    if number_of_nodes < 2:
        raise ValueError("A generated preset requires at least two nodes")

    if number_of_edges < number_of_nodes:
        raise ValueError(
            "The edge count must be at least the node count to guarantee coverage"
        )

    maximum_edges = number_of_nodes * (number_of_nodes - 1)
    if number_of_edges > maximum_edges:
        raise ValueError("Requested more unique directed edges than are possible")

    edge_set = {
        (node_id, (node_id + 1) % number_of_nodes) for node_id in range(number_of_nodes)
    }
    random_generator = random.Random(seed)

    while len(edge_set) < number_of_edges:
        source = random_generator.randrange(number_of_nodes)
        target = random_generator.randrange(number_of_nodes)
        if source != target:
            edge_set.add((source, target))

    dataframe = pd.DataFrame(
        sorted(edge_set),
        columns=["source", "target"],
    )
    return dataframe.to_csv(index=False).encode("utf-8")


def choose_query_nodes(
    number_of_nodes: int,
    query_count: int,
    sampling: str,
    seed: int,
) -> list[int]:
    actual_count = min(query_count, number_of_nodes)

    if sampling == "Contiguous nodes":
        return list(range(actual_count))

    random_generator = random.Random(seed)
    return sorted(
        random_generator.sample(
            range(number_of_nodes),
            actual_count,
        )
    )


def run_benchmark(
    normalized_graph,
    configuration: dict,
    progress_bar=None,
    status_container=None,
) -> dict:
    query_nodes = choose_query_nodes(
        number_of_nodes=normalized_graph.number_of_nodes,
        query_count=configuration["query_count"],
        sampling=configuration["query_sampling"],
        seed=configuration["query_seed"],
    )

    networkx_backend = NetworkXBackend()
    ladybug_backend = LadybugBackend()

    try:
        if status_container is not None:
            status_container.info("Testing NetworkX...")
        if progress_bar is not None:
            progress_bar.progress(10, text="Testing NetworkX")

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
            status_container.info("NetworkX complete. Testing LadybugDB...")
        if progress_bar is not None:
            progress_bar.progress(48, text="Testing LadybugDB")

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
            status_container.info(
                "Checking that both engines returned the same answer..."
            )
        if progress_bar is not None:
            progress_bar.progress(88, text="Checking correctness")

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
                "actual_query_count": len(query_nodes),
                "query_strategy": (
                    "Adaptive range predicate"
                    if configuration["query_sampling"] == "Contiguous nodes"
                    else "Parameterized IN batch"
                ),
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
                "Operation": "Build graph",
                "Engine": "NetworkX",
                "Latency": report["networkx"]["build_median_ms"],
            },
            {
                "Operation": "Build graph",
                "Engine": "LadybugDB",
                "Latency": report["ladybug"]["build_median_ms"],
            },
            {
                "Operation": "Find neighbors",
                "Engine": "NetworkX",
                "Latency": report["networkx"]["query_median_ms"],
            },
            {
                "Operation": "Find neighbors",
                "Engine": "LadybugDB",
                "Latency": report["ladybug"]["query_median_ms"],
            },
        ]
    )

    scale_name = st.radio(
        "Chart scale",
        ["Logarithmic", "Linear"],
        horizontal=True,
        key="latency_scale",
        help="Logarithmic scale keeps very small and large values visible together.",
    )
    scale = alt.Scale(
        type="log" if scale_name == "Logarithmic" else "linear",
        zero=scale_name == "Linear",
        nice=True,
    )

    base = alt.Chart(dataframe).encode(
        x=alt.X("Latency:Q", title="Median time (milliseconds)", scale=scale),
        y=alt.Y("Operation:N", title=None, sort=["Build graph", "Find neighbors"]),
        yOffset="Engine:N",
        color=alt.Color(
            "Engine:N",
            scale=alt.Scale(
                domain=list(ENGINE_COLORS),
                range=list(ENGINE_COLORS.values()),
            ),
            legend=alt.Legend(title=None, orient="top"),
        ),
        tooltip=[
            "Operation:N",
            "Engine:N",
            alt.Tooltip("Latency:Q", format=".6f", title="Median milliseconds"),
        ],
    )

    points = base.mark_circle(size=260)
    labels = base.mark_text(align="left", dx=10, fontSize=12).encode(
        text=alt.Text("Latency:Q", format=".4f")
    )
    st.altair_chart((points + labels).properties(height=230), width="stretch")


def create_throughput_chart(report: dict) -> None:
    dataframe = pd.DataFrame(
        [
            {
                "Engine": "NetworkX",
                "Batches per second": report["networkx"]["batch_throughput_per_second"],
            },
            {
                "Engine": "LadybugDB",
                "Batches per second": report["ladybug"]["batch_throughput_per_second"],
            },
        ]
    )

    scale_name = st.radio(
        "Chart scale",
        ["Logarithmic", "Linear"],
        horizontal=True,
        key="throughput_scale",
        help="Use logarithmic scale when one engine's bar is too small to see.",
    )
    scale = alt.Scale(
        type="log" if scale_name == "Logarithmic" else "linear",
        zero=scale_name == "Linear",
        nice=True,
    )

    base = alt.Chart(dataframe).encode(
        x=alt.X(
            "Batches per second:Q",
            title="Estimated complete query batches per second",
            scale=scale,
        ),
        y=alt.Y("Engine:N", title=None, sort=["NetworkX", "LadybugDB"]),
        color=alt.Color(
            "Engine:N",
            scale=alt.Scale(
                domain=list(ENGINE_COLORS),
                range=list(ENGINE_COLORS.values()),
            ),
            legend=None,
        ),
        tooltip=[
            "Engine:N",
            alt.Tooltip("Batches per second:Q", format=",.2f"),
        ],
    )

    points = base.mark_circle(size=280)
    labels = base.mark_text(align="left", dx=11, fontSize=12).encode(
        text=alt.Text("Batches per second:Q", format=",.1f")
    )
    st.altair_chart((points + labels).properties(height=160), width="stretch")


def create_resource_chart(resource_report: dict) -> None:
    dataframe = pd.DataFrame(
        [
            {
                "Engine": "NetworkX",
                "Measurement": "Memory added",
                "Memory": resource_report["networkx"]["additional_peak_memory_mb"],
            },
            {
                "Engine": "NetworkX",
                "Measurement": "Total process peak",
                "Memory": resource_report["networkx"]["peak_memory_mb"],
            },
            {
                "Engine": "LadybugDB",
                "Measurement": "Memory added",
                "Memory": resource_report["ladybug"]["additional_peak_memory_mb"],
            },
            {
                "Engine": "LadybugDB",
                "Measurement": "Total process peak",
                "Memory": resource_report["ladybug"]["peak_memory_mb"],
            },
        ]
    )

    chart = (
        alt.Chart(dataframe)
        .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
        .encode(
            x=alt.X("Engine:N", title=None),
            xOffset="Measurement:N",
            y=alt.Y("Memory:Q", title="Memory (MB)"),
            color=alt.Color(
                "Measurement:N",
                title=None,
                scale=alt.Scale(
                    domain=["Memory added", "Total process peak"],
                    range=["#60A5FA", "#F59E0B"],
                ),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                "Engine:N",
                "Measurement:N",
                alt.Tooltip("Memory:Q", format=".2f", title="MB"),
            ],
        )
        .properties(height=245)
    )
    st.altair_chart(chart, width="stretch")


def create_ingestion_chart(dataframe: pd.DataFrame) -> None:
    chart_data = dataframe[
        [
            "nodes",
            "networkx_build_ms",
            "ladybug_ready_ms",
            "ladybug_adapter_total_ms",
        ]
    ].rename(
        columns={
            "networkx_build_ms": "NetworkX",
            "ladybug_ready_ms": "LadybugDB native load",
            "ladybug_adapter_total_ms": "LadybugDB including Arrow conversion",
        }
    )
    chart_data = chart_data.melt(
        id_vars=["nodes"],
        var_name="Measurement",
        value_name="Latency",
    )

    chart = (
        alt.Chart(chart_data)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X(
                "nodes:Q",
                title="Graph size (nodes)",
                scale=alt.Scale(type="log"),
                axis=alt.Axis(format="~s"),
            ),
            y=alt.Y(
                "Latency:Q",
                title="Median build time (ms)",
                scale=alt.Scale(type="log"),
            ),
            color=alt.Color(
                "Measurement:N", title=None, legend=alt.Legend(orient="top")
            ),
            tooltip=[
                alt.Tooltip("nodes:Q", title="Nodes", format=","),
                "Measurement:N",
                alt.Tooltip("Latency:Q", title="Milliseconds", format=".4f"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(chart, width="stretch")


def create_query_scaling_chart(dataframe: pd.DataFrame) -> None:
    batch_options = sorted(dataframe["batch_size"].unique().tolist())
    selected_batch = st.select_slider(
        "Requested nodes per query batch",
        options=batch_options,
        value=100 if 100 in batch_options else batch_options[0],
    )

    filtered = dataframe[dataframe["batch_size"] == selected_batch][
        ["nodes", "networkx_warm_median_ms", "ladybug_warm_median_ms"]
    ].rename(
        columns={
            "networkx_warm_median_ms": "NetworkX",
            "ladybug_warm_median_ms": "LadybugDB",
        }
    )
    chart_data = filtered.melt(
        id_vars=["nodes"],
        var_name="Engine",
        value_name="Latency",
    )

    chart = (
        alt.Chart(chart_data)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X(
                "nodes:Q",
                title="Graph size (nodes)",
                scale=alt.Scale(type="log"),
                axis=alt.Axis(format="~s"),
            ),
            y=alt.Y(
                "Latency:Q",
                title="Warm median query time (ms)",
                scale=alt.Scale(type="log"),
            ),
            color=alt.Color(
                "Engine:N",
                title=None,
                scale=alt.Scale(
                    domain=list(ENGINE_COLORS),
                    range=list(ENGINE_COLORS.values()),
                ),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip("nodes:Q", title="Nodes", format=","),
                "Engine:N",
                alt.Tooltip("Latency:Q", title="Milliseconds", format=".6f"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(chart, width="stretch")


def render_correctness_details(report: dict) -> None:
    correctness = report["correctness"]
    validation_columns = st.columns(3)
    validation_columns[0].metric(
        "Node counts",
        "PASS" if correctness["node_counts_match"] else "FAIL",
    )
    validation_columns[1].metric(
        "Edge counts",
        "PASS" if correctness["edge_counts_match"] else "FAIL",
    )
    validation_columns[2].metric(
        "Neighbor answers",
        "PASS" if correctness["neighbor_results_match"] else "FAIL",
    )


# -----------------------------------------------------------------------------
# Sidebar configuration
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("Set up your test")
    st.caption("Choose graph data and a repeatable workload.")

    data_source = st.radio(
        "1. Choose graph data",
        ["Sample dataset", "Generated preset", "Upload CSV"],
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
            "Download this sample",
            dataset_bytes,
            dataset_name,
            "text/csv",
            width="stretch",
        )

    elif data_source == "Generated preset":
        selected_preset = st.selectbox("Graph size", list(GENERATED_PRESETS))
        preset = GENERATED_PRESETS[selected_preset]
        st.caption(preset["description"])
        st.caption(
            f"Seed {preset['seed']} · {preset['nodes']:,} nodes · "
            f"{preset['edges']:,} directed edges"
        )

        with st.spinner("Preparing the reproducible graph..."):
            dataset_bytes = generate_preset_csv(
                number_of_nodes=preset["nodes"],
                number_of_edges=preset["edges"],
                seed=preset["seed"],
            )

        dataset_name = (
            f"synthetic_{preset['nodes']}_nodes_"
            f"{preset['edges']}_edges_seed_{preset['seed']}.csv"
        )
        source_column = "source"
        target_column = "target"

        st.download_button(
            "Download generated CSV",
            dataset_bytes,
            dataset_name,
            "text/csv",
            width="stretch",
        )

        if preset["nodes"] >= 100_000:
            st.warning(
                "This large test can take several minutes and may exceed free cloud limits."
            )

    else:
        uploaded_file = st.file_uploader(
            "Edge-list CSV",
            type=["csv"],
            help="Each row should connect one source value to one target value.",
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
        source_column = st.selectbox("Starts at", columns, index=0)
        target_column = st.selectbox(
            "Points to",
            columns,
            index=1 if len(columns) > 1 else 0,
        )

    if source_column == target_column:
        st.error("The starting and destination columns must be different.")
        st.stop()

    st.divider()
    st.markdown("#### 2. Choose the lookup pattern")
    query_sampling = st.radio(
        "Nodes to look up",
        ["Random nodes", "Contiguous nodes"],
        help=(
            "Random nodes represent general lookups. Contiguous nodes allow LadybugDB "
            "to use its tested range-query optimization."
        ),
    )
    query_seed = st.number_input(
        "Query seed",
        min_value=0,
        max_value=2_147_483_647,
        value=42,
        help="The same seed selects the same random nodes on repeated runs.",
    )

    st.divider()
    st.markdown("#### 3. Choose test depth")
    benchmark_mode = st.radio(
        "Benchmark mode",
        ["Quick", "Advanced"],
        horizontal=True,
    )

    if benchmark_mode == "Quick":
        configuration = {
            "mode": "Quick",
            "query_count": 100,
            "build_repetitions": 5,
            "build_warmups": 1,
            "query_repetitions": 20,
            "query_warmups": 3,
            "query_sampling": query_sampling,
            "query_seed": int(query_seed),
        }
        st.caption("5 builds and 20 query batches. Best for first-time visitors.")
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
            "query_sampling": query_sampling,
            "query_seed": int(query_seed),
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
# Main page
# -----------------------------------------------------------------------------
st.markdown(
    """
<div class="hero">
    <div>
        <div class="hero-kicker">Graph engine decision lab</div>
        <h1 class="hero-title">GraphBench</h1>
        <p class="hero-description">
            Upload or generate a graph, run the same work in NetworkX and LadybugDB,
            verify that both return the same answer, and see where each engine performs best.
        </p>
    </div>
    <div class="hero-badge">Open-source learning project</div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="trust-strip">
    <div class="trust-item">
        <div class="trust-label">Same input</div>
        <div class="trust-value">Both engines receive one normalized graph</div>
    </div>
    <div class="trust-item">
        <div class="trust-label">Correctness first</div>
        <div class="trust-value">Speed claims appear only after answers match</div>
    </div>
    <div class="trust-item">
        <div class="trust-label">Reproducible</div>
        <div class="trust-value">Seeds, settings, versions, and dataset hash are recorded</div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

health_columns = st.columns(5)
health_columns[0].metric("Nodes", f"{normalized_graph.number_of_nodes:,}")
health_columns[1].metric("Connections", f"{normalized_graph.valid_rows:,}")
health_columns[2].metric("Rows removed", f"{normalized_graph.missing_rows:,}")
health_columns[3].metric("Duplicates removed", f"{normalized_graph.duplicate_edges:,}")
health_columns[4].metric("Self-connections", f"{normalized_graph.self_loops:,}")

action_one, action_two = st.columns([1.3, 1])
run_performance = action_one.button(
    "Run speed and correctness test",
    type="primary",
    width="stretch",
)
run_resources = action_two.button(
    "Measure memory and CPU",
    width="stretch",
    help="Runs each engine separately for a cleaner resource comparison.",
)

status_container = st.empty()
progress_container = st.empty()

if run_performance:
    with progress_container.container():
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
            "sha256": dataset_hash,
        }
        report["environment"] = collect_environment_metadata()
        st.session_state["benchmark_report"] = report
        status_container.success("Benchmark complete. Review the summary below.")
        progress_container.empty()
    except Exception as error:
        progress_container.empty()
        status_container.error(f"Benchmark failed: {error}")

if run_resources:
    with progress_container.container():
        resource_progress = st.progress(0, text="Preparing resource measurement...")

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
            "sha256": dataset_hash,
        }
        resource_report["environment"] = collect_environment_metadata()
        st.session_state["resource_report"] = resource_report
        status_container.success("Resource measurement complete.")
        progress_container.empty()
    except Exception as error:
        progress_container.empty()
        status_container.error(f"Resource measurement failed: {error}")


report = st.session_state.get("benchmark_report")
resource_report = st.session_state.get("resource_report")

workspace_tabs = st.tabs(
    [
        "Overview",
        "Performance",
        "Scaling research",
        "Resources",
        "Your data",
        "About",
    ]
)


with workspace_tabs[0]:
    if report is None:
        st.subheader("Ready when you are")
        st.markdown(
            '<p class="section-intro">Choose data and settings in the sidebar, then run the speed and correctness test.</p>',
            unsafe_allow_html=True,
        )
        getting_started = st.columns(3)
        getting_started[0].info("1. Choose a sample, generated graph, or your own CSV.")
        getting_started[1].info("2. Select random or contiguous node lookups.")
        getting_started[2].info("3. Run the test and compare verified results.")
    else:
        correctness = report["correctness"]
        configuration_report = report["benchmark_configuration"]

        if correctness["passed"]:
            st.success("Trusted result: both engines returned equivalent answers.")
            build = report["build_comparison"]
            query = report["query_comparison"]

            st.subheader("The short answer")
            result_columns = st.columns(2)
            result_columns[0].metric(
                "Faster graph setup",
                build["winner"],
                f"{build['speedup']:.2f}× faster",
            )
            result_columns[1].metric(
                "Faster neighbor lookup",
                query["winner"],
                f"{query['speedup']:.2f}× faster",
            )

            st.info(
                "A winner applies only to this graph and workload. NetworkX is an "
                "in-memory analysis library; LadybugDB adds persistent storage, Cypher, "
                "and database-oriented analytical capabilities."
            )

            context_columns = st.columns(4)
            context_columns[0].metric(
                "Graph", f"{report['graph_health']['nodes']:,} nodes"
            )
            context_columns[1].metric(
                "Lookup batch",
                f"{configuration_report['actual_query_count']:,} nodes",
            )
            context_columns[2].metric(
                "Lookup selection",
                configuration_report["query_sampling"].replace(" nodes", ""),
            )
            context_columns[3].metric(
                "Ladybug strategy",
                configuration_report["query_strategy"],
            )
        else:
            st.error(
                "Results are not comparable because the engines returned different answers."
            )
            st.warning(
                "Timings are retained only for debugging. GraphBench hides winner claims until all checks pass."
            )
            render_correctness_details(report)


with workspace_tabs[1]:
    st.subheader("Performance details")
    st.markdown(
        '<p class="section-intro">Latency means time taken; lower is better. Throughput means completed batches per second; higher is better.</p>',
        unsafe_allow_html=True,
    )

    if report is None:
        st.info("Run the speed and correctness test to see performance results.")
    elif not report["correctness"]["passed"]:
        st.warning(
            "Performance charts are hidden because correctness validation failed."
        )
        render_correctness_details(report)
    else:
        latency_tab, throughput_tab, table_tab = st.tabs(
            ["Time taken", "Work completed", "Exact numbers"]
        )

        with latency_tab:
            create_latency_chart(report)
            st.caption(
                "Lower values are better. P95 represents a slower result near the tail of repeated runs."
            )

        with throughput_tab:
            create_throughput_chart(report)
            st.caption(
                "Estimated throughput is calculated from average batch latency; it is not a concurrent multi-user load test."
            )

        with table_tab:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Engine": "NetworkX",
                            "Build median (ms)": report["networkx"]["build_median_ms"],
                            "Build P95 (ms)": report["networkx"]["build_p95_ms"],
                            "Query median (ms)": report["networkx"]["query_median_ms"],
                            "Query P95 (ms)": report["networkx"]["query_p95_ms"],
                            "Batches/second": report["networkx"][
                                "batch_throughput_per_second"
                            ],
                        },
                        {
                            "Engine": "LadybugDB",
                            "Build median (ms)": report["ladybug"]["build_median_ms"],
                            "Build P95 (ms)": report["ladybug"]["build_p95_ms"],
                            "Query median (ms)": report["ladybug"]["query_median_ms"],
                            "Query P95 (ms)": report["ladybug"]["query_p95_ms"],
                            "Batches/second": report["ladybug"][
                                "batch_throughput_per_second"
                            ],
                        },
                    ]
                ),
                width="stretch",
                hide_index=True,
            )


with workspace_tabs[2]:
    st.subheader("Saved scaling research")
    st.markdown(
        '<p class="section-intro">These are precomputed development-machine experiments, not results from the graph currently selected in the sidebar.</p>',
        unsafe_allow_html=True,
    )

    show_saved_research = st.toggle(
        "Show saved research results",
        value=False,
        help="Open previously generated ingestion and query scalability studies.",
    )

    if not show_saved_research:
        research_columns = st.columns(3)
        research_columns[0].metric("Small graph", "1K nodes", "NetworkX setup wins")
        research_columns[1].metric("Crossover", "10K nodes", "LadybugDB ingestion wins")
        research_columns[2].metric(
            "Large graph", "100K nodes", "LadybugDB ingestion scales"
        )
        st.info(
            "The research found different winners for different jobs: LadybugDB scaled better for optimized bulk ingestion, while NetworkX remained faster for direct neighbor lookup."
        )
    else:
        ingestion_tab, query_tab, strategy_tab = st.tabs(
            ["Graph ingestion", "Neighbor lookup", "Query strategies"]
        )

        with ingestion_tab:
            st.markdown("#### How graph setup scales")
            st.write(
                "LadybugDB uses sorted PyArrow tables, bulk COPY, and ANALYZE. Native load excludes Arrow conversion; adapter-inclusive load includes it."
            )

            if not INGESTION_RESULTS_FILE.exists():
                st.info(
                    "Run `python run_ingestion_scalability.py` to create these results."
                )
            else:
                ingestion_results = pd.read_csv(INGESTION_RESULTS_FILE)
                create_ingestion_chart(ingestion_results)
                st.dataframe(ingestion_results, width="stretch", hide_index=True)
                st.success(
                    "Observed result: NetworkX won the 1K-node setup, while LadybugDB won optimized ingestion at 10K and 100K nodes."
                )

        with query_tab:
            st.markdown("#### How neighbor lookup scales")
            st.write(
                "Random node batches test a general lookup pattern. Lower latency is better. The logarithmic chart keeps both engines visible."
            )

            if not QUERY_RESULTS_FILE.exists():
                st.info(
                    "Run `python run_query_scalability.py` to create these results."
                )
            else:
                query_results = pd.read_csv(QUERY_RESULTS_FILE)
                create_query_scaling_chart(query_results)
                st.dataframe(query_results, width="stretch", hide_index=True)
                st.info(
                    "Observed result: batching reduced LadybugDB's cost per requested node, but NetworkX remained faster for direct adjacency lookup."
                )

        with strategy_tab:
            st.markdown("#### LadybugDB query-strategy experiment")
            st.write(
                "This test compared equivalent Cypher approaches for a contiguous 100-node batch on a 100K-node graph."
            )

            if not QUERY_STRATEGY_RESULTS_FILE.exists():
                st.info(
                    "Run `python compare_query_strategies.py` to create these results."
                )
            else:
                strategy_results = pd.read_csv(QUERY_STRATEGY_RESULTS_FILE).sort_values(
                    "warm_median_ms"
                )
                st.dataframe(strategy_results, width="stretch", hide_index=True)
                fastest = strategy_results.iloc[0]
                st.success(
                    f"Fastest measured strategy: {fastest['strategy']} at "
                    f"{fastest['warm_median_ms']:.4f} ms. Range lookup applies only to contiguous IDs."
                )


with workspace_tabs[3]:
    st.subheader("Memory and CPU")
    st.markdown(
        '<p class="section-intro">Each engine runs in a separate process so one engine does not inherit the other engine\'s memory.</p>',
        unsafe_allow_html=True,
    )

    if resource_report is None:
        st.info("Select Measure memory and CPU above to create a resource comparison.")
    else:
        if resource_report["correctness"]:
            st.success("Resource-test correctness passed.")
        else:
            st.error("Resource-test correctness failed; do not compare these numbers.")

        networkx_resource = resource_report["networkx"]
        ladybug_resource = resource_report["ladybug"]

        resource_columns = st.columns(4)
        resource_columns[0].metric(
            "NetworkX memory added",
            f"{networkx_resource['additional_peak_memory_mb']:.2f} MB",
        )
        resource_columns[1].metric(
            "LadybugDB memory added",
            f"{ladybug_resource['additional_peak_memory_mb']:.2f} MB",
        )
        resource_columns[2].metric(
            "NetworkX CPU",
            f"{networkx_resource['cpu_utilization_percent']:.1f}%",
        )
        resource_columns[3].metric(
            "LadybugDB CPU",
            f"{ladybug_resource['cpu_utilization_percent']:.1f}%",
        )

        chart_column, explanation_column = st.columns([1.35, 1])
        with chart_column:
            create_resource_chart(resource_report)
        with explanation_column:
            st.info(
                "Memory added estimates the extra memory used while building the graph. Total process peak also includes Python and imported libraries."
            )
            st.caption(
                "CPU may exceed 100% when native code uses more than one processor core. Small graphs are often dominated by startup overhead."
            )


with workspace_tabs[4]:
    preview_column, explanation_column = st.columns([1.45, 1])

    with preview_column:
        st.subheader(dataset_name)
        st.dataframe(preview_dataframe.head(15), width="stretch", hide_index=True)
        st.caption(f"Showing 15 of {len(preview_dataframe):,} original rows.")

    with explanation_column:
        st.subheader("Data preparation")
        st.write(f"Starting-node column: `{source_column}`")
        st.write(f"Destination-node column: `{target_column}`")
        st.write(f"Rows missing an endpoint: **{normalized_graph.missing_rows:,}**")
        st.write(
            f"Duplicate connections removed: **{normalized_graph.duplicate_edges:,}**"
        )
        st.write(f"Self-connections retained: **{normalized_graph.self_loops:,}**")
        st.info(
            "GraphBench converts labels such as names or URLs into internal numeric IDs so both engines receive exactly the same graph."
        )


with workspace_tabs[5]:
    about_tab, methodology_tab, roadmap_tab = st.tabs(
        ["Product", "Methodology", "Roadmap"]
    )

    with about_tab:
        st.subheader("What GraphBench is")
        st.write(
            "GraphBench is an interactive graph-engine evaluation product. It helps developers understand whether an in-memory analysis library or an embedded graph database better fits a particular workload."
        )
        st.write(
            "The project demonstrates correctness validation, reproducible performance engineering, isolated resource measurement, user-data ingestion, query-plan investigation, and evidence-driven optimization."
        )
        st.caption(
            "Python · NetworkX · LadybugDB · Cypher · PyArrow · Pandas · Streamlit · Altair"
        )

    with methodology_tab:
        st.markdown("""
#### How to read the results

- **Build median:** typical time to create a fresh query-ready backend.
- **Query median:** typical time for one complete neighbor-query batch.
- **P95:** a slower tail result; 95% of measured runs finished at or below it.
- **Throughput:** estimated batches per second from average latency, not a concurrent load test.
- **Correctness:** node counts, edge counts, and returned neighbors must match before winner claims appear.

#### LadybugDB optimizations applied

- Sorted PyArrow bulk loading instead of Pandas ingestion.
- `ANALYZE` after loading.
- Parameterized Cypher for plan reuse.
- Fresh backend for each build repetition, excluding previous-graph deletion.
- Python-side result sorting instead of database `ORDER BY`.
- Range predicates for contiguous batches and `IN` for arbitrary batches.

#### Known limitation

Profiling LadybugDB 0.20.3 showed node and relationship scans plus a target-node hash join for arbitrary batched neighbor lookup. This explains why NetworkX remains faster for direct adjacency access even when LadybugDB wins larger optimized ingestion workloads.
""")

        available_report = report or resource_report
        st.divider()
        st.markdown("#### Reproducibility record")

        if available_report is None:
            st.info(
                "Run a benchmark or resource test to record this machine and package versions."
            )
        elif "environment" not in available_report:
            st.info("Run this test again to create an environment record.")
        else:
            environment = available_report["environment"]
            packages = environment["packages"]
            system = environment["system"]

            environment_columns = st.columns(4)
            environment_columns[0].metric("Python", environment["python"]["version"])
            environment_columns[1].metric("NetworkX", packages["networkx"])
            environment_columns[2].metric("LadybugDB", packages["ladybug"])
            environment_columns[3].metric("Machine", system["machine"])

            st.caption(
                f"Recorded {environment['timestamp_utc']} · Dataset SHA-256 "
                f"{available_report['dataset']['sha256'][:16]}..."
            )

            with st.expander("Complete environment details"):
                st.json(environment)

    with roadmap_tab:
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
            "Download reproducibility report",
            json.dumps(combined_report, indent=2),
            "graphbench_report.json",
            "application/json",
            width="stretch",
        )

        with st.expander("Raw report"):
            st.json(combined_report)
