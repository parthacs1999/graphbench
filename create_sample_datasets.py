import random
from pathlib import Path

import pandas as pd

DATA_DIRECTORY = Path("data")
RANDOM_SEED = 42


def create_social_network() -> None:
    random_generator = random.Random(RANDOM_SEED)

    number_of_users = 500
    number_of_connections = 2_500

    connections = set()

    while len(connections) < number_of_connections:
        follower = random_generator.randrange(number_of_users)

        followed = random_generator.randrange(number_of_users)

        if follower != followed:
            connections.add(
                (
                    f"User_{follower}",
                    f"User_{followed}",
                )
            )

    dataframe = pd.DataFrame(
        sorted(connections),
        columns=[
            "follower",
            "followed",
        ],
    )

    dataframe.to_csv(
        DATA_DIRECTORY / "sample_social_network.csv",
        index=False,
    )


def create_web_links() -> None:
    random_generator = random.Random(RANDOM_SEED + 1)

    number_of_pages = 1_000
    number_of_links = 5_000

    links = set()

    while len(links) < number_of_links:
        source_page = random_generator.randrange(number_of_pages)

        target_page = random_generator.randrange(number_of_pages)

        if source_page != target_page:
            links.add(
                (
                    f"Page_{source_page}",
                    f"Page_{target_page}",
                )
            )

    dataframe = pd.DataFrame(
        sorted(links),
        columns=[
            "source_page",
            "target_page",
        ],
    )

    dataframe.to_csv(
        DATA_DIRECTORY / "sample_web_links.csv",
        index=False,
    )


def create_dependencies() -> None:
    random_generator = random.Random(RANDOM_SEED + 2)

    number_of_packages = 250
    number_of_dependencies = 1_000

    dependencies = set()

    while len(dependencies) < number_of_dependencies:
        package = random_generator.randrange(number_of_packages)

        dependency = random_generator.randrange(number_of_packages)

        if package != dependency:
            dependencies.add(
                (
                    f"Package_{package}",
                    f"Package_{dependency}",
                )
            )

    dataframe = pd.DataFrame(
        sorted(dependencies),
        columns=[
            "package",
            "depends_on",
        ],
    )

    dataframe.to_csv(
        DATA_DIRECTORY / "sample_dependencies.csv",
        index=False,
    )


def main() -> None:
    DATA_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    create_social_network()
    create_web_links()
    create_dependencies()

    print("Created sample datasets:")
    print("- data/sample_social_network.csv")
    print("- data/sample_web_links.csv")
    print("- data/sample_dependencies.csv")


if __name__ == "__main__":
    main()
