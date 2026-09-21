GraphBench

GraphBench is an interactive software-dependency intelligence tool. Upload a directed edge-list CSV to discover critical dependencies, architectural bottlenecks, dependency cycles, structural cores, and the potential impact of a component failure.

Live application

Open GraphBench

GraphBench began as a correctness-first NetworkX versus LadybugDB benchmark and evolved into a user-facing architecture-analysis product.

What problem does it solve?

Software dependency graphs are difficult to understand from configuration files and spreadsheets. GraphBench helps answer:

Which shared dependency deserves the strongest reliability controls?

Where are the architectural bottlenecks?

Does the system contain circular dependencies?

Which components form the structural core?

If one component fails, what else could be affected?

GraphBench produces review signals, not proof that a component is defective. Findings should be combined with runtime telemetry and engineering context.

Features

Guided analysis

Built-in dependency sample or CSV upload

Three-step setup flow

Explicit relationship-direction confirmation

Missing-row and duplicate-edge validation

Reproducible JSON and CSV reports

Dependency intelligence

PageRank: finds influential shared dependencies

Betweenness centrality: identifies dependency-path bottlenecks

Cycle detection: exposes circular dependency chains

K-core: finds deeply embedded structural layers

Explainable review candidates with interpretation cautions

Graph Explorer

Visualize the same graph through four lenses:

Lens

Visual meaning

Critical dependencies

Size and color represent PageRank

Path bottlenecks

Size and color represent betweenness

Structural core

Size and color represent K-core depth

Dependency cycles

Cycle members and edges are highlighted

The explorer provides tooltips, zooming, panning, labels, and focused subgraphs for larger inputs.

Failure-impact simulator

Select a component and calculate:

Direct and indirect dependents

Total affected components

Blast-radius percentage

Maximum impact depth

Shortest dependency paths

Cycle membership

Color-coded impact graph

Impact graph colors:

Red: simulated failed component

Orange: directly affected component

Blue: indirectly affected component

Relationship direction

GraphBench interprets edges as:

component -> depends_on

For example, api_gateway -> logging means that api_gateway depends on logging. If logging fails, GraphBench searches backward for components that directly or indirectly depend on it.

flowchart LR
    Storefront[storefront] --> Gateway[api_gateway]
    Gateway --> Auth[authentication]
    Auth --> Logging[logging]

Example result

The sample contains 19 components and 24 dependencies, including the cycle:

logging -> monitoring -> logging

GraphBench identifies logging as the highest-PageRank dependency, api_gateway as the strongest path bottleneck, and a deepest structural core containing 10 components.

Simulating failure of logging produces:

Metric

Result

Direct dependents

5

Indirect dependents

5

Total affected

10

Blast radius

55.56%

Maximum depth

3

NetworkX and LadybugDB research

The repository also contains correctness-first engine benchmarks covering latency, throughput, ingestion scalability, memory, and CPU usage.

Main findings from the tested workloads:

NetworkX was faster for direct in-process adjacency lookup.

LadybugDB became faster for larger optimized bulk-ingestion workloads.

LadybugDB improved after sorted PyArrow loading, bulk COPY, parameterized queries, and ANALYZE.

Results apply only to the tested data, workload, versions, and machine; neither engine is universally faster.

Technology stack

Python · NetworkX · LadybugDB · Cypher · PyArrow · Pandas · Streamlit · Altair · psutil

Project structure

graphbench/
├── analysis/
│   ├── bottleneck_analysis.py
│   ├── core_analysis.py
│   ├── critical_dependencies.py
│   ├── dependency_health.py
│   ├── dependency_report.py
│   └── impact_analysis.py
├── backends/
│   ├── ladybug_backend.py
│   └── networkx_backend.py
├── benchmarks/
├── data/sample_dependency_risk.csv
├── ingestion/
├── results/
├── app.py
└── requirements.txt

Installation

git clone <your-repository-url>
cd graphbench

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

Windows PowerShell activation:

.venv\Scripts\Activate.ps1

The benchmark research was tested with LadybugDB 0.20.3.

Run the application

python -m py_compile app.py
streamlit run app.py

Open http://localhost:8501 or use the live application.

CSV format

component,depends_on
storefront,api_gateway
api_gateway,authentication
authentication,logging
monitoring,logging
logging,monitoring

Column names may differ; users select the source and target columns during setup.

Run individual analyses

python run_dependency_health.py
python run_critical_dependencies.py
python run_bottleneck_analysis.py
python run_core_analysis.py
python run_dependency_report.py
python run_impact_analysis.py

Run benchmark research:

python run_comparison.py
python run_ingestion_scalability.py
python run_query_scalability.py
python run_resource_comparison.py

Methodology

GraphBench validates equivalent results before engine comparisons, uses identical normalized data, separates warm-up and measured runs, reports median and P95 latency, isolates resource measurements, and records seeds, versions, settings, and dataset hashes.

Failure-impact analysis performs breadth-first search on the reversed dependency graph with O(V + E) time and space complexity.

Limitations

Structural importance does not equal runtime failure probability.

Dependencies are currently unweighted.

K-core uses an undirected projection.

Cycles may reinforce PageRank.

Betweenness may use approximation on larger graphs.

Dependency intelligence is limited to 2,000 components.

Altair is not a complete graph-editing environment.

Roadmap

Dedicated graph renderer with node search and selection

Weighted and typed dependencies

Architecture comparison across commits

CI checks for new cycles and blast-radius regressions

Package-manifest and service-catalog imports

Louvain or Leiden community detection

Personalized PageRank

Additional graph engines

Author

Partha Chakraborty
Master's student in Computer Science (AI/ML), University at Buffalo
GitHub
