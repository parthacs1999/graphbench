GraphBench

GraphBench is an interactive software-dependency intelligence tool and graph-engine benchmarking project. It converts a directed edge-list CSV into an explainable architecture review: critical dependencies, path bottlenecks, circular dependencies, structural cores, and simulated failure impact.

The project began as a correctness-first comparison between NetworkX and LadybugDB and evolved into a user-facing tool for architecture analysis and dependency-risk investigation.

Live application: GraphBench on Streamlit Community Cloud

Why GraphBench?

Software systems often contain dependency relationships that are difficult to reason about from configuration files or spreadsheets alone. Teams need practical answers to questions such as:

Which shared component deserves the strongest reliability controls?

Where are the architectural bottlenecks?

Does the system contain circular dependencies?

Which components form the tightly connected structural core?

If a component fails, what could be affected?

Which graph engine is appropriate for a particular workload?

GraphBench uses graph algorithms to generate review signals and then translates those signals into plain-language explanations and recommended engineering actions.

GraphBench identifies components that deserve review. Its findings are not proof that a component is defective and should be validated with system owners, runtime telemetry, and operational context.

Product workflow

Choose the guided dependency sample or upload an edge-list CSV.

Select the component and dependency columns.

Confirm the relationship direction.

Review graph-quality information.

Run dependency intelligence analysis.

Explore the graph through different algorithmic lenses.

Simulate component failure and inspect the potential blast radius.

Download reproducible JSON and CSV reports.

Core features

Guided data setup

Three-step setup dialog

Built-in software-dependency sample

User CSV upload

Explicit relationship-direction confirmation

Missing-row and duplicate-edge validation

Dataset hashing and environment metadata

Dependency intelligence

PageRank-based critical dependency ranking

Betweenness-centrality bottleneck detection

Directed cycle detection

K-core structural analysis

Direct and transitive dependent counts

Transparent review signals and interpretation cautions

Downloadable review candidate report

Graph Explorer

The same dependency graph can be viewed through four analysis lenses:

Lens

Visual meaning

Critical dependencies

Node size and color represent PageRank

Path bottlenecks

Node size and color represent betweenness centrality

Structural core

Node size and color represent K-core depth

Dependency cycles

Cycle members and cycle edges are highlighted

The explorer supports tooltips, zooming, panning, important-node labels, and focused subgraphs for larger inputs.

Failure-impact simulator

Select a component and GraphBench calculates:

Direct dependents

Indirect dependents

Total potentially affected components

Blast-radius percentage

Maximum impact depth

Shortest dependency paths

Impact layers by distance

Cycle membership

A color-coded impact graph

A downloadable incident-impact report

Impact graph colors:

Red: simulated failed component

Orange: directly affected components

Blue: indirectly affected components

Relationship direction

GraphBench uses the following edge meaning:

component -> depends_on

For example:

api_gateway -> logging

means that api_gateway depends on logging.

If logging becomes unavailable, GraphBench searches for components that can reach logging through dependency paths. Internally, the failure-impact algorithm performs breadth-first search on the reversed graph.

flowchart LR
    Storefront[storefront] --> Gateway[api_gateway]
    Gateway --> Auth[authentication]
    Auth --> Logging[logging]

If logging fails, the potential impact path is:

storefront -> api_gateway -> authentication -> logging

Algorithms

PageRank

PageRank highlights dependencies that receive importance from other important components. In a dependency graph, a high score can indicate a widely relied-upon component.

Cycles may reinforce PageRank between their members. GraphBench therefore reports cycle membership as a caution instead of interpreting PageRank in isolation.

Betweenness centrality

Betweenness centrality measures how frequently a component lies on shortest dependency paths. A high value can indicate an architectural connector or bottleneck.

Exact betweenness is used for smaller graphs. Larger supported graphs may use deterministic sampling to control execution time.

K-core

