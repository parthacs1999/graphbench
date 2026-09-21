import json

import pandas as pd

from analysis.impact_analysis import analyze_dependency_impact

DATA_FILE = "data/sample_dependency_risk.csv"
SOURCE_COLUMN = "component"
TARGET_COLUMN = "depends_on"
COMPONENT = "logging"


dataframe = pd.read_csv(DATA_FILE)

report = analyze_dependency_impact(
    dataframe=dataframe,
    source_column=SOURCE_COLUMN,
    target_column=TARGET_COLUMN,
    component=COMPONENT,
)

summary = report["impact_summary"]

print("GraphBench Failure-Impact Analysis")
print("=" * 90)

print("\nRelationship direction")
print("-" * 90)
print("component -> depends_on")
print(
    "Affected components are components that directly "
    "or indirectly depend on the selected component."
)

print("\nSelected component")
print("-" * 90)
print(report["component"])

print("\nImpact summary")
print("-" * 90)
print(f"Direct dependents:          " f"{summary['direct_dependents']}")
print(f"Indirect dependents:        " f"{summary['indirect_dependents']}")
print(f"Total affected components: " f"{summary['total_affected_components']}")
print(f"Blast radius:               " f"{summary['blast_radius_percent']:.2f}%")
print(f"Maximum impact depth:       " f"{summary['maximum_impact_depth']}")

print("\nDirect dependents")
print("-" * 90)

if report["direct_dependents"]:
    for component in report["direct_dependents"]:
        print(f"- {component}")
else:
    print("No direct dependents found.")

print("\nIndirect dependents")
print("-" * 90)

if report["indirect_dependents"]:
    for component in report["indirect_dependents"]:
        print(f"- {component}")
else:
    print("No indirect dependents found.")

print("\nImpact paths")
print("-" * 90)

if report["impact_paths"]:
    for affected_component, path in report["impact_paths"].items():
        print(f"{affected_component}: " f"{' -> '.join(path)}")
else:
    print("No affected components found.")

print("\nCycle information")
print("-" * 90)

if report["cycle"]["in_cycle"]:
    print("The selected component participates in a cycle.")
    print("Cycle members: " + ", ".join(report["cycle"]["cycle_members"]))
else:
    print("The selected component does not participate " "in a dependency cycle.")

with open(
    "results/impact_analysis.json",
    "w",
    encoding="utf-8",
) as report_file:
    json.dump(
        report,
        report_file,
        indent=2,
    )

print("\nSaved report to " "results/impact_analysis.json")
