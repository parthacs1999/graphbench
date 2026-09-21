import pandas as pd

from analysis.dependency_health import (
    analyze_dependency_health,
)

DATASET_PATH = "data/sample_dependency_risk.csv"
SOURCE_COLUMN = "component"
TARGET_COLUMN = "depends_on"


dataframe = pd.read_csv(DATASET_PATH)

report = analyze_dependency_health(
    dataframe=dataframe,
    source_column=SOURCE_COLUMN,
    target_column=TARGET_COLUMN,
)

data_quality = report["data_quality"]

print("GraphBench Dependency Health")
print("=" * 60)

print("\nRelationship meaning")
print(
    f"{SOURCE_COLUMN} -> {TARGET_COLUMN} " f"means the component depends on the target."
)

print("\nData quality")
print("-" * 60)
print(f"Original rows:       " f"{data_quality['original_rows']:,}")
print(f"Valid unique edges:  " f"{data_quality['valid_unique_edges']:,}")
print(f"Missing rows:        " f"{data_quality['missing_rows']:,}")
print(f"Empty rows:          " f"{data_quality['empty_rows']:,}")
print(f"Duplicate edges:     " f"{data_quality['duplicate_edges']:,}")
print(f"Self-dependencies:   " f"{data_quality['self_loops']:,}")

print("\nGraph structure")
print("-" * 60)
print(f"Components:                    " f"{report['number_of_nodes']:,}")
print(f"Dependencies:                  " f"{report['number_of_edges']:,}")
print(f"Density:                       " f"{report['density']:.6f}")
print(f"Weakly connected subsystems:   " f"{report['weakly_connected_components']:,}")
print(f"Strongly connected components: " f"{report['strongly_connected_components']:,}")
print(
    f"Directed acyclic graph:        "
    f"{'YES' if report['is_directed_acyclic'] else 'NO'}"
)

print("\nDependency-cycle check")
print("-" * 60)

if report["representative_cycle_text"] is None:
    print("No dependency cycle was detected.")
else:
    print("Dependency cycle detected:")
    print(report["representative_cycle_text"])

print("\nHealth warnings")
print("-" * 60)

if report["warnings"]:
    for warning in report["warnings"]:
        print(f"- {warning}")
else:
    print("No structural warnings were found.")
