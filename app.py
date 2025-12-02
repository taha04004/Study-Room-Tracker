from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

# ===== EMAIL IMPORTS =====
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email_config import EMAIL_ADDRESS, EMAIL_PASSWORD
# ==========================

app = Flask(__name__)

ROOMS_DB = "rooms.db"
STAFF_DB = "staff.db"

app.secret_key = "change_this_super_secret_key"
app.permanent_session_lifetime = timedelta(minutes=20)


# ==========================
# DB HELPERS
# ==========================
def get_db():
    conn = sqlite3.connect(ROOMS_DB)
    conn.row_factory = sqlite3.Row
    return conn


def get_staff_db():
    conn = sqlite3.connect(STAFF_DB)
    conn.row_factory = sqlite3.Row
    return conn


# ==========================
# EMAIL SENDER
# ==========================
def send_confirmation_email(to_email, room_number, date, start, end):
    subject = "Your Study Room Booking Confirmation"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color:#333;">
        <div style="max-width:600px; margin:auto; padding:20px;
                    border:1px solid #ddd; border-radius:10px;">
            
            <h2 style="color:#cc0000; text-align:center;">
                York University Study Room Booking
            </h2>

            <p>Hello,</p>

            <p>Your booking has been confirmed with the following details:</p>

            <div style="background:#f8f8f8; padding:15px; border-radius:8px;
                        border-left:4px solid #cc0000; margin-top:10px;">

                <p><strong>Room:</strong> {room_number}</p>
                <p><strong>Date:</strong> {date}</p>
                <p><strong>Time:</strong> {start} → {end}</p>
            </div>

            <p style="margin-top:20px;">
                Thank you for using the Study Room Tracker.
            </p>

            <p style="font-size:14px; color:#777; margin-top:25px; text-align:center;">
                This is an automated email. Please do not reply.
            </p>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Confirmation email sent successfully.")
    except Exception as e:
        print("Email sending failed:", e)


# ==========================
# TIME FORMATTER
# ==========================
def to_12h(time_str):
    """
    Convert 'HH:MM' (24h) to 'HH:MM AM/PM'.
    SAFETY FIX: handle '24:00' by clamping to '23:59' so strptime doesn't crash.
    """
    if time_str == "24:00":
        time_str = "23:59"
    return datetime.strptime(time_str, "%H:%M").strftime("%I:%M %p")


# ==========================
# AUTH HELPERS
# ==========================
def staff_required():
    if not session.get("staff_logged_in"):
        return False
    return True


# ==========================
# HOME PAGE
# ==========================
@app.route("/")
def home():
    return render_template("index.html")


# ==========================
# ROOMS LIST
# ==========================
@app.route("/rooms")
def rooms():
    conn = get_db()
    rooms = conn.execute("SELECT * FROM rooms").fetchall()

    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M")

    room_list = []
    for room in rooms:
        active = conn.execute("""
            SELECT end_time
            FROM bookings
            WHERE room_id=? AND date=? AND start_time <= ? AND end_time > ?
            LIMIT 1
        """, (room["id"], today, now, now)).fetchone()

        if active:
            status = f"Occupied until {to_12h(active['end_time'])}"
        else:
            status = "Available"

        room_list.append({
            "id": room["id"],
            "room_number": room["room_number"],
            "capacity": room["capacity"],
            "type": room["type"],
            "status": status
        })

    conn.close()
    return render_template("rooms.html", rooms=room_list)


# ==========================
# ROOM DETAILS + REAL-TIME STATUS
# ==========================
@app.route("/room/<int:id>")
def room_details(id):
    conn = get_db()
    room = conn.execute("SELECT * FROM rooms WHERE id=?", (id,)).fetchone()
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M")

    rows = conn.execute("""
        SELECT start_time, end_time
        FROM bookings
        WHERE room_id=? AND date=?
        ORDER BY start_time
    """, (id, today)).fetchall()

    # Real-time status
    occupied_now = None
    for b in rows:
        if b["start_time"] <= now < b["end_time"]:
            occupied_now = b["end_time"]

    if occupied_now:
        current_status = "occupied"
        occupied_until = to_12h(occupied_now)
    else:
        current_status = "available"
        occupied_until = None

    schedule = [{
        "start": to_12h(b["start_time"]),
        "end": to_12h(b["end_time"]),
        "booked": True
    } for b in rows]

    conn.close()
    return render_template(
        "room_details.html",
        room=room,
        today=today,
        current_status=current_status,
        occupied_until=occupied_until,
        schedule=schedule
    )


