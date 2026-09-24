from flask import Flask, jsonify, request, send_from_directory
import sqlite3
import os
from datetime import datetime, timedelta

from decision_engine import decide_room_action


app = Flask(__name__)


# ============================================================
# PATHS
# ============================================================

DATABASE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "database",
    "smartroom.db"
)

FRONTEND_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "frontend"
)


# ============================================================
# SETTINGS
# ============================================================

GRACE_PERIOD_MINUTES = 10


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    return connection


# ============================================================
# SIMULATED OCCUPANCY
# IMPORTANT:
# This represents simulated sensor data for the prototype.
# It is NOT connected to physical sensors yet.
# ============================================================

occupancy_data = {
    "R01": 0,
    "R02": 5,
    "R03": 2,
    "R04": 0,
    "R05": 12
}


# ============================================================
# AUTOMATIC BOOKING LIFECYCLE
# ============================================================

def update_booking_statuses():

    connection = get_connection()
    cursor = connection.cursor()

    now = datetime.now()

    cursor.execute("""
        SELECT
            booking_id,
            room_id,
            start_time,
            end_time,
            status
        FROM bookings
        WHERE status IN ('BOOKED', 'ACTIVE')
    """)

    bookings = cursor.fetchall()

    for booking in bookings:

        booking_id = booking[0]
        room_id = booking[1]
        start_time_text = booking[2]
        end_time_text = booking[3]
        current_status = booking[4]

        try:
            start_time = datetime.fromisoformat(
                start_time_text
            )

            end_time = datetime.fromisoformat(
                end_time_text
            )

        except ValueError:
            continue

        current_occupancy = occupancy_data.get(
            room_id,
            0
        )

        # ----------------------------------------------------
        # CASE 1: MEETING HAS NOT STARTED
        # ----------------------------------------------------

        if now < start_time:

            if current_status != "BOOKED":

                cursor.execute("""
                    UPDATE bookings
                    SET status = 'BOOKED'
                    WHERE booking_id = ?
                """, (booking_id,))

            continue

        # ----------------------------------------------------
        # CASE 2: MEETING HAS ENDED
        # ----------------------------------------------------

        if now >= end_time:

            if current_status == "ACTIVE":

                cursor.execute("""
                    UPDATE bookings
                    SET status = 'COMPLETED'
                    WHERE booking_id = ?
                """, (booking_id,))

            elif current_status == "BOOKED":

                cursor.execute("""
                    UPDATE bookings
                    SET status = 'NO_SHOW'
                    WHERE booking_id = ?
                """, (booking_id,))

            continue

        # ----------------------------------------------------
        # CASE 3: MEETING IS CURRENTLY RUNNING
        # ----------------------------------------------------

        minutes_since_start = (
            now - start_time
        ).total_seconds() / 60

        # ----------------------------------------------------
        # PEOPLE HAVE ARRIVED
        # ----------------------------------------------------

        if current_occupancy > 0:

            if current_status != "ACTIVE":

                cursor.execute("""
                    UPDATE bookings
                    SET status = 'ACTIVE'
                    WHERE booking_id = ?
                """, (booking_id,))

        # ----------------------------------------------------
        # NOBODY HAS ARRIVED
        # ----------------------------------------------------

        else:

            if minutes_since_start >= GRACE_PERIOD_MINUTES:

                cursor.execute("""
                    UPDATE bookings
                    SET status = 'NO_SHOW'
                    WHERE booking_id = ?
                """, (booking_id,))

    connection.commit()
    connection.close()


# ============================================================
# FRONTEND
# ============================================================

@app.route("/")
def dashboard():

    return send_from_directory(
        FRONTEND_PATH,
        "index.html"
    )


# ============================================================
# ROOMS API
# ============================================================

@app.route("/api/rooms", methods=["GET"])
def api_rooms():

    # Update booking statuses first
    update_booking_statuses()

    connection = get_connection()

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            room_id,
            room_name,
            capacity,
            location,
            status
        FROM rooms
        ORDER BY room_id
    """)

    rooms = cursor.fetchall()

    connection.close()

    rooms_list = []

    for room in rooms:

        rooms_list.append({
            "room_id": room["room_id"],
            "room_name": room["room_name"],
            "capacity": room["capacity"],
            "location": room["location"],
            "status": room["status"]
        })

    return jsonify(rooms_list)


# ============================================================
# OCCUPANCY API
# ============================================================

@app.route("/api/occupancy", methods=["GET"])
def get_occupancy():

    return jsonify(occupancy_data)


@app.route("/api/occupancy", methods=["POST"])
def update_occupancy():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "message": "No data received"
        }), 400

    room_id = data.get("room_id")

    people_count = data.get(
        "people_count"
    )

    if room_id not in occupancy_data:

        return jsonify({
            "success": False,
            "message": "Invalid room ID"
        }), 400

    try:

        people_count = int(
            people_count
        )

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message": "People count must be a number"
        }), 400

    if people_count < 0:

        return jsonify({
            "success": False,
            "message": "People count cannot be negative"
        }), 400

    occupancy_data[room_id] = people_count

    return jsonify({
        "success": True,
        "room_id": room_id,
        "people_count": people_count
    })


# ============================================================
# BOOKINGS - GET
# ============================================================

@app.route("/api/bookings", methods=["GET"])
def get_bookings():

    # Automatically update booking lifecycle
    update_booking_statuses()

    connection = get_connection()

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            booking_id,
            room_id,
            start_time,
            end_time,
            attendees,
            status
        FROM bookings
        ORDER BY start_time
    """)

    bookings = cursor.fetchall()

    connection.close()

    bookings_list = []

    for booking in bookings:

        bookings_list.append({
            "booking_id": booking["booking_id"],
            "room_id": booking["room_id"],
            "start_time": booking["start_time"],
            "end_time": booking["end_time"],
            "attendees": booking["attendees"],
            "status": booking["status"]
        })

    return jsonify(bookings_list)


