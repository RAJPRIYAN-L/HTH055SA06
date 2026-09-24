from database import get_connection


bookings = [
    # Monday
    ("B001", "R01", "2026-09-21 09:00", "2026-09-21 10:00", 3, "COMPLETED"),
    ("B002", "R04", "2026-09-21 10:00", "2026-09-21 11:00", 2, "RELEASED"),
    ("B003", "R02", "2026-09-21 14:00", "2026-09-21 15:00", 6, "COMPLETED"),

    # Tuesday
    ("B004", "R03", "2026-09-22 09:00", "2026-09-22 10:00", 10, "COMPLETED"),
    ("B005", "R05", "2026-09-22 11:00", "2026-09-22 12:00", 0, "NO_SHOW"),
    ("B006", "R01", "2026-09-22 15:00", "2026-09-22 16:00", 2, "COMPLETED"),

    # Wednesday
    ("B007", "R04", "2026-09-23 09:00", "2026-09-23 10:00", 3, "COMPLETED"),
    ("B008", "R02", "2026-09-23 11:00", "2026-09-23 12:00", 0, "NO_SHOW"),
    ("B009", "R05", "2026-09-23 14:00", "2026-09-23 15:00", 15, "COMPLETED"),

    # Thursday
    ("B010", "R03", "2026-09-24 09:00", "2026-09-24 10:00", 8, "COMPLETED"),
    ("B011", "R04", "2026-09-24 11:00", "2026-09-24 12:00", 0, "NO_SHOW"),
    ("B012", "R01", "2026-09-24 15:00", "2026-09-24 16:00", 4, "COMPLETED"),

    # Friday
    ("B013", "R02", "2026-09-25 09:00", "2026-09-25 10:00", 5, "COMPLETED"),
    ("B014", "R05", "2026-09-25 11:00", "2026-09-25 12:00", 4, "COMPLETED"),
    ("B015", "R03", "2026-09-25 14:00", "2026-09-25 15:00", 0, "NO_SHOW"),

    # Saturday
    ("B016", "R01", "2026-09-26 09:00", "2026-09-26 10:00", 2, "COMPLETED"),
    ("B017", "R04", "2026-09-26 11:00", "2026-09-26 12:00", 12, "COMPLETED"),

    # Sunday
    ("B018", "R02", "2026-09-27 10:00", "2026-09-27 11:00", 7, "COMPLETED"),
    ("B019", "R05", "2026-09-27 14:00", "2026-09-27 15:00", 0, "NO_SHOW")
]


connection = get_connection()
cursor = connection.cursor()

for booking in bookings:
    cursor.execute("""
        INSERT OR IGNORE INTO bookings
        (booking_id, room_id, start_time, end_time, attendees, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, booking)

connection.commit()
connection.close()

print("19 simulated bookings added successfully!")