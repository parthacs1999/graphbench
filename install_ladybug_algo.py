import ladybug as lb

database = lb.Database(":memory:")
connection = lb.Connection(database)

try:
    print("Installing the Ladybug ALGO extension...")

    connection.execute("INSTALL algo;")

    print("Installation completed.")
    print("Loading the ALGO extension...")

    connection.execute("LOAD algo;")

    print("ALGO extension loaded successfully.")

    print("\nLoaded extensions:")

    result = connection.execute("CALL SHOW_LOADED_EXTENSIONS() RETURN *;")

    for row in result:
        print(row)

except Exception as error:
    print("\nALGO extension setup failed.")
    print("Reason:", error)

finally:
    connection.close()
