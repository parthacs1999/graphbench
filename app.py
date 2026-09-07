import hashlib
import json

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
)


def determine_comparison(
    networkx_time: float,
    ladybug_time: float,
) -> dict:
    if networkx_time < ladybug_time:
        return {
            "winner": "NetworkX",
            "speedup": ladybug_time / networkx_time,
        }

    return {
        "winner": "LadybugDB",
        "speedup": networkx_time / ladybug_time,
    }


def run_benchmark(normalized_graph) -> dict:
    query_count = min(
        100,
        normalized_graph.number_of_nodes,
    )

    query_nodes = list(range(query_count))

    networkx_backend = NetworkXBackend()
    ladybug_backend = LadybugBackend()

    try:
        networkx_results = benchmark_backend(
            backend=networkx_backend,
            number_of_nodes=(normalized_graph.number_of_nodes),
            edges=normalized_graph.edges,
            query_nodes=query_nodes,
        )

        ladybug_results = benchmark_backend(
            backend=ladybug_backend,
            number_of_nodes=(normalized_graph.number_of_nodes),
            edges=normalized_graph.edges,
            query_nodes=query_nodes,
        )

        correctness = (
            networkx_results["neighbors"]["result"]
            == ladybug_results["neighbors"]["result"]
        )

        networkx_build = networkx_results["build"]["median_ms"]

        ladybug_build = ladybug_results["build"]["median_ms"]

        networkx_query = networkx_results["neighbors"]["median_ms"]

        ladybug_query = ladybug_results["neighbors"]["median_ms"]

        return {
            "graph_health": {
                "nodes": normalized_graph.number_of_nodes,
                "edges": normalized_graph.valid_rows,
                "missing_rows": normalized_graph.missing_rows,
                "duplicate_edges": (normalized_graph.duplicate_edges),
                "self_loops": normalized_graph.self_loops,
            },
            "benchmark_configuration": {
                "neighbor_queries_per_batch": query_count,
                "build_repetitions": 5,
                "query_repetitions": 20,
            },
            "correctness": correctness,
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
                    "#2563EB",
                    "#F59E0B",
                ],
            ),
            legend=alt.Legend(
                title="Backend",
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
                title="Median latency (ms)",
                format=".6f",
            ),
        ],
    )

    points = base_chart.mark_circle(
        size=250,
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
        height=300,
    )

    st.altair_chart(
        chart,
        use_container_width=True,
    )

    if scale_option == "Logarithmic":
        st.caption(
            "The logarithmic scale shows multiplicative "
            "differences. Every measured value remains visible "
            "because dots do not require a zero baseline."
        )
    else:
        st.caption(
            "The linear scale shows absolute differences. "
            "Dots keep very small measurements visible even "
            "when they are close to zero."
        )


def show_query_insight(report: dict) -> None:
    comparison = report["query_comparison"]
    graph_health = report["graph_health"]

    st.subheader("Benchmark insight")

    if not report["correctness"]:
        st.error(
            "The backends returned different results. "
            "No performance recommendation can be made."
        )
        return

    if graph_health["nodes"] < 100:
        st.warning(
            "This graph is too small for a strong backend "
            "recommendation. Fixed initialization and query "
            "overhead dominate operations at this scale."
        )

    st.write(
        f"For this neighbor-lookup workload, "
        f"**{comparison['winner']}** completed the batch "
        f"approximately **{comparison['speedup']:.2f}× faster**."
    )

    if comparison["winner"] == "NetworkX":
        st.write(
            "NetworkX is a strong fit for this measured workload "
            "because the graph is already in memory and neighbor "
            "lookups access its adjacency structure directly."
        )
    else:
        st.write(
            "LadybugDB performed better for this measured " "neighbor-query workload."
        )

    st.info(
        "This result applies only to the uploaded dataset, "
        "selected workload, installed software versions and "
        "current machine. It does not prove that one backend "
        "is universally faster."
    )


st.title("GraphBench")

st.write(
    "Upload an edge-list CSV to compare NetworkX and "
    "LadybugDB using the same graph and workload."
)


uploaded_file = st.file_uploader(
    "Upload an edge-list CSV",
    type=["csv"],
)


if uploaded_file is None:
    st.info("Upload a CSV containing source and target columns " "to begin.")
    st.stop()


uploaded_bytes = uploaded_file.getvalue()

dataset_hash = hashlib.sha256(uploaded_bytes).hexdigest()


try:
    uploaded_file.seek(0)
    preview_dataframe = pd.read_csv(uploaded_file)
except Exception as error:
    st.error(f"Could not read the CSV: {error}")
    st.stop()


if len(preview_dataframe.columns) < 2:
    st.error("The CSV must contain at least two columns.")
    st.stop()


