from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Integer
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import Booking, Tanker, GpsPing
import random, string

router = APIRouter()

# ── What data the booking form sends ──────────────────────────────
class BookingRequest(BaseModel):
    name:        str
    phone:       str
    ward:        str
    address:     str
    size_litres: int
    priority:    Optional[str] = "normal"

# ── POST /bookings — resident submits a booking ───────────────────
@router.post("/bookings")
def create_booking(data: BookingRequest, db: Session = Depends(get_db)):
    # Generate a booking ID like WTR-A3F1
    booking_id = "WTR-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

    booking = Booking(
        id          = booking_id,
        name        = data.name,
        phone       = data.phone,
        ward        = data.ward,
        address     = data.address,
        size_litres = data.size_litres,
        priority    = data.priority,
        status      = "pending",
        eta_minutes = random.randint(15, 45)  # real ETA logic comes in Phase 3
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return {"booking_id": booking.id, "eta_minutes": booking.eta_minutes, "status": "pending"}

# ── GET /bookings — admin sees all bookings ───────────────────────
@router.get("/bookings")
def list_bookings(db: Session = Depends(get_db)):
    bookings = db.query(Booking).order_by(Booking.created_at.desc()).all()
    return bookings

# ── GET /bookings/{id} — resident tracks their booking ───────────
@router.get("/bookings/{booking_id}")
def get_booking(booking_id: str, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking

# ── PATCH /bookings/{id}/assign — admin assigns a tanker ─────────
@router.patch("/bookings/{booking_id}/assign")
def assign_tanker(booking_id: str, tanker_id: str, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.tanker_id = tanker_id
    booking.status    = "assigned"
    db.commit()
    return {"message": f"Tanker {tanker_id} assigned to {booking_id}"}

# ── GET /tankers — list all tankers ──────────────────────────────
@router.get("/tankers")
def list_tankers(db: Session = Depends(get_db)):
    return db.query(Tanker).filter(Tanker.active == True).all()

# ── PATCH /bookings/{id}/deliver — mark as delivered ─────────────
@router.patch("/bookings/{booking_id}/deliver")
def mark_delivered(booking_id: str, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.status = "delivered"
    db.commit()
    return {"message": f"{booking_id} marked as delivered"}

# ── In-memory store for the LATEST position of each tanker ───────
# This means we can get any tanker's current location instantly
# without hitting the database every time
latest_positions = {}

class GpsUpdate(BaseModel):
    tanker_id: str
    lat:       float
    lng:       float

# ── POST /location — driver's phone calls this every 10 seconds ──
@router.post("/location")
def update_location(data: GpsUpdate, db: Session = Depends(get_db)):
    # 1. Save to in-memory dict (for instant live map reads)
    latest_positions[data.tanker_id] = {
        "tanker_id": data.tanker_id,
        "lat":       data.lat,
        "lng":       data.lng,
    }
    # 2. Also save to database (for route history later)
    ping = GpsPing(
        tanker_id = data.tanker_id,
        lat       = str(data.lat),
        lng       = str(data.lng),
    )
    db.add(ping)
    db.commit()
    return {"status": "ok"}

# ── GET /locations — admin map calls this to get all tanker spots ─
@router.get("/locations")
def get_locations():
    return list(latest_positions.values())

# ── GET /locations/{tanker_id} — get one tanker's current spot ───
@router.get("/locations/{tanker_id}")
def get_tanker_location(tanker_id: str):
    pos = latest_positions.get(tanker_id)
    if not pos:
        raise HTTPException(status_code=404, detail="No location data yet")
    return pos

# ── POST /tankers/seed — adds default tankers (run once after deploy) ──
@router.post("/tankers/seed")
def seed_tankers(db: Session = Depends(get_db)):
    default_tankers = [
        Tanker(id="TK-01", driver_name="Ramesh K.",  capacity=5000, fill_pct=85, ward="A"),
        Tanker(id="TK-02", driver_name="Sunil M.",   capacity=3000, fill_pct=60, ward="B"),
        Tanker(id="TK-03", driver_name="Dinesh P.",  capacity=5000, fill_pct=90, ward="B"),
        Tanker(id="TK-04", driver_name="Vijay R.",   capacity=2000, fill_pct=40, ward="C"),
        Tanker(id="TK-05", driver_name="Anand S.",   capacity=5000, fill_pct=100, ward="D"),
    ]
    for t in default_tankers:
        db.merge(t)
    db.commit()
    return {"message": "Tankers seeded successfully"}

from sqlalchemy import func
from datetime import datetime, timedelta

# ── GET /analytics/summary — key numbers for the dashboard ───────
@router.get("/analytics/summary")
def analytics_summary(db: Session = Depends(get_db)):
    total     = db.query(Booking).count()
    pending   = db.query(Booking).filter(Booking.status == "pending").count()
    assigned  = db.query(Booking).filter(Booking.status == "assigned").count()
    delivered = db.query(Booking).filter(Booking.status == "delivered").count()

    # Fulfillment rate
    fulfillment = round((delivered / total * 100), 1) if total > 0 else 0

    # Average ETA of delivered bookings
    avg_eta = db.query(func.avg(Booking.eta_minutes)).filter(
        Booking.status == "delivered"
    ).scalar()
    avg_eta = round(avg_eta, 1) if avg_eta else 0

    # Priority bookings fulfilled
    priority_total     = db.query(Booking).filter(Booking.priority == "high").count()
    priority_delivered = db.query(Booking).filter(
        Booking.priority == "high",
        Booking.status   == "delivered"
    ).count()
    priority_rate = round((priority_delivered / priority_total * 100), 1) if priority_total > 0 else 0

    return {
        "total":          total,
        "pending":        pending,
        "assigned":       assigned,
        "delivered":      delivered,
        "fulfillment":    fulfillment,
        "avg_eta":        avg_eta,
        "priority_rate":  priority_rate,
    }

# ── GET /analytics/by-ward — bookings count per ward ─────────────
@router.get("/analytics/by-ward")
def analytics_by_ward(db: Session = Depends(get_db)):
    results = db.query(
        Booking.ward,
        func.count(Booking.id).label("total"),
        func.sum(
            (Booking.status == "delivered").cast(Integer)
        ).label("delivered")
    ).group_by(Booking.ward).all()

    return [
        {
            "ward":      r.ward,
            "total":     r.total,
            "delivered": r.delivered or 0,
        }
        for r in results
    ]

# ── GET /analytics/by-size — popular tanker sizes ────────────────
@router.get("/analytics/by-size")
def analytics_by_size(db: Session = Depends(get_db)):
    results = db.query(
        Booking.size_litres,
        func.count(Booking.id).label("count")
    ).group_by(Booking.size_litres).order_by(Booking.size_litres).all()

    return [{"size": r.size_litres, "count": r.count} for r in results]

# ── GET /analytics/recent — last 7 days delivery count ───────────
@router.get("/analytics/recent")
def analytics_recent(db: Session = Depends(get_db)):
    days = []
    for i in range(6, -1, -1):
        day        = datetime.now() - timedelta(days=i)
        day_start  = day.replace(hour=0,  minute=0,  second=0)
        day_end    = day.replace(hour=23, minute=59, second=59)
        count      = db.query(Booking).filter(
            Booking.created_at >= day_start,
            Booking.created_at <= day_end
        ).count()
        days.append({
            "day":   day.strftime("%a"),   # Mon, Tue etc
            "date":  day.strftime("%d %b"),
            "count": count
        })
    return days