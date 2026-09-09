import ladybug as lb

database = lb.Database(":memory:")
connection = lb.Connection(database)

try:
    print("Ladybug connection created.")

    print("\nOfficial extensions:")
    extensions = connection.execute("CALL SHOW_OFFICIAL_EXTENSIONS() RETURN *;")

    for row in extensions:
        print(row)

    print("\nChecking algo extension...")

    try:
        connection.execute("LOAD algo;")
        print("algo extension is already installed and loaded.")

    except Exception as load_error:
        print("Could not load the algo extension.")
        print("Reason:", load_error)

        print(
            "\nDo not install it yet. We first want to confirm "
            "whether Ladybug 0.20.2 provides a compatible build."
        )

    print("\nLoaded extensions:")

    loaded_extensions = connection.execute("CALL SHOW_LOADED_EXTENSIONS() RETURN *;")

    for row in loaded_extensions:
        print(row)

finally:
    connection.close()
