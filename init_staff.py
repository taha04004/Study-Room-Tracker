# init_staff.py
import sqlite3
from werkzeug.security import generate_password_hash

STAFF_DB = "staff.db"

def init_staff_db():
    conn = sqlite3.connect(STAFF_DB)
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS staff")

    cur.execute("""
        CREATE TABLE staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    # Default staff account:
    username = "admin"
    password = "Admin123"
    pw_hash = generate_password_hash(password)

    cur.execute(
        "INSERT INTO staff (username, password_hash) VALUES (?, ?)",
        (username, pw_hash)
    )

    conn.commit()
    conn.close()
    print("staff.db initialized with default user:")
    print("   username: admin")
    print("   password: Admin123")


if __name__ == "__main__":
    init_staff_db()