# ==========================
# BOOK ROOM
# ==========================
@app.route("/book")
def book():
    room_id = request.args.get("room_id")
    conn = get_db()
    rooms = conn.execute("SELECT * FROM rooms").fetchall()
    conn.close()
    return render_template("booking.html", rooms=rooms, preselected=room_id)


@app.route("/submit-booking", methods=["POST"])
def submit_booking():
    email = request.form["email"]
    room_id = request.form["room"]
    date = request.form["date"]
    start = request.form["start"]
    end = request.form["end"]

    if end <= start:
        return render_template(
            "booking.html",
            rooms=get_db().execute("SELECT * FROM rooms").fetchall(),
            message="End time must be after start time."
        )

    start_dt = datetime.strptime(start, "%H:%M")
    end_dt = datetime.strptime(end, "%H:%M")
    hours = (end_dt - start_dt).total_seconds() / 3600

    if hours <= 0:
        return render_template(
            "booking.html",
            rooms=get_db().execute("SELECT * FROM rooms").fetchall(),
            message="Invalid time range."
        )

    if hours > 6:
        return render_template(
            "booking.html",
            rooms=get_db().execute("SELECT * FROM rooms").fetchall(),
            message="You cannot book more than 6 hours."
        )

    conn = get_db()

    conflict = conn.execute("""
        SELECT *
        FROM bookings
        WHERE room_id=? AND date=? AND NOT (end_time <= ? OR start_time >= ?)
    """, (room_id, date, start, end)).fetchone()

    if conflict:
        day_bookings = conn.execute("""
            SELECT start_time, end_time
            FROM bookings
            WHERE room_id=? AND date=?
            ORDER BY start_time
        """, (room_id, date)).fetchall()

        def to_min(t):
            h, m = map(int, t.split(":"))
            return h * 60 + m

        req_min = int(hours * 60)
        start_min = to_min(start)

        for b in day_bookings:
            b_start = to_min(b["start_time"])
            b_end = to_min(b["end_time"])

            if start_min + req_min <= b_start:
                suggested_start = start_min
                suggested_end = suggested_start + req_min
                break

            if start_min < b_end:
                start_min = b_end
        else:
            suggested_start = start_min
            suggested_end = start_min + req_min

        def fmt(m):
            # clamp anything >= 24:00 to 23:59 to avoid invalid time
            if m >= 24 * 60:
                m = 24 * 60 - 1
            return f"{m//60:02d}:{m%60:02d}"

        msg = f"""
            <p>This room is booked during that time.</p>
            <p>Next available slot:</p>
            <strong>{to_12h(fmt(suggested_start))} → {to_12h(fmt(suggested_end))}</strong>
        """

        return render_template(
            "booking.html",
            rooms=get_db().execute("SELECT * FROM rooms").fetchall(),
            message=msg
        )

    # INSERT BOOKING
    conn.execute("""
        INSERT INTO bookings (email, room_id, date, start_time, end_time)
        VALUES (?, ?, ?, ?, ?)
    """, (email, room_id, date, start, end))
    conn.commit()

    # FETCH ROOM NUMBER FOR EMAIL
    room_row = conn.execute("SELECT room_number FROM rooms WHERE id=?", (room_id,)).fetchone()
    conn.close()

    # SEND CONFIRMATION EMAIL
    send_confirmation_email(
        email,
        room_row["room_number"],
        date,
        start,
        end
    )

    return redirect(url_for("history", msg="success", email=email))


