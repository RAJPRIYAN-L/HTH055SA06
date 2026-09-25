from flask import Flask, jsonify, request, send_from_directory
import sqlite3
import os
from datetime import datetime

from decision_engine import decide_room_action


# ============================================================
# FLASK CONFIGURATION
# ============================================================

app = Flask(
    __name__,
    static_folder="../frontend",
    static_url_path=""
)

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATABASE_PATH = os.path.join(
    BASE_DIR,
    "..",
    "database",
    "smartroom.db"
)

GRACE_PERIOD_MINUTES = 10


# ============================================================
# SIMULATED OCCUPANCY
# ============================================================

# This is currently SIMULATED.
# Later this can be replaced with real room sensors.

occupancy_data = {
    "R01": 0,
    "R02": 5,
    "R03": 2,
    "R04": 0,
    "R05": 12
}


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# FRONTEND
# ============================================================

@app.route("/")
def home():

    return send_from_directory(
        os.path.join(
            BASE_DIR,
            "..",
            "frontend"
        ),
        "index.html"
    )


# ============================================================
# AUTOMATIC BOOKING STATUS UPDATE
# ============================================================

def update_booking_statuses():

    connection = get_connection()
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
        WHERE status IN ('BOOKED', 'ACTIVE')
    """)

    bookings = cursor.fetchall()

    now = datetime.now()

    for booking in bookings:

        try:

            start_time = datetime.fromisoformat(
                booking["start_time"]
            )

            end_time = datetime.fromisoformat(
                booking["end_time"]
            )

        except ValueError:

            continue

        current_occupancy = occupancy_data.get(
            booking["room_id"],
            0
        )

        # ----------------------------------------------------
        # FUTURE BOOKING
        # ----------------------------------------------------

        if now < start_time:

            continue

        # ----------------------------------------------------
        # MEETING CURRENTLY RUNNING
        # ----------------------------------------------------

        if start_time <= now < end_time:

            if current_occupancy > 0:

                cursor.execute("""
                    UPDATE bookings
                    SET status = 'ACTIVE'
                    WHERE booking_id = ?
                """, (
                    booking["booking_id"],
                ))

            else:

                minutes_since_start = (
                    now - start_time
                ).total_seconds() / 60

                if minutes_since_start >= GRACE_PERIOD_MINUTES:

                    cursor.execute("""
                        UPDATE bookings
                        SET status = 'NO_SHOW'
                        WHERE booking_id = ?
                    """, (
                        booking["booking_id"],
                    ))

        # ----------------------------------------------------
        # MEETING ENDED
        # ----------------------------------------------------

        elif now >= end_time:

            if booking["status"] == "ACTIVE":

                cursor.execute("""
                    UPDATE bookings
                    SET status = 'COMPLETED'
                    WHERE booking_id = ?
                """, (
                    booking["booking_id"],
                ))

            else:

                cursor.execute("""
                    UPDATE bookings
                    SET status = 'NO_SHOW'
                    WHERE booking_id = ?
                """, (
                    booking["booking_id"],
                ))

    connection.commit()
    connection.close()


# ============================================================
# ROOMS API
# ============================================================

@app.route("/api/rooms", methods=["GET"])
def get_rooms():

    update_booking_statuses()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            room_id,
            room_name,
            capacity,
            location
        FROM rooms
        ORDER BY room_id
    """)

    rooms = [
        dict(row)
        for row in cursor.fetchall()
    ]

    cursor.execute("""
        SELECT
            room_id,
            booking_id,
            start_time,
            end_time,
            status
        FROM bookings
        WHERE status IN ('BOOKED', 'ACTIVE')
        ORDER BY start_time ASC
    """)

    bookings = cursor.fetchall()

    connection.close()

    now = datetime.now()

    for room in rooms:

        room_id = room["room_id"]

        room["current_occupancy"] = occupancy_data.get(
            room_id,
            0
        )

        current_booking = None
        upcoming_booking = None

        for booking in bookings:

            if booking["room_id"] != room_id:
                continue

            try:

                start_time = datetime.fromisoformat(
                    booking["start_time"]
                )

                end_time = datetime.fromisoformat(
                    booking["end_time"]
                )

            except ValueError:

                continue

            if start_time <= now < end_time:

                current_booking = booking
                break

            elif start_time > now:

                if upcoming_booking is None:

                    upcoming_booking = booking

        # ------------------------------------------------
        # CURRENT MEETING
        # ------------------------------------------------

        if current_booking:

            if current_booking["status"] == "ACTIVE":

                room["status"] = "OCCUPIED"

            else:

                room["status"] = "BOOKED"

            room["booking_id"] = current_booking["booking_id"]

            room["start_time"] = current_booking["start_time"]
            room["end_time"] = current_booking["end_time"]

        # ------------------------------------------------
        # UPCOMING BOOKING
        # ------------------------------------------------

        elif upcoming_booking:

            room["status"] = "BOOKED"

            room["booking_id"] = upcoming_booking["booking_id"]

            room["start_time"] = upcoming_booking["start_time"]
            room["end_time"] = upcoming_booking["end_time"]

        # ------------------------------------------------
        # NO BOOKING
        # ------------------------------------------------

        else:

            room["status"] = "AVAILABLE"

            room["booking_id"] = None

    return jsonify({
        "success": True,
        "rooms": rooms
    })


