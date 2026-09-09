from backends.networkx_backend import NetworkXBackend

backend = NetworkXBackend()

edges = [
    (0, 1),
    (1, 4),
    (0, 2),
    (2, 3),
    (3, 4),
]

try:
    backend.build_graph(
        number_of_nodes=6,
        edges=edges,
    )

    test_cases = [
        (0, 4, [0, 1, 4]),
        (0, 3, [0, 2, 3]),
        (4, 0, None),
        (2, 2, [2]),
        (0, 99, None),
    ]

    all_passed = True

    for source, target, expected in test_cases:
        actual = backend.shortest_path(
            source=source,
            target=target,
        )

        passed = actual == expected
        all_passed = all_passed and passed

        print(
            f"{source} -> {target}: "
            f"expected={expected}, "
            f"actual={actual}, "
            f"status={'PASS' if passed else 'FAIL'}"
        )

    print()
    print(
        "Overall:",
        "PASS" if all_passed else "FAIL",
    )

finally:
    backend.close()