# ==========================
# USER HISTORY + CANCEL OWN
# ==========================
@app.route("/history")
def history():
    msg = request.args.get("msg")
    email = request.args.get("email")

    if not email:
        return render_template("history.html", bookings=None, email=None, msg=msg)

    conn = get_db()
    rows = conn.execute("""
        SELECT bookings.*, rooms.room_number
        FROM bookings
        JOIN rooms ON rooms.id = bookings.room_id
        WHERE email=?
        ORDER BY date DESC, start_time
    """, (email,)).fetchall()
    conn.close()

    bookings = [{
        "id": b["id"],
        "room_number": b["room_number"],
        "date": b["date"],
        "start_time": to_12h(b["start_time"]),
        "end_time": to_12h(b["end_time"])
    } for b in rows]

    return render_template(
        "history.html",
        bookings=bookings,
        email=email,
        msg=msg
    )


@app.route("/cancel/<int:id>")
def cancel_booking(id):
    conn = get_db()
    row = conn.execute("SELECT email FROM bookings WHERE id=?", (id,)).fetchone()
    if row:
        email = row["email"]
        conn.execute("DELETE FROM bookings WHERE id=?", (id,))
        conn.commit()
        conn.close()
        return redirect(url_for("history", msg="deleted", email=email))
    return redirect(url_for("history"))


# ==========================
# STAFF LOGIN / LOGOUT
# ==========================
@app.route("/staff-login", methods=["GET", "POST"])
def staff_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_staff_db()
        staff = conn.execute(
            "SELECT * FROM staff WHERE username=?",
            (username,)
        ).fetchone()
        conn.close()

        if staff and check_password_hash(staff["password_hash"], password):
            session.permanent = True
            session["staff_logged_in"] = True
            session["staff_username"] = username
            return redirect(url_for("staff_dashboard"))

        return render_template("staff_login.html",
                               error="Invalid username or password.")

    return render_template("staff_login.html")


@app.route("/logout")
def logout():
    session.pop("staff_logged_in", None)
    session.pop("staff_username", None)
    return redirect(url_for("home"))


# ==========================
# STAFF DASHBOARD
# ==========================
@app.route("/staff-dashboard")
def staff_dashboard():
    if not staff_required():
        return redirect(url_for("staff_login"))

    conn = get_db()

    today = datetime.now().strftime("%Y-%m-%d")
    bookings_today = conn.execute("""
        SELECT COUNT(*) AS total
        FROM bookings
        WHERE date=?
    """, (today,)).fetchone()["total"]

    now = datetime.now().strftime("%H:%M")
    active_now = conn.execute("""
        SELECT COUNT(*) AS total
        FROM bookings
        WHERE date=? AND start_time <= ? AND end_time > ?
    """, (today, now, now)).fetchone()["total"]

    rooms_count = conn.execute("SELECT COUNT(*) AS total FROM rooms").fetchone()["total"]

    most_booked = conn.execute("""
        SELECT rooms.room_number, COUNT(bookings.id) AS total
        FROM rooms
        LEFT JOIN bookings ON rooms.id = bookings.room_id
        GROUP BY rooms.room_number
        ORDER BY total DESC
        LIMIT 1
    """).fetchone()

    recent_bookings = conn.execute("""
        SELECT bookings.id, bookings.date, bookings.start_time, bookings.end_time,
               bookings.email, rooms.room_number
        FROM bookings
        JOIN rooms ON rooms.id = bookings.room_id
        ORDER BY bookings.date DESC, bookings.start_time DESC
        LIMIT 20
    """).fetchall()

    conn.close()

    return render_template(
        "staff_dashboard.html",
        bookings_today=bookings_today,
        active_now=active_now,
        rooms_count=rooms_count,
        most_booked=most_booked,
        recent_bookings=recent_bookings
    )


