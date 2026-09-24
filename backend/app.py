from flask import Flask, jsonify, send_from_directory
import sqlite3
import os

app = Flask(__name__)

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


def get_connection():
    return sqlite3.connect(DATABASE_PATH)


@app.route("/")
def dashboard():
    return send_from_directory(FRONTEND_PATH, "index.html")


@app.route("/api/rooms")
def api_rooms():

    connection = get_connection()
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute("""
        SELECT room_id, room_name, capacity, location, status
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


if __name__ == "__main__":
    app.run(debug=True)