import json
from pathlib import Path

import pandas as pd

from analysis.dependency_report import (
    generate_dependency_intelligence_report,
)

DATASET_PATH = "data/sample_dependency_risk.csv"
OUTPUT_PATH = Path("results/dependency_intelligence_report.json")

SOURCE_COLUMN = "component"
TARGET_COLUMN = "depends_on"


dataframe = pd.read_csv(DATASET_PATH)

report = generate_dependency_intelligence_report(
    dataframe=dataframe,
    source_column=SOURCE_COLUMN,
    target_column=TARGET_COLUMN,
    top_n=10,
    pagerank_alpha=0.85,
    exact_betweenness_threshold=2_000,
    approximation_samples=500,
    seed=42,
)

summary = report["executive_summary"]

print("GraphBench Dependency Intelligence")
print("=" * 100)

print("\nExecutive summary")
print("-" * 100)
print(f"Status:                    " f"{report['status']}")
print(
    f"Highest PageRank:          "
    f"{summary['highest_pagerank_component']} "
    f"({summary['highest_pagerank_score']:.6f})"
)
print(
    f"Strongest bottleneck:      "
    f"{summary['strongest_bottleneck']} "
    f"({summary['strongest_betweenness_score']:.6f})"
)
print(f"Deepest structural core:  " f"{summary['maximum_core']}-core")
print(f"Deepest-core components:  " f"{summary['deepest_core_size']}")
print(
    f"Dependency cycle:         "
    f"{'DETECTED' if summary['dependency_cycle_detected'] else 'NONE'}"
)

if summary["representative_cycle"]:
    print(f"Representative cycle:     " f"{summary['representative_cycle']}")

print("\nComponents recommended for review")
print("-" * 100)
print(
    f"{'Rank':<6}"
    f"{'Component':<24}"
    f"{'Signals':>10}"
    f"{'PageRank':>12}"
    f"{'Between.':>12}"
    f"{'Core':>8}"
    f"{'Cycle':>10}"
)

for result in report["review_candidates"]:
    print(
        f"{result['review_rank']:<6}"
        f"{result['component']:<24}"
        f"{result['structural_signal_count']:>10}"
        f"{result['pagerank']:>12.6f}"
        f"{result['betweenness']:>12.6f}"
        f"{result['core_number']:>8}"
        f"{str(result['in_dependency_cycle']):>10}"
    )

    for signal in result["signals"]:
        print(f"      - {signal}")

    for caution in result["cautions"]:
        print(f"      ! {caution}")

print("\nMethodology")
print("-" * 100)

for key, value in report["methodology"].items():
    print(f"{key}: {value}")

OUTPUT_PATH.parent.mkdir(
    parents=True,
    exist_ok=True,
)

with OUTPUT_PATH.open(
    "w",
    encoding="utf-8",
) as output_file:
    json.dump(
        report,
        output_file,
        indent=2,
    )

print(f"\nSaved report to {OUTPUT_PATH}")
