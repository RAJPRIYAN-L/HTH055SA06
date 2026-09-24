import sqlite3
import os

DATABASE_PATH = os.path.join(
    os.path.dirname(__file__),
    "smartroom.db"
)


def get_connection():
    return sqlite3.connect(DATABASE_PATH)


def create_tables():
    connection = get_connection()
    cursor = connection.cursor()

    # Rooms table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_id TEXT PRIMARY KEY,
            room_name TEXT NOT NULL,
            capacity INTEGER NOT NULL,
            location TEXT,
            status TEXT DEFAULT 'AVAILABLE'
        )
    """)

    # Bookings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            attendees INTEGER NOT NULL,
            status TEXT DEFAULT 'BOOKED',
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    """)

    # Occupancy table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS occupancy (
            occupancy_id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            occupied INTEGER NOT NULL,
            people_count INTEGER DEFAULT 0,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    """)

    # Room history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS room_history (
            room_id TEXT PRIMARY KEY,
            total_bookings INTEGER DEFAULT 0,
            no_shows INTEGER DEFAULT 0,
            late_starts INTEGER DEFAULT 0,
            average_occupancy REAL DEFAULT 0,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    """)

    connection.commit()
    connection.close()


if __name__ == "__main__":
    create_tables()
    print("SmartRoom AI database created successfully!")