K-core analysis finds components that remain connected after lower-degree components are repeatedly removed. GraphBench runs K-core on an undirected structural projection, so dependency direction is intentionally ignored for this measurement.

Strongly connected components

Strongly connected components identify groups in which each component can reach the others. A group containing multiple components represents a directed dependency cycle.

Failure-impact traversal

The impact simulator reverses the dependency graph and performs a breadth-first search from the simulated failed component. This produces all reachable dependents and their shortest impact paths in:

Time:  O(V + E)
Space: O(V + E)

where V is the number of components and E is the number of dependency relationships.

Example result

The included sample contains 19 components and 24 directed dependencies. It intentionally includes the following cycle:

logging -> monitoring -> logging

The sample analysis identifies:

logging as the highest-PageRank dependency

api_gateway as the strongest dependency-path bottleneck

A deepest structural core of 10 components

A cycle between logging and monitoring

Simulating failure of logging produces:

Metric

Result

Direct dependents

5

Indirect dependents

5

Total affected components

10

Blast radius

55.56%

Maximum impact depth

3

The blast radius excludes the selected component from the denominator:

10 affected components / 18 other components = 55.56%

NetworkX and LadybugDB research

The repository also contains correctness-first experiments comparing NetworkX with LadybugDB.

The benchmark process includes:

Equivalent normalized graph data

Matching node and edge counts

Matching neighbor-query results

Warm-up runs

Repeated measurements

Median and P95 latency

Estimated throughput

Isolated-process memory and CPU measurements

Saved environment and package metadata

Main findings

NetworkX remained faster for direct in-process adjacency lookup in the tested workloads.

LadybugDB became competitive or faster for larger optimized bulk-ingestion workloads.

LadybugDB performance improved substantially after using sorted PyArrow tables, bulk COPY, parameterized queries, and ANALYZE.

Query profiling showed that arbitrary batched neighbor lookup could still introduce scans and joins that direct NetworkX dictionary access avoids.

A benchmark result applies only to the tested dataset, operation, configuration, package versions, and machine.

This is not evidence that one engine is universally faster. NetworkX is an in-process graph-analysis library, while LadybugDB provides database capabilities such as Cypher, persistence, and database-oriented query execution.

Technology stack

Python

NetworkX

LadybugDB

Cypher

PyArrow

Pandas

Streamlit

Altair

psutil

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
│   ├── base.py
│   ├── ladybug_backend.py
│   └── networkx_backend.py
├── benchmarks/
│   ├── isolated_resources.py
│   ├── reproducibility.py
│   ├── resource_worker.py
│   ├── resources.py
│   ├── runner.py
│   └── timer.py
├── data/
│   └── sample_dependency_risk.csv
├── ingestion/
│   └── csv_loader.py
├── results/
├── app.py
├── requirements.txt
├── run_bottleneck_analysis.py
├── run_core_analysis.py
├── run_critical_dependencies.py
├── run_dependency_health.py
├── run_dependency_report.py
├── run_impact_analysis.py
├── run_ingestion_comparison.py
├── run_ingestion_scalability.py
├── run_query_scalability.py
└── run_resource_comparison.py

The exact repository contents may grow as additional analyses and graph engines are introduced.

Installation

1. Clone the repository

git clone <your-repository-url>
cd graphbench

Replace <your-repository-url> with the actual GitHub repository URL.

2. Create a virtual environment

macOS or Linux:

python3 -m venv .venv
source .venv/bin/activate

Windows PowerShell:

python -m venv .venv
.venv\Scripts\Activate.ps1

3. Install dependencies

python -m pip install --upgrade pip
pip install -r requirements.txt

The project was tested with LadybugDB 0.20.3. Use the same version when reproducing the saved engine experiments.

4. Validate the application

python -m py_compile app.py

5. Start GraphBench

streamlit run app.py

Open the local URL printed by Streamlit, normally:

http://localhost:8501

CSV input format

GraphBench accepts a directed edge-list CSV with at least two columns.

Example:

