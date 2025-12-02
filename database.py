import sqlite3

DATABASE = "rooms.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ROOM FUNCTIONS
def get_all_rooms():
    conn = get_db()
    rows = conn.execute("SELECT * FROM rooms").fetchall()
    conn.close()
    return rows

def get_room(room_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    conn.close()
    return row


# BOOKING FUNCTIONS
def create_booking(email, room_id, date, start_time, end_time):
    conn = get_db()
    conn.execute("""
        INSERT INTO bookings (email, room_id, date, start_time, end_time)
        VALUES (?, ?, ?, ?, ?)
    """, (email, room_id, date, start_time, end_time))
    conn.commit()
    conn.close()

def get_bookings(email):
    conn = get_db()
    rows = conn.execute("""
        SELECT bookings.*, rooms.room_number
        FROM bookings
        JOIN rooms ON rooms.id = bookings.room_id
        WHERE email = ?
        ORDER BY date, start_time
    """, (email,)).fetchall()
    conn.close()
    return rows

def cancel_booking(booking_id):
    conn = get_db()
    conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()

def get_active_booking(room_id, today, current_time):
    conn = get_db()
    row = conn.execute("""
        SELECT * FROM bookings
        WHERE room_id = ?
        AND date = ?
        AND start_time <= ?
        AND end_time > ?
        ORDER BY end_time DESC
    """, (room_id, today, current_time, current_time)).fetchone()
    conn.close()
    return row


# OVERLAP LOGIC
def booking_overlap(email, date, start_time, end_time):
    conn = get_db()
    result = conn.execute("""
        SELECT * FROM bookings
        WHERE email = ?
        AND date = ?
        AND (start_time < ? AND end_time > ?)
    """, (email, date, end_time, start_time)).fetchone()

    conn.close()
    return result is not None