# ============================================================
# BOOKINGS - CREATE
# ============================================================

@app.route("/api/bookings", methods=["POST"])
def create_booking():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "message": "No booking data received"
        }), 400

    room_id = data.get("room_id")

    start_time = data.get(
        "start_time"
    )

    end_time = data.get(
        "end_time"
    )

    attendees = data.get(
        "attendees"
    )

    if (
        not room_id
        or not start_time
        or not end_time
        or attendees is None
    ):

        return jsonify({
            "success": False,
            "message":
                "Room, start time, end time and attendees are required"
        }), 400

    # --------------------------------------------------------
    # Convert attendees to integer
    # --------------------------------------------------------

    try:

        attendees = int(
            attendees
        )

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message": "Attendees must be a number"
        }), 400

    if attendees <= 0:

        return jsonify({
            "success": False,
            "message": "Attendees must be greater than zero"
        }), 400

    # --------------------------------------------------------
    # Validate date/time
    # --------------------------------------------------------

    try:

        start_datetime = datetime.fromisoformat(
            start_time
        )

        end_datetime = datetime.fromisoformat(
            end_time
        )

    except ValueError:

        return jsonify({
            "success": False,
            "message": "Invalid date or time format"
        }), 400

    if end_datetime <= start_datetime:

        return jsonify({
            "success": False,
            "message": "End time must be after start time"
        }), 400

    # --------------------------------------------------------
    # Connect database
    # --------------------------------------------------------

    connection = get_connection()

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    # --------------------------------------------------------
    # Check room
    # --------------------------------------------------------

    cursor.execute("""
        SELECT
            room_id,
            room_name,
            capacity,
            location,
            status
        FROM rooms
        WHERE room_id = ?
    """, (room_id,))

    room = cursor.fetchone()

    if room is None:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Room not found"
        }), 404

    # --------------------------------------------------------
    # Check room capacity
    # --------------------------------------------------------

    if attendees > room["capacity"]:

        connection.close()

        return jsonify({
            "success": False,
            "message":
                f"{room['room_name']} can accommodate only "
                f"{room['capacity']} people"
        }), 400

    # --------------------------------------------------------
    # Check booking conflict
    # --------------------------------------------------------

    cursor.execute("""
        SELECT
            booking_id,
            start_time,
            end_time
        FROM bookings
        WHERE room_id = ?
        AND status IN ('BOOKED', 'ACTIVE')
        AND start_time < ?
        AND end_time > ?
    """, (
        room_id,
        end_time,
        start_time
    ))

    existing_booking = cursor.fetchone()

    if existing_booking:

        connection.close()

        return jsonify({
            "success": False,
            "message":
                "Room is already booked during this time"
        }), 409

    # --------------------------------------------------------
    # Generate new booking ID
    # --------------------------------------------------------

    cursor.execute("""
        SELECT booking_id
        FROM bookings
        ORDER BY booking_id DESC
        LIMIT 1
    """)

    last_booking = cursor.fetchone()

    if last_booking:

        try:

            last_number = int(
                last_booking["booking_id"].replace(
                    "B",
                    ""
                )
            )

            new_number = last_number + 1

        except (
            ValueError,
            AttributeError
        ):

            new_number = 1

    else:

        new_number = 1

    booking_id = f"B{new_number:03d}"

    # --------------------------------------------------------
    # Insert booking
    # --------------------------------------------------------

    cursor.execute("""
        INSERT INTO bookings
        (
            booking_id,
            room_id,
            start_time,
            end_time,
            attendees,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        booking_id,
        room_id,
        start_time,
        end_time,
        attendees,
        "BOOKED"
    ))

    connection.commit()

    connection.close()

    return jsonify({
        "success": True,
        "message": "Room booked successfully",
        "booking": {
            "booking_id": booking_id,
            "room_id": room_id,
            "start_time": start_time,
            "end_time": end_time,
            "attendees": attendees,
            "status": "BOOKED"
        }
    }), 201


# ============================================================
# DECISION ENGINE API
# ============================================================

@app.route("/api/decision", methods=["POST"])
def get_decision():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "message": "No decision data received"
        }), 400

    current_occupancy = data.get(
        "current_occupancy",
        0
    )

    expected_attendees = data.get(
        "expected_attendees",
        0
    )

    room_capacity = data.get(
        "room_capacity",
        0
    )

    minutes_since_start = data.get(
        "minutes_since_start",
        0
    )

    grace_period = data.get(
        "grace_period",
        10
    )

    decision = decide_room_action(
        current_occupancy=current_occupancy,
        expected_attendees=expected_attendees,
        room_capacity=room_capacity,
        minutes_since_start=minutes_since_start,
        grace_period=grace_period
    )

    return jsonify({
        "success": True,
        "decision": decision,
        "current_occupancy": current_occupancy,
        "expected_attendees": expected_attendees,
        "room_capacity": room_capacity,
        "minutes_since_start": minutes_since_start,
        "grace_period": grace_period
    })


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )