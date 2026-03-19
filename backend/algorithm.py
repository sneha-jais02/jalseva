from geopy.distance import geodesic
from wards import get_ward_coords, WARD_COORDS
from models import Booking, Tanker
from database import SessionLocal

# ─────────────────────────────────────────────────────────────────
# SCORING — higher score = higher priority in the queue
# ─────────────────────────────────────────────────────────────────
def score_booking(booking):
    score = 0

    # 1. Wait time — every minute waiting adds 2 points
    #    so someone waiting 30 mins gets +60 points
    from datetime import datetime, timezone
    now     = datetime.now()
    created = booking.created_at
    # Handle both timezone-aware and naive datetimes
    if hasattr(created, 'tzinfo') and created.tzinfo:
        now = datetime.now(timezone.utc)
    waited_minutes = (now - created).seconds // 60
    score += waited_minutes * 2

    # 2. Priority category — senior/medical jumps the queue
    if booking.priority == "high":
        score += 50

    return score


# ─────────────────────────────────────────────────────────────────
# DISTANCE — km between a tanker and a booking address
# ─────────────────────────────────────────────────────────────────
def get_tanker_coords(tanker, live_positions: dict):
    # Use live GPS if the driver's phone is sending location
    if tanker.id in live_positions:
        pos = live_positions[tanker.id]
        return (pos["lat"], pos["lng"])
    # Otherwise fall back to the tanker's assigned ward centre
    coords = get_ward_coords(tanker.ward or "A")
    return (coords["lat"], coords["lng"])


def distance_km(tanker, booking, live_positions: dict):
    tanker_coords  = get_tanker_coords(tanker, live_positions)
    booking_coords = get_ward_coords(booking.ward)
    booking_point  = (booking_coords["lat"], booking_coords["lng"])
    return geodesic(tanker_coords, booking_point).km


# ─────────────────────────────────────────────────────────────────
# FAIRNESS — prevent one ward from taking all tankers
# ─────────────────────────────────────────────────────────────────
def ward_is_overserved(ward: str, db) -> bool:
    # Count how many tankers are currently assigned to this ward
    active_in_ward = db.query(Booking).filter(
        Booking.status   == "assigned",
        Booking.ward     == ward
    ).count()

    total_active = db.query(Booking).filter(
        Booking.status == "assigned"
    ).count()

    if total_active == 0:
        return False

    # If this ward already has more than 40% of all active deliveries
    # hold back non-priority bookings from it
    return (active_in_ward / total_active) > 0.4


# ─────────────────────────────────────────────────────────────────
# ANTI-HOARDING — same address twice in 4 hours gets deprioritised
# ─────────────────────────────────────────────────────────────────
def is_hoarding(booking, db) -> bool:
    from datetime import datetime, timedelta
    four_hours_ago = datetime.now() - timedelta(hours=4)
    recent = db.query(Booking).filter(
        Booking.address    == booking.address,
        Booking.status     == "delivered",
        Booking.created_at >= four_hours_ago
    ).count()
    return recent >= 1


# ─────────────────────────────────────────────────────────────────
# MAIN DISPATCH — runs every 30 seconds
# ─────────────────────────────────────────────────────────────────
def run_dispatch(live_positions: dict):
    db = SessionLocal()
    try:
        # Get all pending bookings
        pending = db.query(Booking).filter(
            Booking.status == "pending"
        ).all()

        if not pending:
            return  # nothing to do

        # Get all available tankers (idle or active, not busy)
        available_tankers = db.query(Tanker).filter(
            Tanker.status.in_(["idle", "active"]),
            Tanker.active  == True,
            Tanker.fill_pct > 10  # must have water left
        ).all()

        if not available_tankers:
            print("Dispatch: no tankers available right now")
            return

        # Score and sort bookings — highest score first
        scored = sorted(pending, key=lambda b: score_booking(b), reverse=True)

        assigned_tanker_ids = set()  # track what we've already used this round

        for booking in scored:
            if not available_tankers:
                break  # no more tankers left this round

            # Apply fairness check for non-priority bookings
            if booking.priority != "high":
                if ward_is_overserved(booking.ward, db):
                    print(f"Dispatch: Ward {booking.ward} overserved, skipping {booking.id}")
                    continue

            # Apply anti-hoarding check
            if is_hoarding(booking, db):
                if booking.priority != "high":
                    print(f"Dispatch: Hoarding detected at {booking.address}, skipping")
                    continue

            # Find the nearest available tanker not yet used this round
            candidates = [
                t for t in available_tankers
                if t.id not in assigned_tanker_ids
                and t.fill_pct >= (booking.size_litres / 50)  # has enough water
            ]

            if not candidates:
                continue

            nearest = min(
                candidates,
                key=lambda t: distance_km(t, booking, live_positions)
            )

            # Calculate ETA — rough estimate: 3 min/km + 5 min loading
            dist    = distance_km(nearest, booking, live_positions)
            eta     = int(dist * 3) + 5

            # Assign in the database
            booking.tanker_id   = nearest.id
            booking.status      = "assigned"
            booking.eta_minutes = eta
            nearest.status      = "busy"

            assigned_tanker_ids.add(nearest.id)

            print(f"Dispatch: {booking.id} → {nearest.id} "
                  f"(dist: {dist:.1f}km, ETA: {eta}min, "
                  f"priority: {booking.priority})")

        db.commit()

    except Exception as e:
        print(f"Dispatch error: {e}")
        db.rollback()
    finally:
        db.close()