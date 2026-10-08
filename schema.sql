-- Movie Ticket Booking System - SQLite schema
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS movies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL UNIQUE,
    genre        TEXT    NOT NULL,
    language     TEXT    NOT NULL,
    duration_min INTEGER NOT NULL CHECK (duration_min > 0),
    rating       TEXT    NOT NULL            -- U, UA, A
);

CREATE TABLE IF NOT EXISTS shows (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id  INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    show_date TEXT    NOT NULL,              -- YYYY-MM-DD
    show_time TEXT    NOT NULL,              -- HH:MM (24h)
    screen    TEXT    NOT NULL,
    UNIQUE (movie_id, show_date, show_time)
);

CREATE TABLE IF NOT EXISTS bookings (
    id            TEXT    PRIMARY KEY,       -- e.g. BK48213
    customer_name TEXT    NOT NULL,
    phone         TEXT,
    show_id       INTEGER NOT NULL REFERENCES shows(id),
    seats         TEXT    NOT NULL,          -- "A1,A2"
    total_amount  INTEGER NOT NULL CHECK (total_amount >= 0),
    status        TEXT    NOT NULL DEFAULT 'CONFIRMED'
                  CHECK (status IN ('CONFIRMED', 'CANCELLED')),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- One row per booked seat. UNIQUE(show_id, seat_no) makes double booking
-- impossible, even if two people try at the same moment.
CREATE TABLE IF NOT EXISTS booking_seats (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id TEXT    NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    show_id    INTEGER NOT NULL REFERENCES shows(id),
    seat_no    TEXT    NOT NULL,
    price      INTEGER NOT NULL,
    UNIQUE (show_id, seat_no)
);

CREATE INDEX IF NOT EXISTS idx_shows_movie_date ON shows(movie_id, show_date);
CREATE INDEX IF NOT EXISTS idx_bookings_phone   ON bookings(phone);
CREATE INDEX IF NOT EXISTS idx_seats_show       ON booking_seats(show_id);
