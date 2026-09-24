from database import get_connection


rooms = [
    ("R01", "Meeting Room 1", 4, "Floor 1"),
    ("R02", "Meeting Room 2", 8, "Floor 1"),
    ("R03", "Meeting Room 3", 12, "Floor 2"),
    ("R04", "Meeting Room 4", 20, "Floor 2"),
    ("R05", "Meeting Room 5", 30, "Floor 3")
]


connection = get_connection()
cursor = connection.cursor()

for room in rooms:
    cursor.execute("""
        INSERT OR IGNORE INTO rooms
        (room_id, room_name, capacity, location)
        VALUES (?, ?, ?, ?)
    """, room)

connection.commit()
connection.close()

print("5 meeting rooms added successfully!")