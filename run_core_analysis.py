import pandas as pd

from analysis.core_analysis import (
    analyze_structural_core,
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

core_report = analyze_structural_core(
    graph=health_report["graph"],
    top_n=10,
)

print("GraphBench Structural Core Analysis")
print("=" * 88)

print("\nMethod")
print("-" * 88)
print("Graph type used: Undirected structural projection")
print("Dependency direction is ignored during K-core analysis.")

print("\nCore summary")
print("-" * 88)
print(f"Maximum core number: " f"{core_report['maximum_core']}")
print(f"Deepest-core size:   " f"{len(core_report['deepest_core_components'])}")

print("\nDeepest-core components")
print("-" * 88)

for component in core_report["deepest_core_components"]:
    print(f"- {component}")

print("\nCore distribution")
print("-" * 88)
print(f"{'Core number':<16}" f"{'Components':>14}")

for (
    core_number,
    component_count,
) in core_report["core_distribution"].items():
    print(f"{core_number:<16}" f"{component_count:>14}")

print("\nTop structurally embedded components")
print("-" * 88)
print(
    f"{'Rank':<6}"
    f"{'Component':<24}"
    f"{'Core':>10}"
    f"{'Structural degree':>20}"
    f"{'Deepest core':>16}"
)

for result in core_report["rankings"]:
    print(
        f"{result['rank']:<6}"
        f"{result['component']:<24}"
        f"{result['core_number']:>10}"
        f"{result['structural_degree']:>20}"
        f"{str(result['is_deepest_core']):>16}"
    )

print("\nInterpretation of the top result")
print("-" * 88)

if core_report["rankings"]:
    print(core_report["rankings"][0]["explanation"])

print("\nMethod warnings")
print("-" * 88)

for warning in core_report["warnings"]:
    print(f"- {warning}")