# ============================================================
# OCCUPANCY API - GET
# ============================================================

@app.route("/api/occupancy", methods=["GET"])
def get_occupancy():

    return jsonify({
        "success": True,
        "occupancy": occupancy_data
    })


# ============================================================
# OCCUPANCY API - UPDATE
# ============================================================

@app.route("/api/occupancy", methods=["POST"])
def update_occupancy():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "message": "No occupancy data received"
        }), 400

    room_id = data.get("room_id")
    occupancy = data.get("occupancy")

    if room_id not in occupancy_data:

        return jsonify({
            "success": False,
            "message": "Invalid room ID"
        }), 400

    try:

        occupancy = int(occupancy)

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message": "Occupancy must be a number"
        }), 400

    if occupancy < 0:

        return jsonify({
            "success": False,
            "message": "Occupancy cannot be negative"
        }), 400

    occupancy_data[room_id] = occupancy

    update_booking_statuses()

    return jsonify({
        "success": True,
        "room_id": room_id,
        "occupancy": occupancy
    })


# ============================================================
# OCCUPANCY SIMULATOR
# ============================================================

@app.route("/api/simulator/occupancy", methods=["POST"])
def simulator_occupancy():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "message": "No simulator data received"
        }), 400

    room_id = data.get("room_id")
    occupancy = data.get("occupancy")

    if not room_id:

        return jsonify({
            "success": False,
            "message": "room_id is required"
        }), 400

    if occupancy is None:

        return jsonify({
            "success": False,
            "message": "occupancy is required"
        }), 400

    try:

        occupancy = int(occupancy)

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message": "occupancy must be a number"
        }), 400

    if occupancy < 0:

        return jsonify({
            "success": False,
            "message": "occupancy cannot be negative"
        }), 400

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT capacity
        FROM rooms
        WHERE room_id = ?
        """,
        (room_id,)
    )

    room = cursor.fetchone()

    connection.close()

    if room is None:

        return jsonify({
            "success": False,
            "message": "Room not found"
        }), 404

    if occupancy > room["capacity"]:

        return jsonify({
            "success": False,
            "message": "Occupancy cannot exceed room capacity"
        }), 400

    occupancy_data[room_id] = occupancy

    update_booking_statuses()

    return jsonify({
        "success": True,
        "room_id": room_id,
        "occupancy": occupancy,
        "message": (
            f"Occupancy for {room_id} "
            f"updated to {occupancy}"
        )
    })


# ============================================================
# BOOKINGS API - GET
# ============================================================

@app.route("/api/bookings", methods=["GET"])
def get_bookings():

    update_booking_statuses()

    connection = get_connection()
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
        ORDER BY start_time ASC
    """)

    bookings = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return jsonify({
        "success": True,
        "bookings": bookings
    })


