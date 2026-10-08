"""
Movie Ticket Booking System - command line app
Run:  python app.py
"""

from datetime import datetime

import database as dbm

ADMIN_PASSWORD = "admin123"      # change this


# ---------- small helpers ----------
def ask_number(prompt, valid):
    """Ask until the user enters a number in `valid`; returns None on 0."""
    while True:
        raw = input(prompt).strip()
        if raw == "0":
            return None
        if raw.isdigit() and int(raw) in valid:
            return int(raw)
        print("  Invalid choice, try again (0 to go back).")


def parse_seats(text):
    seats = []
    for part in text.replace(",", " ").split():
        part = part.upper()
        if len(part) < 2 or part[0] not in dbm.ROWS or not part[1:].isdigit():
            return None
        if not 1 <= int(part[1:]) <= dbm.COLS:
            return None
        if part not in seats:
            seats.append(part)
    return seats or None


def print_seats(booked):
    print("\n              S C R E E N")
    print("       " + " ".join(f"{c:>2}" for c in range(1, dbm.COLS + 1)))
    for r in dbm.ROWS:
        cells = " ".join(" X" if f"{r}{c}" in booked else " ." for c in range(1, dbm.COLS + 1))
        print(f"  {r}    {cells}    Rs.{dbm.PRICE_BY_ROW[r]}")
    print("  (. = available, X = booked)")
    print("  Rows A-C Standard | D-F Premium | G-H Recliner")


def print_ticket(b):
    print("\n" + "=" * 40)
    print("            MOVIE TICKET")
    print("=" * 40)
    print(f" Booking ID : {b['id']}")
    print(f" Status     : {b['status']}")
    print(f" Name       : {b['customer_name']}")
    print(f" Movie      : {b['movie']}")
    print(f" Date/Time  : {b['show_date']}  {b['show_time']}")
    print(f" Screen     : {b['screen']}")
    print(f" Seats      : {b['seats']}")
    print(f" Total      : Rs.{b['total_amount']}")
    print(f" Booked on  : {b['created_at']}")
    print("=" * 40)


def pick_movie():
    movies = dbm.list_movies()
    print("\n--- Now Showing ---")
    for m in movies:
        print(f"  {m['id']}. {m['title']:<18} {m['genre']:<9} {m['language']:<8} "
              f"{m['duration_min']} min  [{m['rating']}]")
    mid = ask_number("Choose movie (0 to go back): ", {m["id"] for m in movies})
    return mid


def pick_show(movie_id):
    shows = dbm.list_upcoming_shows(movie_id)
    if not shows:
        print("  No upcoming shows for this movie.")
        return None
    print("\n--- Upcoming Shows ---")
    for i, s in enumerate(shows, 1):
        free = dbm.TOTAL_SEATS - s["booked_count"]
        print(f"  {i:>2}. {s['show_date']}  {s['show_time']}  {s['screen']}  "
              f"({free} seats free)")
    n = ask_number("Choose show (0 to go back): ", set(range(1, len(shows) + 1)))
    return shows[n - 1]["id"] if n else None


# ---------- menu actions ----------
def book_tickets():
    mid = pick_movie()
    if mid is None:
        return
    show_id = pick_show(mid)
    if show_id is None:
        return

    booked = dbm.booked_seats(show_id)
    if len(booked) >= dbm.TOTAL_SEATS:
        print("  Housefull! Please choose another show.")
        return
    print_seats(booked)

    while True:
        raw = input("\nEnter seats (e.g. A1, A2, B5) or 0 to cancel: ").strip()
        if raw == "0":
            return
        seats = parse_seats(raw)
        if not seats:
            print("  Invalid format. Use row letter + number, e.g. C4.")
            continue
        taken = [s for s in seats if s in booked]
        if taken:
            print(f"  Already booked: {', '.join(taken)}. Choose other seats.")
            continue
        break

    total = sum(dbm.PRICE_BY_ROW[s[0]] for s in seats)
    name = input("Your name: ").strip() or "Guest"
    phone = input("Phone number: ").strip()
    print(f"\nSeats: {', '.join(seats)}    Total: Rs.{total}")
    if input("Confirm booking? (y/n): ").strip().lower() != "y":
        print("Booking cancelled.")
        return

    try:
        booking = dbm.create_booking(show_id, name, phone, seats)
    except dbm.SeatTakenError as e:
        print(f"  {e} Please try again.")
        return
    print("\nPayment successful (demo). Booking confirmed!")
    print_ticket(booking)


def check_availability():
    mid = pick_movie()
    if mid is None:
        return
    show_id = pick_show(mid)
    if show_id is None:
        return
    print_seats(dbm.booked_seats(show_id))


def view_booking():
    bid = input("Enter Booking ID: ").strip().upper()
    b = dbm.get_booking(bid)
    print_ticket(b) if b else print("  No booking found with that ID.")


def my_bookings():
    phone = input("Enter your phone number: ").strip()
    rows = dbm.bookings_by_phone(phone)
    if not rows:
        print("  No bookings found for that number.")
        return
    for b in rows:
        print(f"  {b['id']}  {b['movie']:<18} {b['show_date']} {b['show_time']}  "
              f"{b['seats']:<14} Rs.{b['total_amount']:<5} {b['status']}")


def cancel_booking():
    bid = input("Enter Booking ID to cancel: ").strip().upper()
    b = dbm.get_booking(bid)
    if not b:
        print("  No booking found with that ID.")
        return
    if b["status"] == "CANCELLED":
        print("  This booking is already cancelled.")
        return
    show_start = datetime.strptime(f"{b['show_date']} {b['show_time']}", "%Y-%m-%d %H:%M")
    if show_start <= datetime.now():
        print("  The show has already started - cancellation not allowed.")
        return
    print_ticket(b)
    if input("Cancel this booking? (y/n): ").strip().lower() != "y":
        return
    dbm.cancel_booking(bid)
    print(f"  Cancelled. Refund of Rs.{b['total_amount']} will be processed (demo).")


def admin_panel():
    if input("Admin password: ").strip() != ADMIN_PASSWORD:
        print("  Wrong password.")
        return
    print("\n--- Revenue by movie (confirmed bookings) ---")
    for r in dbm.revenue_summary():
        print(f"  {r['title']:<18} bookings: {r['bookings']:<4} revenue: Rs.{r['revenue']}")
    print("\n--- All bookings ---")
    rows = dbm.all_bookings()
    if not rows:
        print("  No bookings yet.")
    for b in rows:
        print(f"  {b['id']}  {b['customer_name'][:12]:<12} {b['movie']:<18} "
              f"{b['show_date']} {b['show_time']}  {b['seats']:<14} "
              f"Rs.{b['total_amount']:<5} {b['status']}")


def main():
    dbm.init_db()
    actions = {
        "1": book_tickets,
        "2": check_availability,
        "3": view_booking,
        "4": my_bookings,
        "5": cancel_booking,
        "6": admin_panel,
    }
    while True:
        print("\n===== MOVIE TICKET BOOKING =====")
        print(" 1. Book tickets")
        print(" 2. Check seat availability")
        print(" 3. View booking by ID")
        print(" 4. My bookings (by phone)")
        print(" 5. Cancel booking")
        print(" 6. Admin panel")
        print(" 7. Exit")
        choice = input("Choose: ").strip()
        if choice == "7":
            print("Thank you! Enjoy the movie.")
            break
        action = actions.get(choice)
        action() if action else print("  Invalid option.")


if __name__ == "__main__":
    main()
