import pandas as pd

from analysis.critical_dependencies import (
    rank_critical_dependencies,
)
from analysis.dependency_health import (
    analyze_dependency_health,
)

DATASET_PATH = "data/sample_dependency_risk.csv"
SOURCE_COLUMN = "component"
TARGET_COLUMN = "depends_on"


dataframe = pd.read_csv(DATASET_PATH)

health_report = analyze_dependency_health(
    dataframe=dataframe,
    source_column=SOURCE_COLUMN,
    target_column=TARGET_COLUMN,
)

graph = health_report["graph"]

ranking_report = rank_critical_dependencies(
    graph=graph,
    top_n=10,
    alpha=0.85,
    max_iterations=100,
    tolerance=1e-6,
)

print("GraphBench Critical Dependency Ranking")
print("=" * 88)

print("\nRelationship direction")
print(f"{SOURCE_COLUMN} -> {TARGET_COLUMN} " "means the source depends on the target.")

if not health_report["is_directed_acyclic"]:
    print("\nWarning")
    print("-" * 88)
    print(
        "The graph contains a dependency cycle. "
        "The cycle may reinforce PageRank between its members."
    )
    print("Detected cycle: " f"{health_report['representative_cycle_text']}")

print("\nPageRank validation")
print("-" * 88)
print(f"Sum of PageRank scores: " f"{ranking_report['pagerank_sum']:.10f}")
print(f"Damping factor:         " f"{ranking_report['parameters']['alpha']}")
print(f"Edge weights used:      " f"{ranking_report['parameters']['weight']}")

print("\nTop critical dependencies")
print("-" * 88)
print(
    f"{'Rank':<6}"
    f"{'Component':<24}"
    f"{'PageRank':>12}"
    f"{'Dependents':>14}"
    f"{'Dependencies':>16}"
    f"{'In-degree':>14}"
)

for result in ranking_report["rankings"]:
    print(
        f"{result['rank']:<6}"
        f"{result['component']:<24}"
        f"{result['pagerank']:>12.6f}"
        f"{result['dependent_count']:>14}"
        f"{result['dependency_count']:>16}"
        f"{result['in_degree_centrality']:>14.6f}"
    )

print("\nMost critical component")
print("-" * 88)

if ranking_report["rankings"]:
    top_result = ranking_report["rankings"][0]

    print(top_result["explanation"])
else:
    print("No component could be ranked.")