component,depends_on
storefront,api_gateway
mobile_app,api_gateway
api_gateway,authentication
authentication,logging
monitoring,logging
logging,monitoring

Column names do not need to be component and depends_on. The setup dialog lets the user select the correct source and target columns.

Data preparation includes:

Removing rows with missing endpoints

Removing duplicate relationships

Trimming component labels

Preserving self-dependencies for explicit analysis

Mapping the same normalized graph into the analysis workflow

Running the analysis scripts

Dependency health:

python run_dependency_health.py

Critical dependency ranking:

python run_critical_dependencies.py

Architectural bottlenecks:

python run_bottleneck_analysis.py

Structural core:

python run_core_analysis.py

Combined dependency-intelligence report:

python run_dependency_report.py

Failure-impact analysis:

python run_impact_analysis.py

Running the benchmark research

Basic engine comparison:

python run_comparison.py

Ingestion comparison:

python run_ingestion_comparison.py

Ingestion scalability:

python run_ingestion_scalability.py

Neighbor-query scalability:

python run_query_scalability.py

Isolated resource comparison:

python run_resource_comparison.py

Benchmarking principles

GraphBench follows these rules when comparing engines:

Validate equivalent results before comparing performance.

Use identical normalized graph data.

Separate warm-up runs from measured runs.

Report medians and tail latency instead of relying on one run.

Isolate resource measurements in separate processes.

Record dataset hashes, seeds, package versions, Python version, and system metadata.

Distinguish native ingestion from adapter-conversion overhead.

Use parameterized LadybugDB queries and run ANALYZE after ingestion.

State workload limitations instead of claiming a universal winner.

Deployment

GraphBench can be deployed through Streamlit Community Cloud.

Push the repository to GitHub.

Sign in to Streamlit Community Cloud.

Select the repository and branch.

Set the application entry point to app.py.

Confirm that requirements.txt includes all imported packages.

Deploy and inspect the build logs.

Large analyses may exceed free cloud memory or execution limits. The current dependency-intelligence interface therefore limits architecture analysis to 2,000 components and renders a focused subgraph when the complete graph would be unreadable.

Known limitations

Graph findings represent structural relationships, not runtime traffic or production failure probability.

All uploaded dependencies are currently treated as unweighted.

K-core and articulation-style structural interpretations ignore edge direction when explicitly stated.

PageRank can be reinforced by dependency cycles.

Betweenness can be expensive and may use approximation for larger graphs.

The current Altair graph renderer is suitable for small and focused subgraphs but is not a full graph-editing environment.

Very large graphs need asynchronous jobs, persistent storage, and additional sampling or aggregation strategies.

LadybugDB graph-algorithm extension availability may vary by platform and package build.

Roadmap

Replace the current graph renderer with a dedicated interactive network component

Add node search and click-to-inspect behavior

Add weighted dependencies and relationship types

Compare architecture snapshots across commits

Import dependency data from package manifests and service catalogs

Add CI checks for newly introduced cycles and blast-radius regressions

Add community detection with Louvain or Leiden

Add Personalized PageRank for component-specific investigation

Add persistent project history and team annotations

Add additional graph engines such as Neo4j, igraph, or NetworKit

Add automated tests and continuous integration

Responsible interpretation

GraphBench should support—not replace—engineering judgment. Before acting on a finding:

Verify that the uploaded relationship direction is correct.

Confirm the dependency with component owners.

Compare structural findings with runtime telemetry.

Check whether fallbacks, replication, retries, or isolation boundaries reduce the practical risk.

Re-run the analysis after architecture changes.

Project motivation

GraphBench demonstrates how graph algorithms, database benchmarking, performance engineering, reproducibility, and product-oriented UI design can be combined into a practical developer tool. The project emphasizes transparent methodology and actionable explanations rather than presenting algorithm scores without context.

Author

Partha Chakraborty
Master's student in Computer Science (AI/ML), University at Buffalo
GitHub profile
