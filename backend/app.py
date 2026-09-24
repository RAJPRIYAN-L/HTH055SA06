from flask import Flask
import sqlite3
import os

app = Flask(__name__)

DATABASE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "database",
    "smartroom.db"
)


def get_connection():
    return sqlite3.connect(DATABASE_PATH)


@app.route("/")
def home():
    return "SmartRoom AI is connected to the database!"


@app.route("/rooms")
def rooms():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT room_id, room_name, capacity, location, status
        FROM rooms
    """)

    rooms_data = cursor.fetchall()

    connection.close()

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SmartRoom AI - Rooms</title>

        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 40px;
                background-color: #f5f7fa;
            }

            h1 {
                margin-bottom: 25px;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                background-color: white;
            }

            th, td {
                padding: 14px;
                border: 1px solid #ddd;
                text-align: left;
            }

            th {
                background-color: #eeeeee;
            }

            tr:hover {
                background-color: #f9f9f9;
            }
        </style>
    </head>

    <body>

        <h1>SmartRoom AI - Meeting Rooms</h1>

        <table>
            <tr>
                <th>Room ID</th>
                <th>Room Name</th>
                <th>Capacity</th>
                <th>Location</th>
                <th>Status</th>
            </tr>
    """

    for room in rooms_data:
        html += f"""
            <tr>
                <td>{room[0]}</td>
                <td>{room[1]}</td>
                <td>{room[2]}</td>
                <td>{room[3]}</td>
                <td>{room[4]}</td>
            </tr>
        """

    html += """
        </table>

    </body>
    </html>
    """

    return html


if __name__ == "__main__":
    app.run(debug=True)