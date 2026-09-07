import json

from benchmarks.reproducibility import collect_environment_metadata

metadata = collect_environment_metadata()

print(json.dumps(metadata, indent=2))
