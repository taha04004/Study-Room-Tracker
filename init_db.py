import sqlite3

def init_db():
    conn = sqlite3.connect("rooms.db")
    cursor = conn.cursor()

    # Reset tables during development
    cursor.execute("DROP TABLE IF EXISTS bookings")
    cursor.execute("DROP TABLE IF EXISTS rooms")

    # Create rooms table
    cursor.execute("""
        CREATE TABLE rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT NOT NULL,
            capacity INTEGER NOT NULL,
            type TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    # Create bookings table
    cursor.execute("""
        CREATE TABLE bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            room_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
    """)

    # Insert sample rooms
    sample_rooms = [
        ("101", 4, "Study", "Available"),
        ("102", 6, "Study", "Available"),
        ("103", 2, "Quiet", "Occupied"),
        ("201", 8, "Group", "Available"),
        ("202", 10, "Group", "Available")
    ]

    cursor.executemany(
        "INSERT INTO rooms (room_number, capacity, type, status) VALUES (?, ?, ?, ?)",
        sample_rooms
    )

    conn.commit()
    conn.close()
    print("\n✅ Database initialized successfully!\n")


if __name__ == "__main__":
    init_db()