if preview_dataframe.empty:
    st.error("The CSV does not contain any data rows.")
    st.stop()


st.subheader("Data preview")

st.dataframe(
    preview_dataframe.head(10),
    use_container_width=True,
)


columns = list(preview_dataframe.columns)

mapping_column_one, mapping_column_two = st.columns(2)


with mapping_column_one:
    source_column = st.selectbox(
        "Starting-node column",
        options=columns,
        index=0,
    )


with mapping_column_two:
    available_target_indexes = [
        index for index, column in enumerate(columns) if column != source_column
    ]

    default_target_index = (
        available_target_indexes[0] if available_target_indexes else 0
    )

    target_column = st.selectbox(
        "Connected-node column",
        options=columns,
        index=default_target_index,
    )


if source_column == target_column:
    st.warning("Choose different source and target columns.")
    st.stop()


uploaded_file.seek(0)


try:
    normalized_graph = load_edge_csv(
        file_path=uploaded_file,
        source_column=source_column,
        target_column=target_column,
    )
except Exception as error:
    st.error(f"Could not prepare the graph: {error}")
    st.stop()


if normalized_graph.number_of_nodes == 0:
    st.error(
        "No valid graph data remained after removing "
        "missing source and target values."
    )
    st.stop()


st.subheader("Graph health")

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
    "Duplicate edges",
    f"{normalized_graph.duplicate_edges:,}",
)

health_columns[4].metric(
    "Self-loops",
    f"{normalized_graph.self_loops:,}",
)


if normalized_graph.number_of_nodes < 100:
    st.warning(
        "This is a very small graph. Fixed library and "
        "query overhead may dominate the result, so large "
        "speedup ratios should be interpreted cautiously."
    )


current_dataset_key = (
    dataset_hash,
    source_column,
    target_column,
)


if st.session_state.get("dataset_key") != current_dataset_key:
    st.session_state.pop(
        "benchmark_report",
        None,
    )

    st.session_state["dataset_key"] = current_dataset_key


if st.button(
    "Run comparison",
    type="primary",
    use_container_width=True,
):
    with st.spinner("Running equivalent workloads in both backends..."):
        try:
            benchmark_report = run_benchmark(normalized_graph)

            st.session_state["benchmark_report"] = benchmark_report
        except Exception as error:
            st.error(f"The benchmark could not be completed: {error}")
            st.stop()


if "benchmark_report" not in st.session_state:
    st.stop()


report = st.session_state["benchmark_report"]


st.subheader("Benchmark results")


if report["correctness"]:
    st.success(
        "Correctness passed: both backends returned " "the same neighbor results."
    )
else:
    st.error("Correctness failed. The performance results " "should not be used.")


result_column_one, result_column_two = st.columns(2)


with result_column_one:
    st.markdown("### Graph construction")

    st.metric(
        "NetworkX median",
        (f"{report['networkx']['build_median_ms']:.6f} ms"),
    )

    st.metric(
        "NetworkX P95",
        (f"{report['networkx']['build_p95_ms']:.6f} ms"),
    )

    st.metric(
        "LadybugDB median",
        (f"{report['ladybug']['build_median_ms']:.6f} ms"),
    )

    st.metric(
        "LadybugDB P95",
        (f"{report['ladybug']['build_p95_ms']:.6f} ms"),
    )

    build_comparison = report["build_comparison"]

    st.write(
        f"**{build_comparison['winner']}** completed "
        f"graph construction "
        f"{build_comparison['speedup']:.2f}× faster."
    )


with result_column_two:
    st.markdown("### Neighbor-query batch")

    st.metric(
        "NetworkX median",
        (f"{report['networkx']['query_median_ms']:.6f} ms"),
    )

    st.metric(
        "NetworkX P95",
        (f"{report['networkx']['query_p95_ms']:.6f} ms"),
    )

    st.metric(
        "LadybugDB median",
        (f"{report['ladybug']['query_median_ms']:.6f} ms"),
    )

    st.metric(
        "LadybugDB P95",
        (f"{report['ladybug']['query_p95_ms']:.6f} ms"),
    )

    query_comparison = report["query_comparison"]

    st.write(
        f"**{query_comparison['winner']}** completed "
        f"the neighbor-query batch "
        f"{query_comparison['speedup']:.2f}× faster."
    )


st.subheader("Latency comparison")

create_latency_chart(report)


show_query_insight(report)


st.subheader("Download results")

report_json = json.dumps(
    report,
    indent=2,
)


st.download_button(
    label="Download JSON report",
    data=report_json,
    file_name="graphbench_report.json",
    mime="application/json",
    use_container_width=True,
)


st.caption(
    "GraphBench currently compares directed, unweighted "
    "graphs using graph construction and batched outgoing-"
    "neighbor lookup workloads."
)