# ==========================
# STAFF CANCEL ANY BOOKING
# ==========================
@app.route("/staff/cancel/<int:id>")
def staff_cancel_booking(id):
    if not staff_required():
        return redirect(url_for("staff_login"))

    conn = get_db()
    conn.execute("DELETE FROM bookings WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("staff_dashboard"))


# ==========================
# ROOM MANAGEMENT (STAFF)
# ==========================
@app.route("/manage-rooms")
def manage_rooms():
    if not staff_required():
        return redirect(url_for("staff_login"))

    conn = get_db()
    rooms = conn.execute("SELECT * FROM rooms ORDER BY room_number").fetchall()
    conn.close()
    return render_template("manage_rooms.html", rooms=rooms)


@app.route("/add-room", methods=["GET", "POST"])
def add_room():
    if not staff_required():
        return redirect(url_for("staff_login"))

    if request.method == "POST":
        room_number = request.form["room_number"]
        capacity = request.form["capacity"]
        room_type = request.form["type"]

        conn = get_db()
        conn.execute("""
            INSERT INTO rooms (room_number, capacity, type, status)
            VALUES (?, ?, ?, ?)
        """, (room_number, capacity, room_type, "Available"))
        conn.commit()
        conn.close()

        return redirect(url_for("manage_rooms"))

    return render_template("add_room.html")


@app.route("/edit-room/<int:id>", methods=["GET", "POST"])
def edit_room(id):
    if not staff_required():
        return redirect(url_for("staff_login"))

    conn = get_db()

    if request.method == "POST":
        room_number = request.form["room_number"]
        capacity = request.form["capacity"]
        room_type = request.form["type"]
        status = request.form["status"]

        conn.execute("""
            UPDATE rooms
            SET room_number=?, capacity=?, type=?, status=?
            WHERE id=?
        """, (room_number, capacity, room_type, status, id))
        conn.commit()
        conn.close()
        return redirect(url_for("manage_rooms"))

    room = conn.execute("SELECT * FROM rooms WHERE id=?", (id,)).fetchone()
    conn.close()
    return render_template("edit_room.html", room=room)


@app.route("/delete-room/<int:id>")
def delete_room(id):
    if not staff_required():
        return redirect(url_for("staff_login"))

    conn = get_db()
    conn.execute("DELETE FROM rooms WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("manage_rooms"))


# ==========================
# FILTER ROOMS (USER)
# ==========================
@app.route("/filter", methods=["GET", "POST"])
def filter_rooms():
    if request.method == "GET":
        return render_template("filter.html")

    date = request.form["date"]
    start = request.form["start"]
    end = request.form["end"]
    capacity = int(request.form["capacity"])

    conn = get_db()

    rooms = conn.execute("""
        SELECT * FROM rooms WHERE capacity >= ?
    """, (capacity,)).fetchall()

    available = []
    for room in rooms:
        conflict = conn.execute("""
            SELECT *
            FROM bookings
            WHERE room_id=? AND date=? AND NOT (end_time <= ? OR start_time >= ?)
        """, (room["id"], date, start, end)).fetchone()

        if not conflict:
            available.append(room)

    conn.close()

    return render_template(
        "filter_results.html",
        rooms=available,
        date=date,
        start=start,
        end=end,
        min_capacity=capacity
    )


# ==========================
# ANALYTICS (STAFF ONLY)
# ==========================
@app.route("/analytics")
def analytics():
    if not staff_required():
        return redirect(url_for("staff_login"))

    conn = get_db()

    bookings_per_room = conn.execute("""
        SELECT rooms.room_number, COUNT(bookings.id) AS total
        FROM rooms
        LEFT JOIN bookings ON rooms.id = bookings.room_id
        GROUP BY rooms.room_number
        ORDER BY total DESC
    """).fetchall()

    hours_per_room = conn.execute("""
        SELECT rooms.room_number,
               SUM((julianday('2000-01-01 ' || end_time) -
                    julianday('2000-01-01 ' || start_time)) * 24.0) AS total_hours
        FROM rooms
        LEFT JOIN bookings ON rooms.id = bookings.room_id
        GROUP BY rooms.room_number
        ORDER BY total_hours DESC
    """).fetchall()

    times = conn.execute("""
        SELECT start_time, COUNT(*) AS total
        FROM bookings
        GROUP BY start_time
        ORDER BY total DESC
    """).fetchall()

    bookings_per_day = conn.execute("""
        SELECT date, COUNT(*) AS total
        FROM bookings
        GROUP BY date
        ORDER BY date DESC
    """).fetchall()

    conn.close()

    return render_template(
        "analytics.html",
        bookings_per_room=bookings_per_room,
        hours_per_room=hours_per_room,
        times=times,
        bookings_per_day=bookings_per_day
    )


# ==========================
# RUN APP
# ==========================
if __name__ == "__main__":
    app.run(debug=True)
