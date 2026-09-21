import pandas as pd

from analysis.bottleneck_analysis import (
    analyze_bottlenecks,
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

bottleneck_report = analyze_bottlenecks(
    graph=health_report["graph"],
    top_n=10,
    exact_threshold=2_000,
    approximation_samples=500,
    seed=42,
)

print("GraphBench Architectural Bottleneck Analysis")
print("=" * 100)

print("\nMethod")
print("-" * 100)
print(f"Betweenness calculation: " f"{bottleneck_report['betweenness_mode'].upper()}")

if bottleneck_report["betweenness_samples"]:
    print(f"Sampled source nodes:    " f"{bottleneck_report['betweenness_samples']:,}")

print("Articulation analysis:   " "Undirected structural projection")

print("\nTop architectural bottlenecks")
print("-" * 100)
print(
    f"{'Rank':<6}"
    f"{'Component':<24}"
    f"{'Betweenness':>14}"
    f"{'Direct':>12}"
    f"{'Transitive':>14}"
    f"{'Articulation':>16}"
)

for result in bottleneck_report["rankings"]:
    print(
        f"{result['rank']:<6}"
        f"{result['component']:<24}"
        f"{result['betweenness']:>14.6f}"
        f"{result['direct_dependents']:>12}"
        f"{result['transitive_dependents']:>14}"
        f"{str(result['is_articulation_point']):>16}"
    )

print("\nStructural articulation points")
print("-" * 100)

if bottleneck_report["articulation_points"]:
    for component in bottleneck_report["articulation_points"]:
        print(f"- {component}")
else:
    print("No articulation points were found.")

print("\nStructural bridges")
print("-" * 100)

if bottleneck_report["bridges"]:
    for source, target in bottleneck_report["bridges"]:
        print(f"- {source} -- {target}")
else:
    print("No structural bridges were found.")

print("\nInterpretation of the top result")
print("-" * 100)

if bottleneck_report["rankings"]:
    print(bottleneck_report["rankings"][0]["explanation"])

print("\nMethod warnings")
print("-" * 100)

for warning in bottleneck_report["warnings"]:
    print(f"- {warning}")
