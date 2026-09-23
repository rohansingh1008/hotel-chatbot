import sqlite3

conn = sqlite3.connect("hotel.db")
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS bookings")
cur.execute("DROP TABLE IF EXISTS rooms")
cur.execute("DROP TABLE IF EXISTS hotels")
cur.execute("DROP TABLE IF EXISTS hotel_info")

cur.execute("""
CREATE TABLE hotels (
    hotel_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    city TEXT
)
""")

cur.execute("""
CREATE TABLE rooms (
    room_id INTEGER PRIMARY KEY,
    hotel_id INTEGER NOT NULL,
    room_type TEXT NOT NULL,
    price_per_night REAL NOT NULL,
    total_rooms INTEGER NOT NULL,
    capacity INTEGER NOT NULL,
    breakfast_included INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (hotel_id) REFERENCES hotels(hotel_id)
)
""")

cur.execute("""
CREATE TABLE bookings (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hotel_id INTEGER NOT NULL,
    room_type TEXT NOT NULL,
    check_in TEXT NOT NULL,
    check_out TEXT NOT NULL,
    rooms_booked INTEGER NOT NULL,
    FOREIGN KEY (hotel_id) REFERENCES hotels(hotel_id)
)
""")

cur.execute("""
CREATE TABLE hotel_info (
    topic TEXT PRIMARY KEY,
    answer TEXT NOT NULL
)
""")

cur.executemany(
    "INSERT INTO hotels (name, city) VALUES (?, ?)",
    [
        ("Sunrise Grand Hotel", "New York"),
        ("Blue Horizon Inn", "San Francisco"),
    ],
)

cur.execute("SELECT hotel_id, name FROM hotels")
hotel_ids = {name: hid for hid, name in cur.fetchall()}
sunrise_id = hotel_ids["Sunrise Grand Hotel"]
blue_id = hotel_ids["Blue Horizon Inn"]

cur.executemany(
    "INSERT INTO rooms (hotel_id, room_type, price_per_night, total_rooms, capacity, breakfast_included) VALUES (?, ?, ?, ?, ?, ?)",
    [
        (sunrise_id, "single", 60.0, 10, 1, 1),
        (sunrise_id, "double", 90.0, 8, 2, 1),
        (sunrise_id, "triple", 120.0, 5, 3, 1),
        (sunrise_id, "suite", 180.0, 4, 4, 1),

        (blue_id, "single", 55.0, 12, 1, 1),
        (blue_id, "double", 85.0, 10, 2, 1),
        (blue_id, "triple", 115.0, 6, 3, 1),
        (blue_id, "suite", 175.0, 3, 4, 1),
    ],
)

cur.executemany(
    "INSERT INTO bookings (hotel_id, room_type, check_in, check_out, rooms_booked) VALUES (?, ?, ?, ?, ?)",
    [
        (sunrise_id, "double", "2026-10-01", "2026-10-05", 3),
        (sunrise_id, "suite", "2026-10-02", "2026-10-04", 2),
        (blue_id, "double", "2026-10-01", "2026-10-03", 4),
    ],
)

cur.executemany(
    "INSERT INTO hotel_info (topic, answer) VALUES (?, ?)",
    [
        ("check_in_time", "Check-in time is 2:00 PM and check-out time is 11:00 AM."),
        ("pool", "Yes, the hotel has an outdoor swimming pool open from 7 AM to 9 PM, plus a smaller indoor pool for winter."),
        ("breakfast", "Breakfast is included in all room rates and is served buffet-style from 7 AM to 10:30 AM in the main restaurant."),
        ("cancellation_policy", "Free cancellation up to 48 hours before check-in. Cancellations within 48 hours are charged one night's stay."),
        ("wifi", "Free high-speed WiFi is available throughout the hotel."),
        ("parking", "Complimentary self-parking is available for all guests."),
    ],
)

conn.commit()
conn.close()
print("hotel.db created and seeded with multiple hotels.")