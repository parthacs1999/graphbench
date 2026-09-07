from typing import Any


def compare_results(
    operation_name: str,
    networkx_result: Any,
    ladybug_result: Any,
) -> dict:
    matches = networkx_result == ladybug_result

    return {
        "operation": operation_name,
        "networkx_result": networkx_result,
        "ladybug_result": ladybug_result,
        "matches": matches,
    }