# ============================================================
# BOOKINGS API - CREATE
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
    start_time = data.get("start_time")
    end_time = data.get("end_time")
    attendees = data.get("attendees")

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

    try:

        attendees = int(attendees)

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message": "Attendees must be a number"
        }), 400

    if attendees <= 0:

        return jsonify({
            "success": False,
            "message":
                "Attendees must be greater than zero"
        }), 400

    try:

        requested_start = datetime.fromisoformat(
            start_time
        )

        requested_end = datetime.fromisoformat(
            end_time
        )

    except ValueError:

        return jsonify({
            "success": False,
            "message":
                "Invalid date or time format"
        }), 400

    if requested_end <= requested_start:

        return jsonify({
            "success": False,
            "message":
                "End time must be after start time"
        }), 400

    update_booking_statuses()

    connection = get_connection()
    cursor = connection.cursor()

    # --------------------------------------------------------
    # CHECK ROOM
    # --------------------------------------------------------

    cursor.execute("""
        SELECT
            room_id,
            room_name,
            capacity,
            location
        FROM rooms
        WHERE room_id = ?
    """, (
        room_id,
    ))

    room = cursor.fetchone()

    if not room:

        connection.close()

        return jsonify({
            "success": False,
            "message":
                "Room not found"
        }), 404

    # --------------------------------------------------------
    # CHECK CAPACITY
    # --------------------------------------------------------

    if attendees > room["capacity"]:

        connection.close()

        return jsonify({
            "success": False,
            "message":
                f"Room capacity is only "
                f"{room['capacity']} people"
        }), 400

    # --------------------------------------------------------
    # CHECK BOOKING CONFLICT
    # --------------------------------------------------------

    cursor.execute("""
        SELECT
            booking_id
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

    conflict = cursor.fetchone()

    if conflict:

        connection.close()

        return jsonify({
            "success": False,
            "message":
                "This room is already booked during the selected time"
        }), 409

    # --------------------------------------------------------
    # CREATE BOOKING ID
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
                last_booking["booking_id"][1:]
            )

        except (ValueError, TypeError):

            last_number = 0

    else:

        last_number = 0

    booking_id = f"B{last_number + 1:03d}"

    # --------------------------------------------------------
    # INSERT BOOKING
    # --------------------------------------------------------

    cursor.execute("""
        INSERT INTO bookings (
            booking_id,
            room_id,
            start_time,
            end_time,
            attendees,
            status
        )
        VALUES (?, ?, ?, ?, ?, 'BOOKED')
    """, (
        booking_id,
        room_id,
        start_time,
        end_time,
        attendees
    ))

    connection.commit()
    connection.close()

    return jsonify({

        "success": True,

        "message":
            "Meeting room booked successfully",

        "booking": {

            "booking_id":
                booking_id,

            "room_id":
                room_id,

            "start_time":
                start_time,

            "end_time":
                end_time,

            "attendees":
                attendees,

            "status":
                "BOOKED"
        }

    }), 201


# ============================================================
# SMART ROOM SUGGESTIONS API
# ============================================================

@app.route("/api/suggestions", methods=["POST"])
def get_room_suggestions():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "message":
                "No suggestion data received"
        }), 400

    start_time = data.get("start_time")
    end_time = data.get("end_time")
    attendees = data.get("attendees")

    if (
        not start_time
        or not end_time
        or attendees is None
    ):

        return jsonify({
            "success": False,
            "message":
                "Start time, end time and attendees are required"
        }), 400

    try:

        attendees = int(attendees)

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message":
                "Attendees must be a number"
        }), 400

    if attendees <= 0:

        return jsonify({
            "success": False,
            "message":
                "Attendees must be greater than zero"
        }), 400

    try:

        requested_start = datetime.fromisoformat(
            start_time
        )

        requested_end = datetime.fromisoformat(
            end_time
        )

    except ValueError:

        return jsonify({
            "success": False,
            "message":
                "Invalid date or time format"
        }), 400

    if requested_end <= requested_start:

        return jsonify({
            "success": False,
            "message":
                "End time must be after start time"
        }), 400

    update_booking_statuses()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            room_id,
            room_name,
            capacity,
            location
        FROM rooms
        ORDER BY capacity ASC
    """)

    rooms = cursor.fetchall()

    cursor.execute("""
        SELECT
            room_id,
            start_time,
            end_time
        FROM bookings
        WHERE status IN ('BOOKED', 'ACTIVE')
        AND start_time < ?
        AND end_time > ?
    """, (
        end_time,
        start_time
    ))

    conflicting_bookings = cursor.fetchall()

    connection.close()

    busy_rooms = {
        booking["room_id"]
        for booking in conflicting_bookings
    }

    suggestions = []

    for room in rooms:

        if attendees > room["capacity"]:
            continue

        if room["room_id"] in busy_rooms:
            continue

        unused_capacity = (
            room["capacity"]
            - attendees
        )

        utilization = (
            attendees
            / room["capacity"]
        ) * 100

        suggestions.append({

            "room_id":
                room["room_id"],

            "room_name":
                room["room_name"],

            "capacity":
                room["capacity"],

            "location":
                room["location"],

            "unused_capacity":
                unused_capacity,

            "utilization_percentage":
                round(
                    utilization,
                    1
                )

        })

    suggestions.sort(
        key=lambda room: (
            room["unused_capacity"],
            room["capacity"]
        )
    )

    for index, room in enumerate(
        suggestions
    ):

        if index == 0:

            room["recommended"] = True

            room["recommendation_reason"] = (
                "Best capacity fit for "
                "the expected number of attendees"
            )

        else:

            room["recommended"] = False

            room["recommendation_reason"] = (
                "Alternative available room"
            )

    return jsonify({

        "success": True,

        "attendees":
            attendees,

        "suggestions":
            suggestions

    })


