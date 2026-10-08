"""Database layer (SQLite). All SQL lives here."""

import os
import random
import sqlite3
import string
from contextlib import contextmanager
from datetime import date, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "movie_booking.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

ROWS = "ABCDEFGH"
COLS = 10
PRICE_BY_ROW = {"A": 150, "B": 150, "C": 150,      # Standard
                "D": 220, "E": 220, "F": 220,      # Premium
                "G": 350, "H": 350}                # Recliner
TOTAL_SEATS = len(ROWS) * COLS

SHOW_TIMES = ["10:00", "14:00", "18:30", "21:45"]
DAYS_AHEAD = 7

SEED_MOVIES = [
    ("Space Odyssey",    "Sci-Fi",   "English", 148, "UA"),
    ("Laugh Riot",       "Comedy",   "Hindi",   132, "U"),
    ("Midnight Mystery", "Thriller", "English", 121, "A"),
    ("Dhoom Dhadaka",    "Action",   "Hindi",   155, "UA"),
]


class SeatTakenError(Exception):
    """Raised when one or more chosen seats are already booked."""


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------- setup ----------
def init_db():
    """Create tables, seed movies on first run, and top up upcoming shows."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    with db() as conn:
        conn.executescript(schema)
        if conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO movies (title, genre, language, duration_min, rating) "
                "VALUES (?, ?, ?, ?, ?)", SEED_MOVIES)
        ensure_upcoming_shows(conn)


def ensure_upcoming_shows(conn, days=DAYS_AHEAD):
    """Make sure every movie has shows for today and the next `days` days."""
    movie_ids = [r["id"] for r in conn.execute("SELECT id FROM movies")]
    for mid in movie_ids:
        screen = f"Screen {(mid - 1) % 3 + 1}"
        for d in range(days + 1):
            day = (date.today() + timedelta(days=d)).isoformat()
            for t in SHOW_TIMES:
                conn.execute(
                    "INSERT OR IGNORE INTO shows (movie_id, show_date, show_time, screen) "
                    "VALUES (?, ?, ?, ?)", (mid, day, t, screen))


# ---------- queries ----------
def list_movies():
    with db() as conn:
        return conn.execute("SELECT * FROM movies ORDER BY id").fetchall()


def list_upcoming_shows(movie_id, limit=12):
    with db() as conn:
        return conn.execute(
            """
            SELECT s.*,
                   (SELECT COUNT(*) FROM booking_seats bs WHERE bs.show_id = s.id) AS booked_count
            FROM shows s
            WHERE s.movie_id = ?
              AND (s.show_date > date('now', 'localtime')
                   OR (s.show_date = date('now', 'localtime')
                       AND s.show_time > strftime('%H:%M', 'now', 'localtime')))
            ORDER BY s.show_date, s.show_time
            LIMIT ?
            """, (movie_id, limit)).fetchall()


def get_show(show_id):
    with db() as conn:
        return conn.execute(
            "SELECT s.*, m.title FROM shows s JOIN movies m ON m.id = s.movie_id "
            "WHERE s.id = ?", (show_id,)).fetchone()


def booked_seats(show_id):
    with db() as conn:
        rows = conn.execute(
            "SELECT seat_no FROM booking_seats WHERE show_id = ?", (show_id,)).fetchall()
    return {r["seat_no"] for r in rows}


# ---------- bookings ----------
def _new_booking_id(conn):
    while True:
        bid = "BK" + "".join(random.choices(string.digits, k=5))
        if not conn.execute("SELECT 1 FROM bookings WHERE id = ?", (bid,)).fetchone():
            return bid


def create_booking(show_id, name, phone, seats):
    """Insert booking + seats in one transaction. Raises SeatTakenError on clash."""
    total = sum(PRICE_BY_ROW[s[0]] for s in seats)
    try:
        with db() as conn:
            bid = _new_booking_id(conn)
            conn.execute(
                "INSERT INTO bookings (id, customer_name, phone, show_id, seats, total_amount) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (bid, name, phone, show_id, ",".join(seats), total))
            conn.executemany(
                "INSERT INTO booking_seats (booking_id, show_id, seat_no, price) "
                "VALUES (?, ?, ?, ?)",
                [(bid, show_id, s, PRICE_BY_ROW[s[0]]) for s in seats])
    except sqlite3.IntegrityError:
        raise SeatTakenError("Some of those seats were just booked by someone else.")
    return get_booking(bid)


_BOOKING_SQL = """
    SELECT b.*, m.title AS movie, s.show_date, s.show_time, s.screen
    FROM bookings b
    JOIN shows  s ON s.id = b.show_id
    JOIN movies m ON m.id = s.movie_id
"""


def get_booking(booking_id):
    with db() as conn:
        return conn.execute(_BOOKING_SQL + " WHERE b.id = ?", (booking_id,)).fetchone()


def bookings_by_phone(phone):
    with db() as conn:
        return conn.execute(
            _BOOKING_SQL + " WHERE b.phone = ? ORDER BY b.created_at DESC", (phone,)).fetchall()


def all_bookings():
    with db() as conn:
        return conn.execute(_BOOKING_SQL + " ORDER BY b.created_at DESC").fetchall()


def cancel_booking(booking_id):
    """Free the seats and mark the booking CANCELLED. Returns the booking row."""
    with db() as conn:
        conn.execute("DELETE FROM booking_seats WHERE booking_id = ?", (booking_id,))
        conn.execute("UPDATE bookings SET status = 'CANCELLED' WHERE id = ?", (booking_id,))
    return get_booking(booking_id)


def revenue_summary():
    with db() as conn:
        return conn.execute(
            """
            SELECT m.title,
                   COUNT(b.id)                      AS bookings,
                   COALESCE(SUM(b.total_amount), 0) AS revenue
            FROM movies m
            LEFT JOIN shows s    ON s.movie_id = m.id
            LEFT JOIN bookings b ON b.show_id = s.id AND b.status = 'CONFIRMED'
            GROUP BY m.id ORDER BY revenue DESC
            """).fetchall()
