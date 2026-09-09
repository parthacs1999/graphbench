import ladybug as lb

database = lb.Database(":memory:")
connection = lb.Connection(database)

try:
    print("Refreshing the ALGO extension...")

    connection.execute("UPDATE algo;")

    print("Extension downloaded.")
    print("Trying to load the extension...")

    connection.execute("LOAD algo;")

    print("PASS: ALGO extension loaded successfully.")

    print("\nLoaded extensions:")

    result = connection.execute("CALL SHOW_LOADED_EXTENSIONS() RETURN *;")

    for row in result:
        print(row)

except Exception as error:
    print("FAIL: ALGO extension still cannot be loaded.")
    print()
    print(error)

finally:
    connection.close()