# ============================================================
# DECISION ENGINE API
# ============================================================

@app.route("/api/decision", methods=["POST"])
def room_decision():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "message":
                "No decision data received"
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

    try:

        current_occupancy = int(
            current_occupancy
        )

        expected_attendees = int(
            expected_attendees
        )

        room_capacity = int(
            room_capacity
        )

        minutes_since_start = float(
            minutes_since_start
        )

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message":
                "Decision values must be numeric"
        }), 400

    action = decide_room_action(

        current_occupancy=
            current_occupancy,

        expected_attendees=
            expected_attendees,

        room_capacity=
            room_capacity,

        minutes_since_start=
            minutes_since_start,

        grace_period=
            GRACE_PERIOD_MINUTES

    )

    return jsonify({

        "success": True,

        "decision":
            action,

        "current_occupancy":
            current_occupancy,

        "expected_attendees":
            expected_attendees,

        "room_capacity":
            room_capacity,

        "minutes_since_start":
            minutes_since_start,

        "grace_period":
            GRACE_PERIOD_MINUTES

    })


# ============================================================
# ANALYTICS API
# ============================================================

@app.route("/api/analytics", methods=["GET"])
def get_analytics():

    # Make sure booking statuses are up to date
    update_booking_statuses()

    connection = get_connection()
    cursor = connection.cursor()

    # --------------------------------------------------------
    # GET ALL ROOMS
    # --------------------------------------------------------

    cursor.execute("""
        SELECT
            room_id,
            room_name,
            capacity,
            location
        FROM rooms
        ORDER BY room_id
    """)

    rooms = cursor.fetchall()

    # --------------------------------------------------------
    # GET ALL BOOKINGS
    # --------------------------------------------------------

    cursor.execute("""
        SELECT
            booking_id,
            room_id,
            start_time,
            end_time,
            attendees,
            status
        FROM bookings
        ORDER BY start_time ASC
    """)

    bookings = cursor.fetchall()

    connection.close()

    # --------------------------------------------------------
    # OVERALL ANALYTICS
    # --------------------------------------------------------

    total_bookings = len(bookings)

    completed_bookings = 0
    no_show_bookings = 0
    active_bookings = 0
    upcoming_bookings = 0

    total_scheduled_minutes = 0
    total_completed_minutes = 0

    now = datetime.now()

    # Room-wise statistics
    room_stats = {}

    for room in rooms:

        room_stats[room["room_id"]] = {

            "room_id":
                room["room_id"],

            "room_name":
                room["room_name"],

            "capacity":
                room["capacity"],

            "location":
                room["location"],

            "total_bookings":
                0,

            "completed_bookings":
                0,

            "no_show_bookings":
                0,

            "active_bookings":
                0,

            "scheduled_minutes":
                0,

            "completed_minutes":
                0,

            "average_meeting_minutes":
                0,

            "utilization_percentage":
                0

        }

    # --------------------------------------------------------
    # PROCESS BOOKINGS
    # --------------------------------------------------------

    for booking in bookings:

        room_id = booking["room_id"]

        try:

            start_time = datetime.fromisoformat(
                booking["start_time"]
            )

            end_time = datetime.fromisoformat(
                booking["end_time"]
            )

        except (ValueError, TypeError):

            continue

        duration_minutes = (
            end_time - start_time
        ).total_seconds() / 60

        duration_minutes = max(
            0,
            duration_minutes
        )

        total_scheduled_minutes += duration_minutes

        # ----------------------------------------------------
        # OVERALL STATUS COUNTS
        # ----------------------------------------------------

        if booking["status"] == "COMPLETED":

            completed_bookings += 1

            total_completed_minutes += (
                duration_minutes
            )

        elif booking["status"] == "NO_SHOW":

            no_show_bookings += 1

        elif booking["status"] == "ACTIVE":

            active_bookings += 1

        elif booking["status"] == "BOOKED":

            if start_time > now:

                upcoming_bookings += 1

        # ----------------------------------------------------
        # ROOM STATISTICS
        # ----------------------------------------------------

        if room_id not in room_stats:

            continue

        room_stats[room_id]["total_bookings"] += 1

        room_stats[room_id]["scheduled_minutes"] += (
            duration_minutes
        )

        if booking["status"] == "COMPLETED":

            room_stats[room_id]["completed_bookings"] += 1

            room_stats[room_id]["completed_minutes"] += (
                duration_minutes
            )

        elif booking["status"] == "NO_SHOW":

            room_stats[room_id]["no_show_bookings"] += 1

        elif booking["status"] == "ACTIVE":

            room_stats[room_id]["active_bookings"] += 1

    # --------------------------------------------------------
    # CALCULATE ROOM METRICS
    # --------------------------------------------------------

    for room_id, stats in room_stats.items():

        completed_minutes = stats[
            "completed_minutes"
        ]

        completed_bookings_for_room = stats[
            "completed_bookings"
        ]

        scheduled_minutes = stats[
            "scheduled_minutes"
        ]

        # Average duration of completed meetings
        if completed_bookings_for_room > 0:

            stats["average_meeting_minutes"] = round(
                completed_minutes
                / completed_bookings_for_room,
                1
            )

        else:

            stats["average_meeting_minutes"] = 0

        # ----------------------------------------------------
        # ROOM UTILIZATION
        #
        # This represents the percentage of scheduled
        # meeting time that was actually completed.
        #
        # It is NOT sensor-based physical occupancy.
        # ----------------------------------------------------

        if scheduled_minutes > 0:

            stats["utilization_percentage"] = round(
                (
                    completed_minutes
                    / scheduled_minutes
                ) * 100,
                1
            )

        else:

            stats["utilization_percentage"] = 0

        stats["scheduled_minutes"] = round(
            stats["scheduled_minutes"],
            1
        )

        stats["completed_minutes"] = round(
            stats["completed_minutes"],
            1
        )

    # --------------------------------------------------------
    # OVERALL UTILIZATION
    # --------------------------------------------------------

    if total_scheduled_minutes > 0:

        overall_utilization = round(
            (
                total_completed_minutes
                / total_scheduled_minutes
            ) * 100,
            1
        )

    else:

        overall_utilization = 0

    # --------------------------------------------------------
    # CONVERT ROOM DICTIONARY TO LIST
    # --------------------------------------------------------

    room_analytics = list(
        room_stats.values()
    )

    return jsonify({

        "success": True,

        "summary": {

            "total_bookings":
                total_bookings,

            "completed_bookings":
                completed_bookings,

            "no_show_bookings":
                no_show_bookings,

            "active_bookings":
                active_bookings,

            "upcoming_bookings":
                upcoming_bookings,

            "total_scheduled_minutes":
                round(
                    total_scheduled_minutes,
                    1
                ),

            "total_completed_minutes":
                round(
                    total_completed_minutes,
                    1
                ),

            "overall_utilization_percentage":
                overall_utilization

        },

        "rooms":
            room_analytics

    })


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )